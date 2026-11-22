"""Build the isolated blog pilot. Standard library only.

Input: sanitized snapshots exported from the authoring Google Docs.
This build does not fetch private Google data, deploy Pages, or emit RSS.
"""
import hashlib
import html
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
OUT = ROOT / '_site'
POSTS_ROOT = ROOT / 'content' / 'posts'

SPECS = {
    '2013-10-14-the-humanitarian-ring': {
        'id': '64003052404', 'slug': 'the-humanitarian-ring', 'title': 'The Humanitarian Ring',
        'date': '2013-10-14', 'original_url': 'https://blog.veritythink.com/post/64003052404/the-humanitarian-ring',
        'kind': 'legacy-test', 'images': ['ring-1.png', 'ring-2.png'],
        'edition_left': 'The archive / No. 64003052404', 'edition_right': 'Original edition · 14 October 2013',
        'kicker': 'From the archive · Technology', 'byline_date': '14 October 2013',
        'note': 'Migration test: this is an archival article, not a new post. Original wording, links, date and both images are retained. Email subscription text above is historical only. No subscription form, RSS feed or email distribution is active. <a href="https://blog.veritythink.com/post/64003052404/the-humanitarian-ring">Read the original post</a>.',
    },
    '2026-11-22-pilot-test-post': {
        'id': 'vt-0001', 'slug': 'pilot-test-post', 'title': 'Publishing test, not a real article',
        'date': '2026-11-22', 'original_url': None,
        'kind': 'new-test', 'images': [],
        'edition_left': 'Pipeline test / No. vt-0001', 'edition_right': 'Test edition · 22 November 2026',
        'kicker': 'Publishing test', 'byline_date': '22 November 2026',
        'note': 'Pipeline test: this is a labelled test post, not a real article. It will be removed when the pilot finishes. No subscription form, RSS feed or email distribution is active.',
    },
}

CSS = '''
:root{--ink:#22211e;--paper:#f7f4ed;--red:#a72b31;--line:#c9c2b6}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink)}
a{color:var(--red);text-underline-offset:3px}a:hover{color:#6b151b}
.wrap{max-width:1120px;margin:auto;padding:0 28px}.test{font:12px/1.5 system-ui,sans-serif;background:var(--red);color:white;text-align:center;padding:9px 18px;letter-spacing:.07em;text-transform:uppercase}
.masthead{padding:35px 0 18px;border-bottom:4px double var(--ink);text-align:center}.name{font:bold clamp(42px,8vw,78px)/1 Georgia,serif;letter-spacing:-.065em;color:var(--ink);text-decoration:none}.tagline{font:11px/1.5 system-ui,sans-serif;letter-spacing:.22em;text-transform:uppercase;margin:14px 0 0}.edition{display:flex;justify-content:space-between;border-bottom:1px solid var(--line);padding:11px 0;font:10px system-ui,sans-serif;letter-spacing:.12em;text-transform:uppercase}
article{max-width:750px;margin:55px auto 70px}.kicker{font:11px system-ui,sans-serif;color:var(--red);text-transform:uppercase;letter-spacing:.16em}h1{font:normal clamp(40px,6vw,60px)/1.05 Georgia,serif;letter-spacing:-.035em;margin:15px 0 20px}.byline{border-top:1px solid var(--line);border-bottom:1px solid var(--line);padding:13px 0;margin:25px 0 35px;font:12px system-ui,sans-serif;color:#625e56}.body{font:19px/1.75 Georgia,serif}.body p{margin:0 0 25px}.body>p:first-child{font-size:23px;line-height:1.6}.body img{display:block;max-width:100%;height:auto;max-height:420px;margin:35px auto}.note{border-left:3px solid var(--red);padding:8px 18px;font:13px/1.6 system-ui,sans-serif;background:#efebe1;margin-top:45px}footer{border-top:4px double var(--ink);padding:24px 0 40px;display:flex;justify-content:space-between;gap:20px;font:11px/1.6 system-ui,sans-serif;color:#625e56}@media(max-width:600px){.wrap{padding:0 20px}.masthead{padding-top:28px}.tagline{letter-spacing:.11em}.edition{font-size:8px}article{margin-top:35px}.body{font-size:18px}footer{display:block}.body>p:first-child{font-size:21px}}
'''

def load_posts():
    posts = []
    for folder in sorted(p for p in POSTS_ROOT.iterdir() if p.is_dir()):
        spec = SPECS.get(folder.name)
        if spec is None:
            raise SystemExit('Unexpected post folder: ' + folder.name)
        post = json.loads((folder / 'post.json').read_text())
        assert set(post) == {'id', 'slug', 'title', 'date', 'original_url', 'kind', 'html', 'images'}
        for key in ('id', 'slug', 'title', 'date', 'original_url', 'kind', 'images'):
            assert post[key] == spec[key], folder.name + ': ' + key
        assert 'docs.google.com' not in post['html']
        assert 'data:image' not in post['html']
        assert '<script' not in post['html'].lower()
        assert post['html'].count('<img ') == len(spec['images'])
        posts.append((folder, spec, post))
    if not posts:
        raise SystemExit('No approved post snapshot present')
    return posts

def render_article(spec, post):
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>{html.escape(post['title'])} | VerityThink test</title><style>{CSS}</style></head><body>
<div class="test">Isolated migration test · Not the live blog</div><div class="wrap"><header class="masthead"><a class="name" href="#">VerityThink</a><p class="tagline">Humanitarian ideas. Technology. Possibility.</p></header><div class="edition"><span>{spec['edition_left']}</span><span>{spec['edition_right']}</span></div>
<main><article><div class="kicker">{spec['kicker']}</div><h1>{html.escape(post['title'])}</h1><div class="byline">Andrej Verity &nbsp; / &nbsp; <time datetime="{post['date']}">{spec['byline_date']}</time></div><div class="body">{post['html']}</div><aside class="note">{spec['note']}</aside></article></main>
<footer><span>VerityThink / An independent space for ideas.</span><span>Google Doc snapshot → static build<br>Test output only. No live-site changes.</span></footer></div></body></html>'''

LIST_CSS = '''.list{max-width:750px;margin:55px auto 70px}.list a{text-decoration:none;color:var(--ink)}.list a:hover h2{color:var(--red)}.list h2{font:normal clamp(28px,4vw,40px)/1.15 Georgia,serif;letter-spacing:-.02em;margin:8px 0 10px}.list .when{font:11px system-ui,sans-serif;color:#625e56;letter-spacing:.1em;text-transform:uppercase}.list .entry{border-bottom:1px solid var(--line);padding:28px 0}'''

def render_index(articles):
    entries = ''
    for spec, post in sorted(articles, key=lambda item: item[1]['date'], reverse=True):
        entries += f'''<div class="entry"><div class="kicker">{spec['kicker']}</div><a href="post/{post['id']}/{post['slug']}/"><h2>{html.escape(post['title'])}</h2></a><div class="when">{spec['byline_date']}</div></div>\n'''
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>VerityThink test</title><style>{CSS + LIST_CSS}</style></head><body>
<div class="test">Isolated migration test · Not the live blog</div><div class="wrap"><header class="masthead"><a class="name" href="#">VerityThink</a><p class="tagline">Humanitarian ideas. Technology. Possibility.</p></header>
<main><div class="list">{entries}</div></main>
<footer><span>VerityThink / An independent space for ideas.</span><span>Google Doc snapshot → static build<br>Test output only. No live-site changes.</span></footer></div></body></html>'''

def build():
    if OUT.exists():
        shutil.rmtree(OUT)
    posts = load_posts()
    articles = []
    for folder, spec, post in posts:
        article_dir = OUT / 'post' / post['id'] / post['slug']
        article_dir.mkdir(parents=True)
        for name in post['images']:
            assert Path(name).name == name
            shutil.copyfile(folder / 'images' / name, OUT / name)
            shutil.copyfile(folder / 'images' / name, article_dir / name)
        page = render_article(spec, post)
        (article_dir / 'index.html').write_text(page)
        articles.append((spec, post, page))
    if len(articles) == 1:
        (OUT / 'index.html').write_text(articles[0][2])
    else:
        (OUT / 'index.html').write_text(render_index([(spec, post) for spec, post, _ in articles]))
    (OUT / 'robots.txt').write_text('User-agent: *\nDisallow: /\n')
    manifest = {'posts': [{'post_id': post['id'], 'date': post['date'], 'kind': post['kind']} for _, _, post in posts], 'rss_emitted': False, 'image_sha256': {name: hashlib.sha256((OUT / name).read_bytes()).hexdigest() for _, _, post in posts for name in post['images']}}
    (OUT / 'build-manifest.json').write_text(json.dumps(manifest, indent=2))
    assert not list(OUT.rglob('*.xml'))
    print('PASS: ' + str(len(posts)) + ' approved post(s) built; archival date and stable ID preserved; no feed or deployment.')

if __name__ == '__main__':
    build()
