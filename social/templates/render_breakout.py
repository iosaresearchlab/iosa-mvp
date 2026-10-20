import json, sys, urllib.parse, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))  # the repo: social.paths (FIX-1e)
from social.paths import template
from playwright.sync_api import sync_playwright
data = json.loads(pathlib.Path(sys.argv[1]).read_text())
out = sys.argv[2]
url = template('card_breakout.html').as_uri() + '?d=' + urllib.parse.quote(json.dumps(data))
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    pg = b.new_page(viewport={'width':1080,'height':1350})
    pg.goto(url); pg.wait_for_timeout(1500)
    pg.locator('#card').screenshot(path=out)
    b.close()
