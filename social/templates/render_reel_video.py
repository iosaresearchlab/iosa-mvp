# usage: python3 -I render_reel_video.py <template.html> <data.json> <out.mp4> <seconds>
# Renders 1080x1920 frames at 30 fps through the template's render(t), encodes H.264,
# and muxes an original 120 BPM beat synthesized here (no third-party audio), loudness -14 LUFS.
import json, sys, urllib.parse, pathlib, subprocess, tempfile, wave
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))  # the repo: social.paths (FIX-1e)
from social.paths import template
import numpy as np
from playwright.sync_api import sync_playwright
tpl, data, out, dur = sys.argv[1], pathlib.Path(sys.argv[2]).read_text(), sys.argv[3], float(sys.argv[4])
FPS = 30
tmp = pathlib.Path(tempfile.mkdtemp())
url = template(tpl).as_uri() + '?d=' + urllib.parse.quote(json.dumps(json.loads(data)))
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    pg = b.new_page(viewport={'width': 1080, 'height': 1920})
    pg.goto(url); pg.wait_for_timeout(2000)
    el = pg.locator('#s')
    for i in range(int(FPS * dur)):
        pg.evaluate(f'render({i / FPS})')
        el.screenshot(path=str(tmp / f'f{i:04d}.png'))
    b.close()
# beat: kick on every beat, hat on off-beats, a soft pad per bar (A minor), 120 BPM
sr = 44100; n = int(sr * dur); a = np.zeros(n); beat = 0.5
def env(L, d): x = np.arange(L) / sr; return np.exp(-x / d)
for k in range(int(dur / beat)):
    s = int(k * beat * sr); L = min(int(0.35 * sr), n - s)
    if L <= 0: break
    x = np.arange(L) / sr
    a[s:s+L] += 0.9 * np.sin(2*np.pi*(50 + 90*np.exp(-x/0.04))*x) * env(L, 0.12)
    h = int((k + 0.5) * beat * sr); Lh = min(int(0.06 * sr), n - h)
    if Lh > 0: a[h:h+Lh] += 0.12 * np.random.default_rng(k).standard_normal(Lh) * env(Lh, 0.015)
chords = [[220, 261.6, 329.6], [174.6, 220, 261.6], [196, 246.9, 293.7], [164.8, 207.7, 246.9]]
for bar in range(int(dur / 2) + 1):
    s = int(bar * 2 * sr); L = min(int(2 * sr), n - s)
    if L <= 0: break
    x = np.arange(L) / sr; c = chords[bar % 4]
    pad = sum(np.sin(2*np.pi*f*x) for f in c) / 3
    a[s:s+L] += 0.18 * pad * np.minimum(1, x/0.3) * np.minimum(1, (2-x)/0.3)
a = a / np.max(np.abs(a)) * 0.8
fade = int(1.5 * sr); a[-fade:] *= np.linspace(1, 0, fade)
with wave.open(str(tmp / 'a.wav'), 'w') as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes((a * 32767).astype(np.int16).tobytes())
subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', str(FPS), '-i', str(tmp / 'f%04d.png'),
                '-i', str(tmp / 'a.wav'), '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18',
                '-af', 'loudnorm=I=-14:TP=-1.5:LRA=11', '-c:a', 'aac', '-b:a', '192k', '-shortest', out], check=True)
print(out)
