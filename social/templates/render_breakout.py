import json, sys, urllib.parse, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))  # the repo: social.paths (FIX-1e)
from social.paths import template
from playwright.sync_api import sync_playwright
src = pathlib.Path(sys.argv[1]).resolve()
data = json.loads(src.read_text())
out = sys.argv[2]
# "avatar" and "thumb" (face layout, 24/10): a URL, or a file path relative to the data JSON
# (or to the template folder, as in the reel); passed to the page as file:// URIs.
for k in ('avatar', 'thumb'):
    v = data.get(k)
    if v and not v.startswith(('http://', 'https://', 'file:')):
        p = pathlib.Path(v)
        for base in (src.parent, template('card_breakout.html').parent):
            if not p.is_absolute() and (base / p).is_file():
                p = base / p
                break
        if not p.is_file():
            sys.exit(f'{k} not found: {v}')
        data[k] = p.absolute().as_uri()       # not .resolve(): FIX-1e's guard keeps that for templates
url = template('card_breakout.html').as_uri() + '?d=' + urllib.parse.quote(json.dumps(data))
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    pg = b.new_page(viewport={'width':1080,'height':1350})
    pg.goto(url)
    pg.wait_for_function('window.__ready === true', timeout=20000)
    pg.wait_for_timeout(400)
    pg.locator('#card').screenshot(path=out)
    b.close()
