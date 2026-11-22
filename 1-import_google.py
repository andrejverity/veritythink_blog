"""Read the approved Ring pilot and the gated vt-0001 test post from private Google sources.

No source identifiers or OAuth tokens are printed or placed in the site.
Only the already-approved archival article and the explicitly gated labelled
test post can be built by this pilot.
"""
import base64
import hashlib
import html
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent
POST_ID = '64003052404'
POST_FOLDER = '2013-10-14-the-humanitarian-ring'
EXPORT = ROOT / 'content' / 'posts' / POST_FOLDER
ORIGINAL = 'https://blog.veritythink.com/post/64003052404/the-humanitarian-ring'
TEST_ID = 'vt-0001'
TEST_FOLDER = '2026-11-22-pilot-test-post'
TEST_EXPORT = ROOT / 'content' / 'posts' / TEST_FOLDER
TEST_TITLE = 'Publishing test, not a real article'
TEST_SLUG = 'pilot-test-post'
TEST_DATE = '2026-11-22'
STAGE = 'configuration'

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
    with OPENER.open(req, timeout=45) as response:
        data = response.read(10_000_001)
    if len(data) > 10_000_000:
        raise RuntimeError('Source exceeds pilot size limit')
    return data

def output_publish(value):
    target = os.environ.get('GITHUB_OUTPUT')
    if target:
        with open(target, 'a') as f:
            f.write('publish=' + ('true' if value else 'false') + '\n')

def ring_headers(parts):
    if len(parts) < 4 or parts[0].text().strip() != 'The Humanitarian Ring':
        raise RuntimeError('Pilot header changed; manual review required')
    if not parts[1].text().startswith('Original post: 14 Oct 2013') or parts[2].text().strip() != 'Original blog post':
        raise RuntimeError('Pilot metadata boundary changed; manual review required')
    return 3

def test_headers(parts):
    if len(parts) < 2 or parts[0].text().strip() != TEST_TITLE:
        raise RuntimeError('Test-post title changed; manual review required')
    return 1

def sanitize(source, check_headers, image_prefix, expected_images):
    tree = Tree()
    tree.feed(source)
    if tree.body is None:
        raise RuntimeError('Missing article body')
    parts = [c for c in tree.body.children if isinstance(c, Node)]
    stripped = check_headers(parts)
    for n in parts[:stripped]:
        tree.body.children.remove(n)
    images = []
    allowed = {'p', 'a', 'img', 'strong', 'em', 'b', 'i', 'br', 'ul', 'ol', 'li', 'h2', 'h3', 'blockquote'}
    forbidden = {'script', 'style', 'iframe', 'object', 'embed', 'form', 'input', 'button'}
    def render(n):
        if not isinstance(n, Node):
            return html.escape(n, quote=False)
        if n.tag in forbidden:
            return ''
        if n.tag == 'img':
            m = re.fullmatch(r'data:image/png;base64,([A-Za-z0-9+/=\s]+)', n.attrs.get('src', ''))
            if not m:
                raise RuntimeError('Non-embedded PNG image requires manual review')
            raw = base64.b64decode(m.group(1), validate=False)
            if not raw.startswith(b'\x89PNG\r\n\x1a\n') or len(raw) > 5_000_000:
                raise RuntimeError('Invalid pilot image')
            name = image_prefix + str(len(images)+1) + '.png'
            images.append((name, raw))
            return ' '
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
            if parsed.hostname and (parsed.hostname.endswith('google.com') or parsed.hostname.endswith('googleusercontent.com')):
                raise RuntimeError('Private Google link requires manual review')
            return ' ' + inner + ' '
        if n.tag == 'br':
            return ' '
        return '<' + n.tag + '>' + inner + '</' + n.tag + '>'
    body = ''.join(render(c) for c in tree.body.children)
    if len(images) != expected_images:
        raise RuntimeError('Unexpected pilot image count; manual review required')
    if 'docs.google.com' in body or 'data:image' in body:
        raise RuntimeError('Unsafe source reference refused')
    return body, images

def validate_post_folder(cfg, token, doc_meta, folder_name):
    parents = doc_meta.get('parents', [])
    if len(parents) != 1:
        raise RuntimeError('Source is outside the approved folder')
    post_folder = json.loads(api('https://www.googleapis.com/drive/v3/files/' + parents[0] + '?fields=name,parents,mimeType,trashed', token))
    ancestors = post_folder.get('parents', [])
    if post_folder.get('trashed') or post_folder.get('name') != folder_name or post_folder.get('mimeType') != 'application/vnd.google-apps.folder' or len(ancestors) != 1:
        raise RuntimeError('Unexpected post folder; manual review required')
    posts_folder = json.loads(api('https://www.googleapis.com/drive/v3/files/' + ancestors[0] + '?fields=name,parents,mimeType,trashed', token))
    if posts_folder.get('trashed') or posts_folder.get('name') != 'Posts' or posts_folder.get('mimeType') != 'application/vnd.google-apps.folder' or cfg['folder_id'] not in posts_folder.get('parents', []):
        raise RuntimeError('Post folder is outside the approved publishing path')

def main():
    global STAGE
    cfg = json.loads(os.environ['BLOG_SOURCE_CONFIG'])
    token = os.environ['GOOGLE_ACCESS_TOKEN']
    for key in ('spreadsheet_id', 'folder_id', 'document_id'):
        if not re.fullmatch(r'[A-Za-z0-9_-]+', cfg[key]):
            raise RuntimeError('Invalid private source configuration')
    STAGE = 'folder access validation'
    version = None
    for key, expected_type in [('spreadsheet_id', 'application/vnd.google-apps.spreadsheet'), ('document_id', 'application/vnd.google-apps.document')]:
        url = 'https://www.googleapis.com/drive/v3/files/' + cfg[key] + '?fields=parents,mimeType,trashed,version'
        meta = json.loads(api(url, token))
        if meta.get('trashed') or meta.get('mimeType') != expected_type:
            raise RuntimeError('Source is not an active file inside the approved folder')
        parents = meta.get('parents', [])
        if cfg['folder_id'] not in parents:
            if key != 'document_id':
                raise RuntimeError('Source is outside the approved folder')
            validate_post_folder(cfg, token, meta, POST_FOLDER)
        if key == 'document_id':
            version = str(meta.get('version', ''))
    STAGE = 'spreadsheet read'
    ranges = urllib.parse.quote('Redirects!A1:N200', safe='')
    rows = json.loads(api('https://sheets.googleapis.com/v4/spreadsheets/' + cfg['spreadsheet_id'] + '/values/' + ranges, token)).get('values', [])
    matches = [r for r in rows[1:] if len(r) > 9 and str(r[9]) == POST_ID]
    if len(matches) != 1:
        raise RuntimeError('Expected exactly one approved archival row')
    row = matches[0]
    ring_publish = row[5] == 'Publish test'
    if ring_publish:
        source_match = re.search(r'/document/d/([A-Za-z0-9_-]+)', row[3])
        if row[0] != ORIGINAL or row[2] != '2013-10-14' or not source_match or source_match.group(1) != cfg['document_id']:
            raise RuntimeError('Archival identity, date or source changed; manual review required')
        STAGE = 'document export'
        raw = api('https://www.googleapis.com/drive/v3/files/' + cfg['document_id'] + '/export?mimeType=text%2Fhtml', token)
        STAGE = 'article sanitization'
        body, images = sanitize(raw.decode('utf-8'), ring_headers, 'ring-', 2)
        (EXPORT / 'images').mkdir(parents=True, exist_ok=True)
        for name, data in images:
            (EXPORT / 'images' / name).write_bytes(data)
            (ROOT / name).write_bytes(data) # Ephemeral compatibility input, never committed
        post = dict(id=POST_ID, slug='the-humanitarian-ring', title='The Humanitarian Ring', date='2013-10-14', original_url=ORIGINAL, kind='legacy-test', html=body, images=[n for n, _ in images])
        (EXPORT / 'post.json').write_text(json.dumps(post, ensure_ascii=False, indent=2))
        (ROOT / 'ring.json').write_text(json.dumps(post, ensure_ascii=False, indent=2)) # Ephemeral compatibility input
        proof = {'source_mode': 'private-google-readonly', 'source_version': version, 'source_sha256': hashlib.sha256(raw).hexdigest(), 'imported_at_utc': __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()}
        (ROOT / 'source-proof.json').write_text(json.dumps(proof))
        print('PASS: private Sheet and Doc read with short-lived credentials; one approved archival article and two embedded images imported. No source IDs exported.')
    else:
        print('PAUSED: the archival row is not set to Publish test. Existing preview remains unchanged.')
    STAGE = 'new-post registry read'
    test_publish = import_test_post(cfg, token)
    output_publish(ring_publish or test_publish)

def import_test_post(cfg, token):
    global STAGE
    ranges = urllib.parse.quote("'New posts'!A1:K50", safe='')
    rows = json.loads(api('https://sheets.googleapis.com/v4/spreadsheets/' + cfg['spreadsheet_id'] + '/values/' + ranges, token)).get('values', [])
    matches = [r for r in rows[1:] if len(r) > 0 and str(r[0]) == TEST_ID]
    if len(matches) != 1:
        raise RuntimeError('Expected exactly one vt-0001 registry row')
    row = list(matches[0]) + [''] * 11
    if row[9] != 'Not eligible':
        raise RuntimeError('Test post RSS/email eligibility changed; manual review required')
    if row[4] != 'Publish test':
        print('SKIP: the vt-0001 test post is not set to Publish test. Existing preview remains unchanged.')
        return False
    if row[1].strip() != TEST_TITLE:
        raise RuntimeError('Test post registry title changed; manual review required')
    source_match = re.search(r'/document/d/([A-Za-z0-9_-]+)', row[2])
    if not source_match:
        raise RuntimeError('Test post source Doc missing; manual review required')
    doc_id = source_match.group(1)
    STAGE = 'test post folder access validation'
    url = 'https://www.googleapis.com/drive/v3/files/' + doc_id + '?fields=parents,mimeType,trashed,version'
    meta = json.loads(api(url, token))
    if meta.get('trashed') or meta.get('mimeType') != 'application/vnd.google-apps.document':
        raise RuntimeError('Test source is not an active document inside the approved folder')
    validate_post_folder(cfg, token, meta, TEST_FOLDER)
    version = str(meta.get('version', ''))
    STAGE = 'test document export'
    raw = api('https://www.googleapis.com/drive/v3/files/' + doc_id + '/export?mimeType=text%2Fhtml', token)
    STAGE = 'test article sanitization'
    body, images = sanitize(raw.decode('utf-8'), test_headers, 'test-', 0)
    post = dict(id=TEST_ID, slug=TEST_SLUG, title=TEST_TITLE, date=TEST_DATE, original_url=None, kind='new-test', html=body, images=[])
    TEST_EXPORT.mkdir(parents=True, exist_ok=True)
    (TEST_EXPORT / 'post.json').write_text(json.dumps(post, ensure_ascii=False, indent=2))
    proof = {'test_post': {'source_mode': 'private-google-readonly', 'source_version': version, 'source_sha256': hashlib.sha256(raw).hexdigest(), 'imported_at_utc': __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()}}
    proof_path = ROOT / 'source-proof.json'
    if proof_path.exists():
        existing = json.loads(proof_path.read_text())
        existing.update(proof)
        proof_path.write_text(json.dumps(existing))
    print('PASS: gated vt-0001 labelled test post imported. No source IDs exported.')
    return True

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
