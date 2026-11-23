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

def sanitize(source, title, folder):
    tree = Tree()
    tree.feed(source)
    if tree.body is None:
        raise RuntimeError('Missing article body')
    parts = [c for c in tree.body.children if isinstance(c, Node)]
    if len(parts) < 3 or parts[0].text().strip() != title:
        raise RuntimeError('Article title header changed; manual review required: ' + folder)
    if not parts[1].text().strip().startswith('Original post:'):
        raise RuntimeError('Article date header changed; manual review required: ' + folder)
    if parts[2].text().strip() != 'Original blog post':
        raise RuntimeError('Article source-link header changed; manual review required: ' + folder)
    for n in parts[:3]:
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
            return '<img src="images/' + name + '" alt="Illustration ' + str(len(images)) + ' from the original post" loading="lazy"/>'
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
            if parsed.hostname and (parsed.hostname.endswith('google.com') or parsed.hostname.endswith('googleusercontent.com') or parsed.hostname.endswith('drive.google.com') or parsed.hostname.endswith('docs.google.com')):
                raise RuntimeError('Private Google link requires manual review: ' + folder)
            return '<a href="' + html.escape(href, quote=True) + '">' + inner + '</a>'
        if n.tag == 'br':
            return '<br/>'
        if n.tag == 'hr':
            return '<hr/>'
        return '<' + n.tag + '>' + inner + '</' + n.tag + '>'
    body = ''.join(render(c) for c in tree.body.children)
    if 'docs.google.com' in body or 'drive.google.com' in body or 'data:image' in body:
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

def import_archive_rows(cfg, token):
    global STAGE
    STAGE = 'redirects registry read'
    rows = sheet_values(cfg, token, 'Redirects!A1:N200')
    imported = []
    seen_folders = set()
    for row in rows[1:]:
        row = list(row) + [''] * 14
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
                    html=body, images=[n for n, _ in images])
        (export_dir / 'post.json').write_text(json.dumps(post, ensure_ascii=False, indent=2))
        imported.append((folder, version, hashlib.sha256(raw).hexdigest()))
        print('IMPORTED: ' + folder + ' (' + str(len(images)) + ' images)')
    return imported

def import_test_post(cfg, token):
    global STAGE
    STAGE = 'new-post registry read'
    rows = sheet_values(cfg, token, "'New posts'!A1:K50")
    matches = [r for r in rows[1:] if len(r) > 0 and str(r[0]) == TEST_ID]
    if len(matches) != 1:
        raise RuntimeError('Expected exactly one vt-0001 registry row')
    row = list(matches[0]) + [''] * 11
    if row[9] != 'Not eligible':
        raise RuntimeError('Test post RSS/email eligibility changed; manual review required')
    if row[4] != 'Publish test':
        print('SKIP: vt-0001 is not set to Publish test.')
        return False
    if row[1].strip() != TEST_TITLE:
        raise RuntimeError('Test post registry title changed; manual review required')
    source_match = DOC_RE.search(row[2])
    if not source_match:
        raise RuntimeError('Test post source Doc missing; manual review required')
    doc_id = source_match.group(1)
    STAGE = 'test post folder access validation'
    meta = drive_meta(doc_id, token)
    if meta.get('trashed') or meta.get('mimeType') != 'application/vnd.google-apps.document':
        raise RuntimeError('Test source is not an active document inside the approved folder')
    validate_post_folder(cfg, token, meta, TEST_FOLDER)
    STAGE = 'test document export'
    raw = api('https://www.googleapis.com/drive/v3/files/' + doc_id + '/export?mimeType=text%2Fhtml', token)
    STAGE = 'test article sanitization'
    body, images = sanitize_test(raw.decode('utf-8'))
    export_dir = POSTS_ROOT / TEST_FOLDER
    if export_dir.exists():
        shutil.rmtree(export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)
    post = dict(id=TEST_ID, slug=TEST_SLUG, title=TEST_TITLE, date=TEST_DATE, display_date=display_date(TEST_DATE),
                timestamp_utc='', original_url=None, kind='new-test', html=body, images=[])
    (export_dir / 'post.json').write_text(json.dumps(post, ensure_ascii=False, indent=2))
    print('IMPORTED: gated vt-0001 labelled test post (excluded from index, navigation and feed).')
    return True

def sanitize_test(source):
    tree = Tree()
    tree.feed(source)
    if tree.body is None:
        raise RuntimeError('Missing test article body')
    parts = [c for c in tree.body.children if isinstance(c, Node)]
    if len(parts) < 1 or parts[0].text().strip() != TEST_TITLE:
        raise RuntimeError('Test-post title changed; manual review required')
    tree.body.children.remove(parts[0])
    images = []
    allowed = {'p', 'a', 'strong', 'em', 'b', 'i', 'br', 'ul', 'ol', 'li', 'h2', 'h3', 'blockquote'}
    def render(n):
        if not isinstance(n, Node):
            return html.escape(n, quote=False)
        if n.tag in {'script', 'style', 'iframe', 'object', 'embed', 'form', 'input', 'button', 'img'}:
            return ''
        inner = ''.join(render(c) for c in n.children)
        if n.tag == 'p' and not n.text().strip():
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
            return '<a href="' + html.escape(href, quote=True) + '">' + inner + '</a>'
        if n.tag == 'br':
            return '<br/>'
        return '<' + n.tag + '>' + inner + '</' + n.tag + '>'
    return ''.join(render(c) for c in tree.body.children), images

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
    test_ok = import_test_post(cfg, token)
    import_site_config(cfg, token)
    proof = {'source_mode': 'private-google-readonly',
             'imported_at_utc': __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
             'posts': {f: {'source_version': v, 'source_sha256': h} for f, v, h in imported},
             'test_post_imported': test_ok}
    (ROOT / 'source-proof.json').write_text(json.dumps(proof, indent=2))
    print('PASS: ' + str(len(imported)) + ' gated archive post(s) imported. No source IDs exported.')
    output_publish(bool(imported) or test_ok)

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
