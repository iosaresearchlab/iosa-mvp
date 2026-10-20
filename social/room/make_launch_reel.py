# usage: python3 make_launch_reel.py <data_url> <out_dir> [seconds]
# Renders the Breakout Room launch reel (1080x1920, 30 fps) from a frozen week of /room data,
# with the original 120 BPM beat, encoded under 30 MB, and writes launch_reel.json (window and counts).
# Needs reel.py next to it and the live page frontend/public/room/index.html (or ROOM_PAGE=<path>).
# FIX-1e: the code (this file, reel.py, reel_mode.js) is in the repo, social/room; it works in
# renders/social/room (test.html, frames, node_modules, the audio), outside git.
import json, os, sys, subprocess, urllib.request, wave, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))  # the repo: social.paths (FIX-1e)
from social import paths
import numpy as np
url, out = sys.argv[1], pathlib.Path(sys.argv[2]); secs = float(sys.argv[3]) if len(sys.argv) > 3 else 30.0
here = pathlib.Path(__file__).resolve().parent; work = paths.work() / 'room'; work.mkdir(parents=True, exist_ok=True)
out = out if out.is_absolute() else work / out   # relative to renders/social/room, as before
os.chdir(work); out.mkdir(parents=True, exist_ok=True)
data = json.load(urllib.request.urlopen(urllib.request.Request(url, headers={'Accept-Encoding': 'identity'}), timeout=120))
assert data.get('v') and data.get('c'), 'empty data'
if not pathlib.Path('node_modules/three/build/three.module.js').exists():
    subprocess.run(['npm', 'i', '--no-save', 'three@0.160.0'], check=True, stdout=subprocess.DEVNULL)
# The page is the LIVE room (frontend/public/room/index.html, owner 17/10): room_template.html is the
# first prototype (old colours, lights and arms) and must not be used. The week's data goes inline.
live = pathlib.Path(os.environ.get('ROOM_PAGE', paths.REPO / 'frontend' / 'public' / 'room' / 'index.html'))
tpl = live.read_text()
hook = '<script>window.ROOM_DATA_URL = "/api/room/latest";</script>'
assert tpl.count(hook) == 1, f'data hook not found in {live}'
blob = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
# Reel block (owner, 18/10): in the 'zoom' version the live page's own reel code is replaced by reel_mode.js (fly-through, then an
# insistent zoom on one creator and on their video, cards open as on a tap). The creator is the first video of the
# latest Friday Top 10 found in the room: renders/social/<date>-top10.json, the newest one not after the room's end.
# Two versions, alternated push after push (owner, 18/10): 'zoom' (36 s, reel_mode.js) on 18 Oct, 15 Nov, ...;
# 'fly' (30 s, the live page's own reel block) on 1 Nov, 29 Nov, ... REEL_STYLE=zoom|fly forces one.
import datetime
push = (datetime.date.today() - datetime.date(2026, 10, 18)).days // 14
style = os.environ.get('REEL_STYLE') or ('zoom' if push % 2 == 0 else 'fly')
if len(sys.argv) <= 3: secs = 36.0 if style == 'zoom' else 30.0
print('style', style, secs, flush=True)
if style == 'zoom':
    a, b = tpl.index('// ---------- reel mode ----------'), tpl.index('// loop')
    tpl = tpl[:a] + (here / 'reel_mode.js').read_text() + tpl[b:]
tops = sorted(p for p in paths.work().glob('20??-??-??-top10.json') if p.name[:10] <= data['to'])
focus = [r['vid'] for r in json.loads(tops[-1].read_text())['rows'] if r.get('vid')] if tops else []
pathlib.Path('test.html').write_text(tpl.replace(hook, '<script>window.REEL_FOCUS = ' + json.dumps(focus) + ';</script>'
    '<script type="application/json" id="room-data">' + blob + '</script>'))
if os.environ.get('STILLS'):   # quick check: STILLS=16,20,27 renders those seconds only
    subprocess.run([sys.executable, str(here / 'reel.py'), 'stills', str(out), os.environ['STILLS']], check=True); sys.exit(0)
frames = pathlib.Path('frames'); frames.mkdir(exist_ok=True)
for f in frames.glob('f*.png'): f.unlink()
n = int(30 * secs)
subprocess.run([sys.executable, str(here / 'reel.py'), 'range', 'frames', f'0-{n-1}'], check=True, env={**os.environ, 'REEL_SECS': str(secs)})
sr = 44100; dur = secs; N = int(sr * dur); a = np.zeros(N); beat = 0.5
def env(L, d): x = np.arange(L) / sr; return np.exp(-x / d)
for k in range(int(dur / beat)):
    s = int(k * beat * sr); L = min(int(0.35 * sr), N - s)
    if L <= 0: break
    x = np.arange(L) / sr
    if k >= 8: a[s:s+L] += 0.9 * np.sin(2*np.pi*(50 + 90*np.exp(-x/0.04))*x) * env(L, 0.12)
    h = int((k + 0.5) * beat * sr); Lh = min(int(0.06 * sr), N - h)
    if Lh > 0 and k >= 16: a[h:h+Lh] += 0.12 * np.random.default_rng(k).standard_normal(Lh) * env(Lh, 0.015)
chords = [[220, 261.6, 329.6], [174.6, 220, 261.6], [196, 246.9, 293.7], [164.8, 207.7, 246.9]]
for bar in range(int(dur / 2) + 1):
    s = int(bar * 2 * sr); L = min(int(2 * sr), N - s)
    if L <= 0: break
    x = np.arange(L) / sr; c = chords[bar % 4]
    a[s:s+L] += 0.2 * (sum(np.sin(2*np.pi*f*x) for f in c) / 3) * np.minimum(1, x/0.3) * np.minimum(1, (2-x)/0.3)
a = a / np.max(np.abs(a)) * 0.8; fi = int(sr); a[:fi] *= np.linspace(0, 1, fi); fo = int(2 * sr); a[-fo:] *= np.linspace(1, 0, fo)
with wave.open('reel_audio.wav', 'w') as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes((a * 32767).astype(np.int16).tobytes())
mp4 = out / f"{data['from']}-reel-breakout-room.mp4"
subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', '30', '-i', 'frames/f%04d.png', '-i', 'reel_audio.wav',
                '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-preset', 'slow', '-b:v', '6M', '-maxrate', '7M', '-bufsize', '12M',
                '-af', 'loudnorm=I=-14:TP=-1.5:LRA=11', '-c:a', 'aac', '-b:a', '192k', '-shortest', '-movflags', '+faststart', str(mp4)], check=True)
meta = {'from': data['from'], 'to': data['to'], 'videos': len(data['v']), 'channels': len(data['c']),
        'live': sum(1 for r in data['v'] if r[13]), 'file': mp4.name, 'bytes': mp4.stat().st_size, 'seconds': secs}
(out / 'launch_reel.json').write_text(json.dumps(meta, indent=1))
print(json.dumps(meta))
