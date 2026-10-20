# IOSA motion renderer (owner-approved method, 16/10/2026).
# usage: python3 -I render_motion.py <template.html> <data.json> <out.mp4> [--workers N] [--fps 30]
#
# The template is one paused GSAP timeline: window.render(t) seeks it, so every frame is a pure
# function of t. The template also declares window.DURATION (seconds) and window.CUES, a list of
# {t, k, ...} sound cues written next to the tweens they belong to. This script renders the frames
# (in parallel), synthesizes the audio FROM THE CUES (no third-party audio, nothing to license),
# lays a quiet 120 BPM bed under it, ducks the bed under every hit, normalizes to -14 LUFS and muxes.
import json, sys, urllib.parse, pathlib, subprocess, tempfile, wave, os
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))  # the repo: social.paths (FIX-1e)
from social.paths import template
from multiprocessing import Process
import numpy as np
from scipy.signal import fftconvolve, butter, sosfilt

args = sys.argv[1:]
tpl, data_path, out = args[0], args[1], args[2]
W = int(args[args.index('--workers') + 1]) if '--workers' in args else max(1, os.cpu_count() or 1)
FPS = int(args[args.index('--fps') + 1]) if '--fps' in args else 30
data = json.loads(pathlib.Path(data_path).read_text())
URL = template(tpl).as_uri() + '?d=' + urllib.parse.quote(json.dumps(data))
tmp = pathlib.Path(tempfile.mkdtemp(prefix='iosa_motion_'))


def open_page(p):
    b = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    pg = b.new_page(viewport={'width': 1080, 'height': 1920})
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto(URL)
    pg.wait_for_function('window.__ready === true', timeout=20000)
    pg.wait_for_timeout(300)
    return b, pg, errs


def worker(frames):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b, pg, errs = open_page(p)
        clip = {'x': 0, 'y': 0, 'width': 1080, 'height': 1920}
        for i in frames:
            pg.evaluate(f'render({i / FPS})')
            pg.screenshot(path=str(tmp / f'f{i:05d}.png'), clip=clip)
        b.close()
        if errs:
            print('PAGE ERRORS', errs, flush=True)


# 1. read duration and cues from the template itself
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b, pg, errs = open_page(p)
    dur = float(pg.evaluate('window.DURATION'))
    cues = pg.evaluate('window.CUES || []')
    b.close()
    if errs:
        sys.exit('template errors: ' + '; '.join(errs))
n = int(round(dur * FPS))
REMIX = args[args.index('--remix') + 1] if '--remix' in args else None

# 2. frames, in W parallel browsers (skipped with --remix <video.mp4>: new audio on existing frames)
procs = [] if REMIX else None
if not REMIX:
  procs = [Process(target=worker, args=(range(k, n, W),)) for k in range(W)]
[q.start() for q in procs]; [q.join() for q in procs]
missing = [] if REMIX else [i for i in range(n) if not (tmp / f'f{i:05d}.png').exists()]
if missing:
    sys.exit(f'{len(missing)} frames missing, first {missing[:5]}')

# 3. audio from the cues
SR = 44100
L = int(SR * dur) + SR
fx = np.zeros(L)        # cue layer
duck = np.ones(L)       # gain applied to the bed
rng = np.random.default_rng(7)
T = lambda d: np.arange(int(d * SR)) / SR
def put(sig, t, buf=None):
    buf = fx if buf is None else buf
    s = int(t * SR); e = min(L, s + len(sig))
    if e > s: buf[s:e] += sig[:e - s]
def dip(t, depth=0.55, d=0.35):
    s = int(t * SR); x = T(d); g = 1 - depth * np.exp(-x / (d / 3))
    e = min(L, s + len(g))
    if e > s: duck[s:e] = np.minimum(duck[s:e], g[:e - s])
def bp(sig, lo, hi):
    return sosfilt(butter(2, [lo, hi], btype='band', fs=SR, output='sos'), sig)
PENTA = [220.0, 261.63, 293.66, 329.63, 392.0, 440.0, 523.25, 587.33, 659.25, 783.99]

# Per-kind level in dB relative to the effects bus; None = muted. Owner 16-17/10: the effects must not
# narrate the motion (no clock ticking, no bells, no counting blips); the bar notes stay audible.
KIND_DB = {'whoosh': -6, 'tick': None, 'whirr': None, 'ding': None, 'pluck': 6, 'riser': -8, 'hit': -6, 'impact': -2}
fx_parts = {}
for c in cues:
    t, k = c['t'], c['k']
    if KIND_DB.get(k, 0) is None:
        continue
    fx_save = fx; fx = np.zeros(L)
    if k == 'whoosh':                         # filtered noise that swells and passes, like air
        d = c.get('d', 0.8) + 0.25; x = T(d)
        env = np.sin(np.pi * np.clip(x / d, 0, 1)) ** 2
        nz = rng.standard_normal(len(x))
        lo = bp(nz, 300, 1400); hi = bp(nz, 1500, 6000)
        mix = lo * (1 - x / d) + hi * (x / d)
        put(0.55 * env * mix / (np.abs(mix).max() + 1e-9), t - 0.12)
    elif k == 'tick':                         # small bright blip, rising with the count
        x = T(0.06); f = 1300 + 900 * c.get('p', 0)
        put(0.22 * np.sin(2 * np.pi * f * x) * np.exp(-x / 0.012), t)
    elif k == 'whirr':                        # a clock hand spinning: ratchet clicks, fast then slow
        d = c.get('d', 1.8); m = 26
        for j in range(m):
            u = j / (m - 1); tt = t + d * (0.5 - 0.5 * np.cos(np.pi * u))
            x = T(0.02); put(0.12 * rng.standard_normal(len(x)) * np.exp(-x / 0.003), tt)
    elif k == 'ding':                         # a bell: fundamental + inharmonic partials
        f = c.get('f', 880); x = T(1.6)
        s = (np.sin(2*np.pi*f*x) + 0.5*np.sin(2*np.pi*2.76*f*x)*np.exp(-x/0.25) + 0.25*np.sin(2*np.pi*5.4*f*x)*np.exp(-x/0.1))
        put(0.28 * s * np.exp(-x / 0.55) * np.minimum(1, x / 0.004), t); dip(t, 0.35)
    elif k == 'pluck':                        # one note per bar, pitch = bar height, timbre = series
        p = c.get('p', 0.5); f = PENTA[int(round(p * (len(PENTA) - 1)))]
        x = T(0.7)
        if c.get('alt'):
            s = (2 / np.pi) * np.arcsin(np.sin(2 * np.pi * f * x))           # triangle
        else:
            s = np.sin(2 * np.pi * f * x) + 0.3 * np.sin(4 * np.pi * f * x)
        g = 0.26 if c.get('mp', True) else 0.09
        put(3.0 * g * s * np.exp(-x / 0.22) * np.minimum(1, x / 0.003), t)   # owner 16/10: the bar notes must be heard
    elif k == 'riser':                        # tension while the line draws
        d = c.get('d', 2.2); x = T(d)
        f = 180 + 520 * (x / d) ** 2
        s = np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.35 * bp(rng.standard_normal(len(x)), 2000, 8000)
        put(0.30 * s * (x / d) ** 1.6, t)
    elif k in ('hit', 'impact'):              # low thump (+ noise burst and longer tail for impact)
        g = c.get('g', 1.0) * (1.25 if k == 'impact' else 1)
        d = 1.4 if k == 'impact' else 0.5; x = T(d)
        thump = np.sin(2 * np.pi * (45 + 110 * np.exp(-x / 0.03)) * x) * np.exp(-x / (0.35 if k == 'impact' else 0.14))
        nz = bp(rng.standard_normal(len(x)), 800, 7000) * np.exp(-x / 0.05) * 0.4
        put(0.6 * g * (thump + nz), t); dip(t, 0.75 if k == 'impact' else 0.55, 0.6 if k == 'impact' else 0.35)

    fx = fx_save + fx * 10 ** (KIND_DB.get(k, 0) / 20)

# small room on the cue layer, so the sounds sit together
ir_x = T(0.9); ir = rng.standard_normal(len(ir_x)) * np.exp(-ir_x / 0.18); ir /= np.abs(ir).sum() / 6
fx = fx + 0.22 * fftconvolve(fx, ir)[:L]
fx = fx / (np.abs(fx).max() + 1e-9)

# MUSIC carries the piece (owner, 16/10: music in front, effects low, there to support it).
# 120 BPM, A minor (Am F C G), 2 s a bar. Arrangement follows the scenes: a filtered intro,
# the full groove from the first hand-off, a lighter bar in the middle, everything back for the end.
BPM = 120; beat = 60 / BPM; bar = 4 * beat
CH = [[220.0, 261.63, 329.63], [174.61, 220.0, 261.63], [261.63, 329.63, 392.0], [196.0, 246.94, 293.66]]
ROOT = [110.0, 87.31, 130.81, 98.0]
mL = np.zeros(L); mR = np.zeros(L)
def putm(sig, t, g=1.0, pan=0.0):
    if t < 0:
        sig = sig[int(-t * SR):]; t = 0.0
    s0 = int(t * SR); e = min(L, s0 + len(sig))
    if e > s0:
        mL[s0:e] += g * (1 - max(0, pan)) * sig[:e - s0]; mR[s0:e] += g * (1 + min(0, pan)) * sig[:e - s0]
def saw(f, x, h=8):
    return sum(((-1) ** (k + 1)) * np.sin(2 * np.pi * k * f * x) / k for k in range(1, h + 1)) * (2 / np.pi)
def lp(sig, fc):
    return sosfilt(butter(2, min(fc, SR / 2 - 100), btype='low', fs=SR, output='sos'), sig)
cut = [c['t'] for c in cues if c['k'] == 'whoosh']          # scene hand-offs
first = cut[0] if cut else 2 * bar
mid = cut[2] if len(cut) > 2 else dur / 2                    # lighter section starts here
back = cut[3] if len(cut) > 3 else mid + 2 * bar
full = cut[1] if len(cut) > 1 else first                    # owner 16/10: the groove builds in scene 2, full from scene 3
off = (first % bar) - bar if first % bar else 0.0           # phase the grid so a downbeat lands on the first hand-off
nbars = int(np.ceil((dur - off) / bar)) + 1
for b in range(nbars):
    t0 = off + b * bar; ch = CH[b % 4]; rt = ROOT[b % 4]
    intro = t0 < first - 0.01; light = (mid <= t0 < back) or (first - 0.01 <= t0 < full - 0.01)
    x = T(bar)
    # pad: detuned saws, low-passed, opening during the intro
    fc = 900 + 2600 * min(1, max(0, t0) / max(first, 0.1)) if intro else 3200
    for i, f in enumerate(ch):
        for det, pan in ((0.997, -0.5), (1.003, 0.5)):
            putm(lp(saw(f * det, x, 6), fc) * np.minimum(1, x / 0.25) * np.minimum(1, (bar - x) / 0.2), t0, 0.07, pan)
    # bass: root on the eighths, short and round
    if not intro:
        for q in range(8):
            xb = T(beat / 2 * 0.9)
            putm(lp(saw(rt / 2, xb, 5), 600) * np.exp(-xb / 0.18), t0 + q * beat / 2, 0.30 if not light else 0.18)
    # arpeggio: chord tones on the sixteenths, up an octave
    notes = [ch[0] * 2, ch[1] * 2, ch[2] * 2, ch[1] * 2]
    for q in range(16):
        xa = T(beat / 4 * 0.95); f = notes[q % 4]
        g = 0.05 if intro else (0.06 if light else 0.08)
        putm(lp(saw(f, xa, 4), 4000) * np.exp(-xa / 0.07), t0 + q * beat / 4, g, -0.35 if q % 2 else 0.35)
    # drums
    for q in range(4):
        tb = t0 + q * beat
        if (not intro and not light) or q in (0, 2):
            xk = T(0.35); putm(np.sin(2 * np.pi * (48 + 95 * np.exp(-xk / 0.025)) * xk) * np.exp(-xk / 0.12), tb, 0.55 if not (intro or light) else 0.32)
        if not intro:
            xh = T(0.05); putm(bp(rng.standard_normal(len(xh)), 6000, 14000) * np.exp(-xh / 0.012), tb + beat / 2, 0.10, 0.3)
        if not intro and not light and q in (1, 3):
            xc = T(0.2); putm(bp(rng.standard_normal(len(xc)), 900, 5000) * np.exp(-xc / 0.05), tb, 0.16, -0.1)
# gentle pump on the music from the kick, so it breathes
pump = np.ones(L)
for b in range(nbars * 4):
    tb0 = off + b * beat
    if tb0 < 0: continue
    s0 = int(tb0 * SR); xg = T(beat); g = 1 - 0.18 * np.exp(-xg / 0.09)
    e = min(L, s0 + len(g))
    if e > s0: pump[s0:e] = g[:e - s0]
mL *= pump; mR *= pump
# slow leveler: sections may change texture, never jump in loudness (owner 17/10: no swell on scene 2)
win = int(1.5 * SR); mono = (mL + mR) / 2
rms = np.sqrt(np.convolve(mono ** 2, np.ones(win) / win, mode='same')) + 1e-6
tgt = np.median(rms[int(first * SR):int(min(dur, L / SR) * SR)])
lev = np.clip((tgt / rms) ** 0.8, 0.6, 1.5)
lev = np.convolve(lev, np.ones(int(0.8 * SR)) / int(0.8 * SR), mode='same')
mL *= lev; mR *= lev
MUSIC = args[args.index('--music') + 1] if '--music' in args else None
if MUSIC:                                                     # owner's own track (e.g. Suno): replaces the synthesized one
    moff = float(args[args.index('--music-offset') + 1]) if '--music-offset' in args else 0.0
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(moff), '-i', MUSIC, '-f', 's16le', '-ac', '2', '-ar', str(SR), '-'],
                         capture_output=True, check=True).stdout
    st2 = np.frombuffer(raw, dtype=np.int16).astype(np.float64) / 32768
    ml_, mr_ = st2[0::2], st2[1::2]
    mL = np.zeros(L); mR = np.zeros(L); k_ = min(L, len(ml_)); mL[:k_] = ml_[:k_]; mR[:k_] = mr_[:k_]
mpk = max(np.abs(mL).max(), np.abs(mR).max()) + 1e-9; mL /= mpk; mR /= mpk

# MIXER: music at 0 dB, effects 16 dB under it, ducking only a touch under the big hits
MUSIC_DB, FX_DB, DUCK = 0.0, -18.0, 0.2
gm, gf = 10 ** (MUSIC_DB / 20), 10 ** (FX_DB / 20)
dk = 1 - DUCK * (1 - duck)
aL = gm * mL * dk + gf * fx; aR = gm * mR * dk + gf * fx
n_s = int(SR * dur); aL, aR = aL[:n_s], aR[:n_s]
fade = int(1.5 * SR); ramp = np.linspace(1, 0, fade); aL[-fade:] *= ramp; aR[-fade:] *= ramp
pk = max(np.abs(aL).max(), np.abs(aR).max()) + 1e-9; aL, aR = aL / pk * 0.9, aR / pk * 0.9
if os.environ.get('IOSA_STEMS'):                            # debug: dump music and effects stems as heard in the mix
    d_ = pathlib.Path(os.environ['IOSA_STEMS']); d_.mkdir(exist_ok=True)
    np.save(d_ / 'music.npy', (gm * (mL + mR) / 2 * dk)[:n_s] / pk * 0.9); np.save(d_ / 'fx.npy', (gf * fx)[:n_s] / pk * 0.9)
st = np.empty(2 * n_s); st[0::2] = aL; st[1::2] = aR
with wave.open(str(tmp / 'a.wav'), 'w') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((st * 32767).astype(np.int16).tobytes())

# 4. encode and mux
vin = ['-i', REMIX] if REMIX else ['-framerate', str(FPS), '-i', str(tmp / 'f%05d.png')]
venc = ['-map', '0:v', '-map', '1:a', '-c:v', 'copy'] if REMIX else ['-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', '-preset', 'medium']
subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', *vin,
                '-i', str(tmp / 'a.wav'), *venc,
                '-af', 'loudnorm=I=-16.5:TP=-1.5:LRA=11', '-c:a', 'aac', '-b:a', '192k', '-shortest',
                '-movflags', '+faststart', out], check=True)
for f in tmp.iterdir():
    f.unlink()
tmp.rmdir()
print(out, f'{n} frames, {len(cues)} sound cues, {W} workers')
