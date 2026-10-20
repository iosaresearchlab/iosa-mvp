import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))  # the repo: social.paths (FIX-1e)
from social.paths import template
from playwright.sync_api import sync_playwright
u=template('reel.html').as_uri()
FPS=30; DUR=16.0
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    pg=b.new_page(viewport={'width':1080,'height':1920})
    pg.goto(u); pg.wait_for_timeout(2000)
    el=pg.locator('#s')
    for i in range(int(FPS*DUR)):
        pg.evaluate(f'render({i/FPS})')
        el.screenshot(path=f'frames/f{i:04d}.png')
    b.close()
