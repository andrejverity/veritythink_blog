"""Read the gated blog posts from private Google sources.

Reads the publishing Sheet's Redirects tab (archived Tumblr posts) and the
New posts tab (gated test/new posts). Rows whose status is in PUBLISH_GATES
are imported from their Google Doc, sanitized, and written as public-ready
snapshots under content/posts/<date-first folder>/.

No source identifiers or OAuth tokens are printed or placed in the site.
Only rows gated for publish can be built.
"""
import base64
import hashlib
import html
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent
POSTS_ROOT = ROOT / 'content' / 'posts'
STAGE = 'configuration'

# Rows in these statuses are (re)imported from their Google Doc.
PUBLISH_GATES = {'Publish', 'Published', 'Publish test'}
# Source-of-truth resource IDs that must never appear in public output. The
# management sheet, the Posts folder and every migrated source Doc are private;
# legacy posts may carry their original public links (including old public
# Google links), so blocking is keyed to these exact IDs, not to google hosts.
FORBIDDEN_IDS = {'1yLSR0PorJld59J9xG1jbzecNu1s0KlYLXdBx94ipp30',
                 '11QcbcYin-3GlyU2GYtXgij54KpRHYDuM'}
# vt-0001 labelled pipeline test (New posts tab) keeps its fixed identity.
TEST_ID = 'vt-0001'
TEST_FOLDER = '2026-11-22-pilot-test-post'
TEST_TITLE = 'Publishing test, not a real article'
TEST_SLUG = 'pilot-test-post'
TEST_DATE = '2026-11-22'
FOLDER_RE = re.compile(r'^\d{4}-\d{2}-\d{2}-[a-z0-9][a-z0-9-]*$')
DOC_RE = re.compile(r'/document/d/([A-Za-z0-9_-]+)')
MONTHS = ['January','February','March','April','May','June','July','August','September','October','November','December']

class Node:
    def __init__(self, tag='', attrs=None):
        self.tag = tag
        self.attrs = dict(attrs or [])
        self.children = []
    def text(self):
        return ''.join(c.text() if isinstance(c, Node) else c for c in self.children)
    def contains_image(self):
        return self.tag == 'img' or any(isinstance(c, Node) and c.contains_image() for c in self.children)

class Tree(HTMLParser):
    VOID = {'img', 'br', 'hr', 'meta', 'link', 'input', 'wbr', 'source'}
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node()
        self.stack = [self.root]
        self.body = None
    def handle_starttag(self, tag, attrs):
        n = Node(tag, attrs)
        self.stack[-1].children.append(n)
        if tag == 'body':
            self.body = n
        if tag not in self.VOID:
            self.stack.append(n)
    def handle_endtag(self, tag):
        for i in range(len(self.stack)-1, 0, -1):
            if self.stack[i].tag == tag:
                self.stack = self.stack[:i]
                break
    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)
    def handle_data(self, data):
        self.stack[-1].children.append(data)

class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlparse(newurl).hostname not in {'www.googleapis.com', 'sheets.googleapis.com'}:
            raise RuntimeError('Unexpected API redirect refused')
        return super().redirect_request(req, fp, code, msg, headers, newurl)

OPENER = urllib.request.build_opener(SafeRedirect())

def api(url, token):
    req = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + token})
    with OPENER.open(req, timeout=60) as response:
        data = response.read(20_000_001)
    if len(data) > 20_000_000:
        raise RuntimeError('Source exceeds size limit')
    return data

def output_publish(value):
    target = os.environ.get('GITHUB_OUTPUT')
    if target:
        with open(target, 'a') as f:
            f.write('publish=' + ('true' if value else 'false') + '\n')

def sanitize(source, title, folder, archive=True):
    tree = Tree()
    tree.feed(source)
    if tree.body is None:
        raise RuntimeError('Missing article body')
    parts = [c for c in tree.body.children if isinstance(c, Node)]
    norm = lambda s: ' '.join(s.split())
    if not parts or norm(parts[0].text()) != norm(title):
        raise RuntimeError('First article paragraph must match the spreadsheet title: ' + folder)
    if archive:
        if len(parts) < 3 or not parts[1].text().strip().startswith('Original post:'):
            raise RuntimeError('Article date header changed; manual review required: ' + folder)
        if parts[2].text().strip() != 'Original blog post':
            raise RuntimeError('Article source-link header changed; manual review required: ' + folder)
    for n in parts[:3] if archive else parts[:1]:
        tree.body.children.remove(n)
    images = []
    allowed = {'p', 'a', 'img', 'strong', 'em', 'b', 'i', 'u', 'br', 'ul', 'ol', 'li', 'h2', 'h3', 'h4', 'blockquote', 'hr'}
    forbidden = {'script', 'style', 'iframe', 'object', 'embed', 'form', 'input', 'button'}
    def render(n):
        if not isinstance(n, Node):
            return html.escape(n, quote=False)
        if n.tag in forbidden:
            return ''
        if n.tag == 'img':
            m = re.fullmatch(r'data:image/(png|jpeg|gif);base64,([A-Za-z0-9+/=\s]+)', n.attrs.get('src', ''))
            if not m:
                raise RuntimeError('Non-embedded image requires manual review: ' + folder)
            fmt, b64 = m.group(1), m.group(2)
            raw = base64.b64decode(b64, validate=False)
            magic = raw.startswith(b'\x89PNG\r\n\x1a\n') if fmt == 'png' else raw.startswith(b'\xff\xd8\xff') if fmt == 'jpeg' else raw.startswith(b'GIF8')
            if not magic or len(raw) > 8_000_000:
                raise RuntimeError('Invalid image payload: ' + folder)
            ext = 'jpg' if fmt == 'jpeg' else fmt
            name = 'image-' + str(len(images)+1) + '.' + ext
            images.append((name, raw))
            return '<img src="images/' + name + '" alt="' + ('Illustration ' + str(len(images)) + ' from the original post' if archive else 'Article illustration ' + str(len(images))) + '" loading="lazy"/>'
        inner = ''.join(render(c) for c in n.children)
        if n.tag == 'p' and not n.text().strip() and not n.contains_image():
            return ''
        if n.tag not in allowed:
            return inner
        if n.tag == 'a':
            href = n.attrs.get('href', '')
            if href.startswith('https://www.google.com/url?'):
                href = urllib.parse.parse_qs(urllib.parse.urlparse(href).query).get('q', [href])[0]
            parsed = urllib.parse.urlparse(href)
            if parsed.scheme not in {'http', 'https', 'mailto'}:
                return inner
            if any(fid in href for fid in FORBIDDEN_IDS):
                raise RuntimeError('Private source link requires manual review: ' + folder)
            return '<a href="' + html.escape(href, quote=True) + '">' + inner + '</a>'
        if n.tag == 'br':
            return '<br/>'
        if n.tag == 'hr':
            return '<hr/>'
        return '<' + n.tag + '>' + inner + '</' + n.tag + '>'
    body = ''.join(render(c) for c in tree.body.children)
    if any(fid in body for fid in FORBIDDEN_IDS) or 'data:image' in body:
        raise RuntimeError('Unsafe source reference refused: ' + folder)
    if len(body) > 1_000_000:
        raise RuntimeError('Article too large: ' + folder)
    return body, images

def drive_meta(file_id, token):
    url = 'https://www.googleapis.com/drive/v3/files/' + file_id + '?fields=name,parents,mimeType,trashed,version'
    return json.loads(api(url, token))

def validate_post_folder(cfg, token, doc_meta, folder_name):
    parents = doc_meta.get('parents', [])
    if len(parents) != 1:
        raise RuntimeError('Source is outside the approved folder: ' + folder_name)
    post_folder = json.loads(api('https://www.googleapis.com/drive/v3/files/' + parents[0] + '?fields=name,parents,mimeType,trashed', token))
    ancestors = post_folder.get('parents', [])
    if post_folder.get('trashed') or post_folder.get('name') != folder_name or post_folder.get('mimeType') != 'application/vnd.google-apps.folder' or len(ancestors) != 1:
        raise RuntimeError('Unexpected post folder; manual review required: ' + folder_name)
    posts_folder = json.loads(api('https://www.googleapis.com/drive/v3/files/' + ancestors[0] + '?fields=name,parents,mimeType,trashed', token))
    if posts_folder.get('trashed') or posts_folder.get('name') != 'Posts' or posts_folder.get('mimeType') != 'application/vnd.google-apps.folder' or cfg['folder_id'] not in posts_folder.get('parents', []):
        raise RuntimeError('Post folder is outside the approved publishing path: ' + folder_name)

def sheet_values(cfg, token, tab_range):
    ranges = urllib.parse.quote(tab_range, safe='')
    return json.loads(api('https://sheets.googleapis.com/v4/spreadsheets/' + cfg['spreadsheet_id'] + '/values/' + ranges, token)).get('values', [])

def display_date(date_iso):
    y, m, d = date_iso.split('-')
    return str(int(d)) + ' ' + MONTHS[int(m)-1] + ' ' + y

def editorial_text(value):
    text = ' '.join(str(value or '').split())
    if len(text) > 2000 or any(fid in text for fid in FORBIDDEN_IDS) or any(marker in text.lower() for marker in ('docs.google.com', 'drive.google.com', '<script')):
        raise RuntimeError('Unsafe editorial metadata; keep private source links out of public fields')
    return text

def import_archive_rows(cfg, token):
    global STAGE
    STAGE = 'redirects registry read'
    rows = sheet_values(cfg, token, 'Redirects!A1:P200')
    for row in rows[1:]:
        doc_cell = row[3] if len(row) > 3 else ''
        source_match = DOC_RE.search(doc_cell or '')
        if source_match:
            FORBIDDEN_IDS.add(source_match.group(1))
    imported = []
    seen_folders = set()
    for row in rows[1:]:
        row = list(row) + [''] * 16
        original_url, title, date_iso, doc_url, _new_url, status = row[0], row[1], row[2], row[3], row[4], row[5]
        tumblr_id, timestamp_utc = row[9], row[11]
        if status not in PUBLISH_GATES:
            continue
        if not (original_url and title and date_iso and tumblr_id):
            raise RuntimeError('Registry row missing identity fields; manual review required')
        slug = original_url.rstrip('/').rsplit('/', 1)[-1]
        folder = date_iso + '-' + slug
        if not FOLDER_RE.fullmatch(folder) or folder in seen_folders:
            raise RuntimeError('Unexpected or duplicate post folder: ' + folder)
        seen_folders.add(folder)
        source_match = DOC_RE.search(doc_url or '')
        if not source_match:
            raise RuntimeError('Source Doc missing for gated row: ' + folder)
        doc_id = source_match.group(1)
        STAGE = 'folder access validation: ' + folder
        meta = drive_meta(doc_id, token)
        if meta.get('trashed') or meta.get('mimeType') != 'application/vnd.google-apps.document':
            raise RuntimeError('Source is not an active document: ' + folder)
        validate_post_folder(cfg, token, meta, folder)
        version = str(meta.get('version', ''))
        STAGE = 'document export: ' + folder
        raw = api('https://www.googleapis.com/drive/v3/files/' + doc_id + '/export?mimeType=text%2Fhtml', token)
        STAGE = 'article sanitization: ' + folder
        body, images = sanitize(raw.decode('utf-8'), title, folder)
        export_dir = POSTS_ROOT / folder
        if export_dir.exists():
            shutil.rmtree(export_dir)
        (export_dir / 'images').mkdir(parents=True, exist_ok=True)
        for name, data in images:
            (export_dir / 'images' / name).write_bytes(data)
        post = dict(id=tumblr_id, slug=slug, title=title, date=date_iso, display_date=display_date(date_iso),
                    timestamp_utc=timestamp_utc, original_url=original_url, kind='archive',
                    html=body, images=[n for n, _ in images],
                    teaser=editorial_text(row[14]), seo_description=editorial_text(row[15]))
        (export_dir / 'post.json').write_text(json.dumps(post, ensure_ascii=False, indent=2))
        imported.append((folder, version, hashlib.sha256(raw).hexdigest()))
        print('IMPORTED: ' + folder + ' (' + str(len(images)) + ' images)')
    return imported

def validate_new_doc(cfg, token, meta):
    """Accept a renamed Doc anywhere beneath the existing publishing folder."""
    seen = set()
    current = meta
    for _ in range(12):
        parents = current.get('parents', [])
        if cfg['folder_id'] in parents:
            return
        if len(parents) != 1 or parents[0] in seen:
            break
        seen.add(parents[0])
        current = drive_meta(parents[0], token)
        if current.get('trashed') or current.get('mimeType') != 'application/vnd.google-apps.folder':
            break
    raise RuntimeError('New article Doc must be inside the publishing folder')

def import_new_rows(cfg, token):
    global STAGE
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo
    STAGE = 'new-post registry read'
    rows = sheet_values(cfg, token, "'New posts'!A1:N1000")
    for row in rows[1:]:
        m = DOC_RE.search(str(row[2]) if len(row) > 2 else '')
        if m:
            FORBIDDEN_IDS.add(m.group(1))
    imported = []
    seen_ids, seen_docs, seen_folders = set(), set(), set()
    now = datetime.now(timezone.utc)
    snapshots = [json.loads(p.read_text()) for p in POSTS_ROOT.glob('*/post.json')]
    for row in rows[1:]:
        row = list(row) + [''] * 14
        if not any(str(c).strip() for c in row):
            continue
        post_id, title, doc_url, tags, status, requested = [str(c).strip() for c in row[:6]]
        if status not in {'Publish', 'Published', 'Publish test'}:
            continue
        STAGE = 'new-post row validation'
        test = post_id == TEST_ID
        if status == 'Publish test' and not test:
            raise RuntimeError('Publish test is reserved for the labelled pipeline test')
        if not re.fullmatch(r'vt-[0-9]{4,}', post_id) or post_id in seen_ids:
            raise RuntimeError('New posts need unique Post IDs, such as vt-0002')
        seen_ids.add(post_id)
        m = DOC_RE.search(doc_url)
        if not m or m.group(1) in seen_docs or not title:
            raise RuntimeError('New posts need a title and a unique Google Doc link')
        doc_id = m.group(1)
        seen_docs.add(doc_id)
        if test:
            if title != TEST_TITLE or row[9] != 'Not eligible':
                raise RuntimeError('Labelled test identity or feed exclusion changed')
            date_iso, slug, timestamp = TEST_DATE, TEST_SLUG, ''
        else:
            slug = str(row[13]).strip()
            if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', slug):
                raise RuntimeError('URL slug is required: lowercase words separated by hyphens')
            try:
                when = datetime.fromisoformat(requested)
                if when.tzinfo is None:
                    when = when.replace(tzinfo=ZoneInfo('Europe/Amsterdam'))
            except ValueError:
                raise RuntimeError('Publish date required: YYYY-MM-DD or YYYY-MM-DD HH:MM in Europe/Amsterdam')
            date_iso = when.astimezone(ZoneInfo('Europe/Amsterdam')).date().isoformat()
            timestamp = when.astimezone(timezone.utc).isoformat()
            if when > now:
                print('SKIP: future-dated new post ' + post_id + '; run again when due.')
                continue
        folder = date_iso + '-' + slug
        if folder in seen_folders:
            raise RuntimeError('Duplicate new-post URL')
        seen_folders.add(folder)
        old = next((p for p in snapshots if p['id'] == post_id), None)
        if old and (old['date'] != date_iso or old['slug'] != slug):
            raise RuntimeError('Published date and slug are permanent; revert the changed URL fields')
        if any(p['id'] != post_id and p['date'] + '-' + p['slug'] == folder for p in snapshots):
            raise RuntimeError('New post URL collides with an existing article')
        existing = POSTS_ROOT / folder / 'post.json'
        if existing.exists() and json.loads(existing.read_text())['id'] != post_id:
            raise RuntimeError('New post URL collides with another imported article')
        STAGE = 'new-post access validation'
        meta = drive_meta(doc_id, token)
        if meta.get('trashed') or meta.get('mimeType') != 'application/vnd.google-apps.document':
            raise RuntimeError('New article source is not an active Google Doc')
        validate_new_doc(cfg, token, meta)
        STAGE = 'new-post export and sanitization'
        raw = api('https://www.googleapis.com/drive/v3/files/' + doc_id + '/export?mimeType=text%2Fhtml', token)
        body, images = sanitize(raw.decode('utf-8'), title, folder, archive=False)
        if not body.strip():
            raise RuntimeError('New article body is empty')
        eligibility = str(row[9]).strip()
        if eligibility not in {'RSS', 'Not eligible'}:
            raise RuntimeError('Choose RSS or Not eligible in the feed column; no email is sent')
        out = POSTS_ROOT / folder
        if out.exists():
            shutil.rmtree(out)
        (out / 'images').mkdir(parents=True, exist_ok=True)
        for name, data in images:
            (out / 'images' / name).write_bytes(data)
        post = dict(id=post_id, title=title, date=date_iso, slug=slug, display_date=display_date(date_iso),
                    timestamp_utc=timestamp, original_url=None, kind='new-test' if test else 'new',
                    html=body, images=[n for n, _ in images], teaser=editorial_text(row[11]),
                    seo_description=editorial_text(row[12]), rss_eligible=not test and eligibility == 'RSS')
        (out / 'post.json').write_text(json.dumps(post, ensure_ascii=False, indent=2))
        imported.append((folder, str(meta.get('version', '')), hashlib.sha256(raw).hexdigest()))
        print('IMPORTED: new-post ' + post_id + (' (labelled test, excluded)' if test else ''))
    return imported

def import_site_config(cfg, token):
    global STAGE
    STAGE = 'site config read'
    rows = sheet_values(cfg, token, 'Site!A1:C30')
    config = {}
    for row in rows[1:]:
        row = list(row) + ['', '']
        key, value = row[0].strip(), row[1].strip()
        if not key:
            continue
        if key.startswith('nav_') and key.endswith('_url'):
            parsed = urllib.parse.urlparse(value)
            if parsed.scheme != 'https' or not parsed.hostname or parsed.hostname.endswith('google.com'):
                raise RuntimeError('Unsafe navigation URL in Site tab: ' + key)
        if key in {'site_title', 'tagline', 'rss_enabled', 'preview_banner'} or key.startswith('nav_'):
            if any(b in value.lower() for b in ['<script', 'docs.google.com', 'drive.google.com']):
                raise RuntimeError('Unsafe value in Site tab: ' + key)
            config[key] = value
    (ROOT / 'content').mkdir(exist_ok=True)
    (ROOT / 'content' / 'site.json').write_text(json.dumps(config, ensure_ascii=False, indent=2))
    print('SITE CONFIG: ' + str(len(config)) + ' keys imported.')
    return config

def main():
    global STAGE
    cfg = json.loads(os.environ['BLOG_SOURCE_CONFIG'])
    token = os.environ['GOOGLE_ACCESS_TOKEN']
    for key in ('spreadsheet_id', 'folder_id'):
        if not re.fullmatch(r'[A-Za-z0-9_-]+', cfg[key]):
            raise RuntimeError('Invalid private source configuration')
    STAGE = 'folder access validation'
    meta = drive_meta(cfg['spreadsheet_id'], token)
    if meta.get('trashed') or meta.get('mimeType') != 'application/vnd.google-apps.spreadsheet' or cfg['folder_id'] not in meta.get('parents', []):
        raise RuntimeError('Registry spreadsheet is outside the approved folder')
    imported = import_archive_rows(cfg, token)
    new_imports = import_new_rows(cfg, token)
    import_site_config(cfg, token)
    proof = {'source_mode': 'private-google-readonly',
             'imported_at_utc': __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
             'posts': {f: {'source_version': v, 'source_sha256': h} for f, v, h in imported + new_imports},
             'new_posts_imported': len(new_imports)}
    (ROOT / 'source-proof.json').write_text(json.dumps(proof, indent=2))
    print('PASS: ' + str(len(imported)) + ' gated archive post(s) imported. No source IDs exported.')
    output_publish(bool(imported) or bool(new_imports))

if __name__ == '__main__':
    try:
        main()
    except urllib.error.HTTPError as exc:
        print('ERROR: ' + STAGE + ', Google API HTTP ' + str(exc.code) + '. No deployment.', file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        detail = str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__
        print('ERROR: ' + STAGE + ': ' + detail + '. No deployment.', file=sys.stderr)
        sys.exit(1)
