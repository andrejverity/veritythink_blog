"""Build the VerityThink blog preview site. Standard library only.

Input: sanitized snapshots under content/posts/<folder>/ (exported from the
authoring Google Docs) plus content/site.json (Site tab of the Sheet).
This build does not fetch private Google data or deploy Pages itself.

URL model:
- Canonical post pages: /post/<YYYY-MM-DD-slug>/
- Legacy Tumblr paths /post/<id>/ and /post/<id>/<slug>/ serve redirect stubs
  (browser redirects; server 301s are not possible on GitHub Pages).
- The labelled pipeline test post keeps its pilot URL and stays out of the
  index, post navigation and RSS.
"""
import email.utils
import hashlib
import html
import json
from datetime import datetime, timezone
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
OUT = ROOT / '_site'
POSTS_ROOT = ROOT / 'content' / 'posts'

# Public URL configuration. At live cutover these become
# BASE = '' and SITE_URL = 'https://blog.veritythink.com'.
BASE = '/veritythink_blog'
SITE_URL = 'https://andrejverity.github.io'

BLOCKED = ['docs.google.com', 'drive.google.com', 'googleusercontent.com', 'data:image', '<script', '<iframe', '<form']

CSS = '''
:root{--ink:#22211e;--paper:#ffffff;--red:#a72b31;--line:#d8d2c6;--grey:#6b675e}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink)}
a{color:var(--red);text-underline-offset:3px}a:hover{color:#6b151b}
.wrap{max-width:1120px;margin:auto;padding:0 28px}
.banner{font:12px/1.5 system-ui,sans-serif;background:var(--red);color:#fff;text-align:center;padding:9px 18px;letter-spacing:.07em;text-transform:uppercase}
.banner a{color:#fff;text-decoration:underline}
.topbar{display:flex;justify-content:space-between;align-items:center;padding:14px 0 0;font:11px system-ui,sans-serif;letter-spacing:.14em;text-transform:uppercase}
.topbar .feed{color:var(--grey);text-decoration:none}.topbar .feed:hover{color:var(--red)}
.topbar nav a{color:var(--ink);text-decoration:none;margin-left:22px}.topbar nav a:hover{color:var(--red)}
.masthead{padding:30px 0 18px;border-bottom:4px double var(--ink);text-align:center}
.name{font:bold clamp(42px,8vw,76px)/1 Georgia,serif;letter-spacing:-.06em;color:var(--ink);text-decoration:none}
.tagline{font:11px/1.5 system-ui,sans-serif;letter-spacing:.22em;text-transform:uppercase;margin:14px 0 0;color:var(--grey)}
.edition{display:flex;justify-content:space-between;border-bottom:1px solid var(--line);padding:11px 0;font:10px system-ui,sans-serif;letter-spacing:.12em;text-transform:uppercase;color:var(--grey)}
article{max-width:750px;margin:50px auto 60px}
.kicker{font:11px system-ui,sans-serif;color:var(--red);text-transform:uppercase;letter-spacing:.16em}
h1{font:normal clamp(36px,6vw,56px)/1.08 Georgia,serif;letter-spacing:-.03em;margin:15px 0 20px}
.byline{border-top:1px solid var(--line);border-bottom:1px solid var(--line);padding:12px 0;margin:25px 0 32px;font:12px system-ui,sans-serif;color:var(--grey);letter-spacing:.04em}
.body{font:19px/1.75 Georgia,serif}.body p{margin:0 0 24px}.body>p:first-child{font-size:23px;line-height:1.6}
.body img{display:block;max-width:100%;height:auto;margin:32px auto;background:#fff}
.body blockquote{margin:28px 0;padding:4px 0 4px 22px;border-left:3px solid var(--red);font-style:italic;color:#3a382f}
.body blockquote p{margin:0 0 12px}.body ul,.body ol{margin:0 0 24px;padding-left:26px}.body li{margin:0 0 8px}
.body h2{font:normal 30px/1.2 Georgia,serif;margin:36px 0 14px}.body h3{font:normal 24px/1.25 Georgia,serif;margin:30px 0 12px}
.body h4{font:bold 19px/1.3 Georgia,serif;margin:26px 0 10px}.body hr{border:0;border-top:1px solid var(--line);margin:32px 0}
.note{border-left:3px solid var(--red);padding:10px 18px;font:13px/1.6 system-ui,sans-serif;background:#f6f4ef;margin-top:42px}
.postnav{display:flex;justify-content:space-between;gap:18px;border-top:4px double var(--ink);border-bottom:1px solid var(--line);padding:16px 0;margin-top:46px;font:13px/1.5 system-ui,sans-serif}
.postnav a{text-decoration:none;color:var(--ink);max-width:46%}.postnav a:hover{color:var(--red)}
.postnav .dir{display:block;font:10px;letter-spacing:.14em;text-transform:uppercase;color:var(--grey);margin-bottom:4px}
.postnav .next{text-align:right;margin-left:auto}
footer{border-top:1px solid var(--line);padding:22px 0 40px;display:flex;justify-content:space-between;gap:20px;font:11px/1.7 system-ui,sans-serif;color:var(--grey)}
footer a{color:var(--grey)}footer a:hover{color:var(--red)}
@media(max-width:600px){.wrap{padding:0 20px}.topbar nav a{margin-left:14px}.masthead{padding-top:24px}.tagline{letter-spacing:.11em}
article{margin-top:34px}.body{font-size:18px}.body>p:first-child{font-size:21px}footer{display:block}.postnav{flex-direction:column}.postnav a{max-width:100%}.postnav .next{text-align:left}}
'''

LIST_CSS = '''.list{max-width:750px;margin:44px auto 60px}.list a{text-decoration:none;color:var(--ink)}
.list a:hover h2{color:var(--red)}.list h2{font:normal clamp(24px,4vw,34px)/1.18 Georgia,serif;letter-spacing:-.02em;margin:6px 0 8px}
.list .when{font:11px system-ui,sans-serif;color:var(--grey);letter-spacing:.1em;text-transform:uppercase}
.list .entry{border-bottom:1px solid var(--line);padding:24px 0}
.count{font:11px system-ui,sans-serif;color:var(--grey);letter-spacing:.14em;text-transform:uppercase;border-bottom:1px solid var(--line);padding-bottom:14px}'''

def esc(s):
    return html.escape(str(s), quote=True)

def load_config():
    cfg_path = ROOT / 'content' / 'site.json'
    cfg = {}
    if cfg_path.exists():
        cfg = json.loads(cfg_path.read_text())
    return {
        'site_title': cfg.get('site_title') or 'verity•think',
        'tagline': cfg.get('tagline') or 'Humanitarian ideas. Technology. Possibility.',
        'rss_enabled': (cfg.get('rss_enabled') or 'yes').lower() == 'yes',
        'preview_banner': cfg.get('preview_banner') or 'Preview of the migrated blog. Not the live blog.',
        'nav': sorted([(k[:-6], cfg[k]) for k in cfg if k.startswith('nav_') and k.endswith('_label') and cfg.get(k[:-6] + '_url')],
                      key=lambda x: x[0]),
    }

def load_posts():
    posts = []
    for folder in sorted(p for p in POSTS_ROOT.iterdir() if p.is_dir()):
        post = json.loads((folder / 'post.json').read_text())
        assert set(post) == {'id', 'slug', 'title', 'date', 'display_date', 'timestamp_utc', 'original_url', 'kind', 'html', 'images'}, folder.name
        assert post['date'] + '-' + post['slug'] == folder.name, folder.name + ': folder must stay date-first and match slug'
        low = post['html'].lower()
        for b in BLOCKED:
            assert b not in low, folder.name + ': blocked content ' + b
        assert post['html'].count('<img ') == len(post['images']), folder.name + ': image count'
        for name in post['images']:
            assert (folder / 'images' / name).is_file(), folder.name + ': missing ' + name
        posts.append((folder.name, post))
    if not posts:
        raise SystemExit('No approved post snapshot present')
    return posts

def page_head(title, cfg, extra_css=''):
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<meta name="robots" content="noindex,nofollow">'
            '<link rel="alternate" type="application/rss+xml" title="' + esc(cfg['site_title']) + '" href="' + BASE + '/feed.xml">'
            '<title>' + esc(title) + '</title><style>' + CSS + extra_css + '</style></head><body>')

def chrome_top(cfg, edition_left='', edition_right=''):
    nav = ''.join('<a href="' + esc(u) + '">' + esc(l) + '</a>' for l, u in nav_items(cfg))
    out = '<div class="banner">' + esc(cfg['preview_banner']) + '</div><div class="wrap">'
    out += '<div class="topbar"><a class="feed" href="' + BASE + '/feed.xml">RSS</a><nav>' + nav + '</nav></div>'
    out += ('<header class="masthead"><a class="name" href="' + BASE + '/">' + esc(cfg['site_title']) + '</a>'
            '<p class="tagline">' + esc(cfg['tagline']) + '</p></header>')
    if edition_left or edition_right:
        out += '<div class="edition"><span>' + esc(edition_left) + '</span><span>' + esc(edition_right) + '</span></div>'
    return out

def nav_items(cfg):
    # cfg['nav'] holds (label_key, label); resolve URLs from the raw site.json
    raw = json.loads((ROOT / 'content' / 'site.json').read_text()) if (ROOT / 'content' / 'site.json').exists() else {}
    items = []
    for key, label in cfg['nav']:
        url = raw.get(key + '_url')
        if url:
            items.append((label, url))
    if not items:
        items = [('veritythink.com', 'https://veritythink.com/')]
    return items

def chrome_foot(cfg):
    nav = ' &nbsp;·&nbsp; '.join('<a href="' + esc(u) + '">' + esc(l) + '</a>' for l, u in nav_items(cfg))
    return ('<footer><span>' + esc(cfg['site_title']) + ' / An independent space for ideas.</span>'
            '<span>' + nav + ' &nbsp;·&nbsp; <a href="' + BASE + '/feed.xml">RSS feed</a></span></footer></div></body></html>')

def canonical(post):
    return BASE + '/post/' + post['date'] + '-' + post['slug'] + '/'

def render_article(post, prev_post, next_post, cfg):
    if post['kind'] == 'new-test':
        kicker = 'Pipeline test'
        note = ('Pipeline test: this is a labelled test post, not a real article. It stays out of the index, '
                'post navigation and RSS, and no email distribution is active.')
        edition_left = 'Pipeline test / No. ' + post['id']
    else:
        kicker = 'From the archive'
        note = ('Migrated from the Tumblr archive. Original wording, links, date and images retained. '
                '<a href="' + esc(post['original_url']) + '">Read the original post</a>.')
        edition_left = 'The archive / No. ' + post['id']
    nav = ''
    if prev_post:
        nav += '<a href="' + canonical(prev_post) + '"><span class="dir">&larr; Newer</span>' + esc(prev_post['title']) + '</a>'
    else:
        nav += '<span></span>'
    if next_post:
        nav += '<a class="next" href="' + canonical(next_post) + '"><span class="dir">Older &rarr;</span>' + esc(next_post['title']) + '</a>'
    body = (chrome_top(cfg, edition_left, 'Original edition · ' + post['display_date'])
            + '<main><article><div class="kicker">' + kicker + '</div><h1>' + esc(post['title']) + '</h1>'
            + '<div class="byline">Andrej Verity &nbsp; / &nbsp; <time datetime="' + post['date'] + '">' + esc(post['display_date']) + '</time></div>'
            + '<div class="body">' + post['html'] + '</div>'
            + '<aside class="note">' + note + '</aside>'
            + '<nav class="postnav">' + nav + '</nav></article></main>'
            + chrome_foot(cfg))
    return page_head(post['title'] + ' | ' + cfg['site_title'], cfg) + body

def render_index(archive_posts, cfg):
    entries = ''
    for post in archive_posts:
        entries += ('<div class="entry"><div class="when">' + esc(post['display_date']) + '</div>'
                    '<a href="' + canonical(post) + '"><h2>' + esc(post['title']) + '</h2></a></div>\n')
    years = str(archive_posts[-1]['date'][:4]) + '–' + str(archive_posts[0]['date'][:4]) if archive_posts else ''
    body = (chrome_top(cfg)
            + '<main><div class="list"><div class="count">' + str(len(archive_posts)) + ' posts from the archive · ' + years + '</div>'
            + entries + '</div></main>' + chrome_foot(cfg))
    return page_head(cfg['site_title'], cfg, LIST_CSS) + body

def render_redirect(post):
    target = canonical(post)
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="robots" content="noindex,nofollow">'
            '<link rel="canonical" href="' + SITE_URL + target + '">'
            '<meta http-equiv="refresh" content="0; url=' + esc(target) + '">'
            '<title>' + esc(post['title']) + '</title></head><body>'
            '<p>This post moved to <a href="' + esc(target) + '">' + esc(post['title']) + '</a>.</p>'
            '</body></html>')

def rfc2822(post):
    ts = post.get('timestamp_utc') or ''
    try:
        dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
    except ValueError:
        dt = datetime.fromisoformat(post['date'] + 'T00:00:00+00:00')
    return email.utils.format_datetime(dt)

def render_feed(archive_posts, cfg):
    base_abs = SITE_URL
    items = ''
    for post in archive_posts:
        content = post['html'].replace('src="images/', 'src="' + SITE_URL + canonical(post) + 'images/')
        content = content.replace(']]>', ']]&gt;')
        items += ('<item><title>' + esc(post['title']) + '</title>'
                  '<link>' + base_abs + canonical(post) + '</link>'
                  '<guid isPermaLink="true">' + esc(post['original_url']) + '</guid>'
                  '<pubDate>' + rfc2822(post) + '</pubDate>'
                  '<content:encoded><![CDATA[' + content + ']]></content:encoded></item>\n')
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">'
            '<channel><title>' + esc(cfg['site_title']) + '</title>'
            '<link>' + SITE_URL + BASE + '/</link>'
            '<description>' + esc(cfg['tagline']) + '</description>'
            '<language>en</language>\n' + items + '</channel></rss>\n')

def build():
    if OUT.exists():
        shutil.rmtree(OUT)
    cfg = load_config()
    posts = load_posts()
    archive = [p for _, p in posts if p['kind'] != 'new-test']
    test = [p for _, p in posts if p['kind'] == 'new-test']
    archive.sort(key=lambda p: (p['date'], p['id']), reverse=True)
    for i, post in enumerate(archive):
        prev_post = archive[i-1] if i > 0 else None
        next_post = archive[i+1] if i < len(archive)-1 else None
        article_dir = OUT / 'post' / (post['date'] + '-' + post['slug'])
        (article_dir / 'images').mkdir(parents=True)
        for name in post['images']:
            shutil.copyfile(POSTS_ROOT / (post['date'] + '-' + post['slug']) / 'images' / name, article_dir / 'images' / name)
        (article_dir / 'index.html').write_text(render_article(post, prev_post, next_post, cfg))
        for stub in (OUT / 'post' / post['id'], OUT / 'post' / post['id'] / post['slug']):
            stub.mkdir(parents=True, exist_ok=True)
            (stub / 'index.html').write_text(render_redirect(post))
    for post in test:
        article_dir = OUT / 'post' / post['id'] / post['slug']
        article_dir.mkdir(parents=True, exist_ok=True)
        (article_dir / 'index.html').write_text(render_article(post, None, None, cfg))
    (OUT / 'index.html').write_text(render_index(archive, cfg))
    if cfg['rss_enabled']:
        (OUT / 'feed.xml').write_text(render_feed(archive, cfg))
    (OUT / 'robots.txt').write_text('User-agent: *\nDisallow: /\n')
    manifest = {'posts': [{'folder': p['date'] + '-' + p['slug'], 'post_id': p['id'], 'date': p['date'], 'kind': p['kind']} for p in archive + test],
                'archive_posts': len(archive), 'rss_emitted': cfg['rss_enabled'],
                'image_sha256': {(p['date'] + '-' + p['slug']) + '/' + n: hashlib.sha256((POSTS_ROOT / (p['date'] + '-' + p['slug']) / 'images' / n).read_bytes()).hexdigest()
                                 for p in archive + test for n in p['images']}}
    (OUT / 'build-manifest.json').write_text(json.dumps(manifest, indent=2))
    print('PASS: ' + str(len(archive)) + ' archive post(s) + ' + str(len(test)) + ' test post(s) built; redirect stubs and feed written; no deployment here.')

if __name__ == '__main__':
    build()
