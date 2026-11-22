"""Build the isolated legacy-post pilot. Standard library only.

Input: a sanitized snapshot exported from the authoring Google Doc.
This build does not fetch private Google data, deploy Pages, or emit RSS.
"""
import hashlib
import html
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
OUT = ROOT / '_site'
POST = json.loads((ROOT / 'ring.json').read_text())
assert POST['kind'] == 'legacy-test'
assert POST['id'] == '64003052404'
assert POST['date'] == '2013-10-14'
assert len(POST['images']) == 2
assert 'docs.google.com' not in POST['html']
assert 'data:image' not in POST['html']
assert '<script' not in POST['html'].lower()
assert POST['html'].count('<img ') == 2

CSS = '''
:root{--ink:#22211e;--paper:#f7f4ed;--red:#a72b31;--line:#c9c2b6}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink)}
a{color:var(--red);text-underline-offset:3px}a:hover{color:#6b151b}
.wrap{max-width:1120px;margin:auto;padding:0 28px}.test{font:12px/1.5 system-ui,sans-serif;background:var(--red);color:white;text-align:center;padding:9px 18px;letter-spacing:.07em;text-transform:uppercase}
.masthead{padding:35px 0 18px;border-bottom:4px double var(--ink);text-align:center}.name{font:bold clamp(42px,8vw,78px)/1 Georgia,serif;letter-spacing:-.065em;color:var(--ink);text-decoration:none}.tagline{font:11px/1.5 system-ui,sans-serif;letter-spacing:.22em;text-transform:uppercase;margin:14px 0 0}.edition{display:flex;justify-content:space-between;border-bottom:1px solid var(--line);padding:11px 0;font:10px system-ui,sans-serif;letter-spacing:.12em;text-transform:uppercase}
article{max-width:750px;margin:55px auto 70px}.kicker{font:11px system-ui,sans-serif;color:var(--red);text-transform:uppercase;letter-spacing:.16em}h1{font:normal clamp(40px,6vw,60px)/1.05 Georgia,serif;letter-spacing:-.035em;margin:15px 0 20px}.byline{border-top:1px solid var(--line);border-bottom:1px solid var(--line);padding:13px 0;margin:25px 0 35px;font:12px system-ui,sans-serif;color:#625e56}.body{font:19px/1.75 Georgia,serif}.body p{margin:0 0 25px}.body>p:first-child{font-size:23px;line-height:1.6}.body img{display:block;max-width:100%;height:auto;max-height:420px;margin:35px auto}.note{border-left:3px solid var(--red);padding:8px 18px;font:13px/1.6 system-ui,sans-serif;background:#efebe1;margin-top:45px}footer{border-top:4px double var(--ink);padding:24px 0 40px;display:flex;justify-content:space-between;gap:20px;font:11px/1.6 system-ui,sans-serif;color:#625e56}@media(max-width:600px){.wrap{padding:0 20px}.masthead{padding-top:28px}.tagline{letter-spacing:.11em}.edition{font-size:8px}article{margin-top:35px}.body{font-size:18px}footer{display:block}.body>p:first-child{font-size:21px}}
'''

def build():
    if OUT.exists():
        shutil.rmtree(OUT)
    article_dir = OUT / 'post' / POST['id'] / POST['slug']
    article_dir.mkdir(parents=True)
    for name in POST['images']:
        assert Path(name).name == name
        shutil.copyfile(ROOT / name, OUT / name)
        shutil.copyfile(ROOT / name, article_dir / name)
    page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>{html.escape(POST['title'])} | VerityThink test</title><style>{CSS}</style></head><body>
<div class="test">Isolated migration test · Not the live blog</div><div class="wrap"><header class="masthead"><a class="name" href="#">VerityThink</a><p class="tagline">Humanitarian ideas. Technology. Possibility.</p></header><div class="edition"><span>The archive / No. {POST['id']}</span><span>Original edition · 14 October 2013</span></div>
<main><article><div class="kicker">From the archive · Technology</div><h1>{html.escape(POST['title'])}</h1><div class="byline">Andrej Verity &nbsp; / &nbsp; <time datetime="{POST['date']}">14 October 2013</time></div><div class="body">{POST['html']}</div><aside class="note">Migration test: this is an archival article, not a new post. Original wording, links, date and both images are retained. Email subscription text above is historical only. No subscription form, RSS feed or email distribution is active. <a href="{POST['original_url']}">Read the original post</a>.</aside></article></main>
<footer><span>VerityThink / An independent space for ideas.</span><span>Google Doc snapshot → static build<br>Test output only. No live-site changes.</span></footer></div></body></html>'''
    (OUT / 'index.html').write_text(page)
    (article_dir / 'index.html').write_text(page)
    (OUT / 'robots.txt').write_text('User-agent: *\nDisallow: /\n')
    manifest = {'post_id': POST['id'], 'original_date': POST['date'], 'mode': 'legacy-test', 'rss_emitted': False, 'image_sha256': {name: hashlib.sha256((OUT/name).read_bytes()).hexdigest() for name in POST['images']}}
    (OUT / 'build-manifest.json').write_text(json.dumps(manifest, indent=2))
    assert not list(OUT.rglob('*.xml'))
    print('PASS: archival date and stable ID preserved; 2 local images; no feed or deployment.')
    print('Built _site/index.html and original-path test page.')

if __name__ == '__main__':
    build()
