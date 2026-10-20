# usage: python3 -I render_card.py <template.html> <data.json> <out.png>
# templates: card_breakout.html, card_top10.html, card_watch5.html
import json, sys, urllib.parse, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))  # the repo: social.paths (FIX-1e)
from social.paths import template
from playwright.sync_api import sync_playwright
tpl, data, out = sys.argv[1], json.loads(pathlib.Path(sys.argv[2]).read_text()), sys.argv[3]
url = template(tpl).as_uri() + '?d=' + urllib.parse.quote(json.dumps(data))
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    pg = b.new_page(viewport={'width':1080,'height':1350})
    pg.goto(url); pg.wait_for_timeout(1500)
    pg.locator('#card').screenshot(path=out)
    b.close()
