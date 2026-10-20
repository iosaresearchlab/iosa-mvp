// ---------- reel mode ----------
// Injected by make_launch_reel.py in place of the live page's own reel block (owner, 18/10: the fly-through, then an
// insistent zoom on one creator with their card open "on tap", then on their video with its card open).
// The creator is the first video of window.REEL_FOCUS (the latest Friday Top 10, in rank order) found in this week's room.
const REEL = location.hash === '#reel';
if (REEL) {
  document.body.classList.add('reel'); intro.hidden = true; labelRenderer.domElement.style.visibility = 'hidden';
  controls.enabled = false; controls.autoRotate = false;
  document.getElementById('reelSub').textContent = 'Most Popular · long-form · ' + PERIOD;
  const st = document.createElement('style');
  st.textContent = `
    body.reel #card:not([hidden]){display:block!important;}
    body.reel #card{position:fixed!important;left:85px!important;top:290px!important;width:350px;transform-origin:0 0;
      transform:scale(2.6);box-shadow:0 30px 90px rgba(0,0,0,.7);border-color:rgba(0,229,255,.35);}
    body.reel #card ul{max-height:none;overflow:visible;}
    body.reel #card .row a{color:var(--cyan);}
    #reelTap{position:absolute;width:0;height:0;opacity:0;}
    #reelTap i{position:absolute;left:-60px;top:-60px;width:120px;height:120px;border-radius:50%;border:5px solid #00E5FF;box-shadow:0 0 30px #00E5FF;}
    #reelTap b{position:absolute;left:-18px;top:-18px;width:36px;height:36px;border-radius:50%;background:rgba(255,255,255,.9);box-shadow:0 0 24px rgba(0,229,255,.9);}`;
  document.head.appendChild(st);
  const tap = document.createElement('div'); tap.id = 'reelTap'; tap.innerHTML = '<i></i><b></b>';
  document.getElementById('reelUI').appendChild(tap);

  // the focus: first Top 10 video present in this room
  const vidIndex = new Map(V.map((r, i) => [r[0], i]));
  const fv = (window.REEL_FOCUS || []).map(id => vidIndex.get(id)).find(i => i != null && tvPos[i]);
  const fsi = fv != null ? tvPos[fv][3] : stacks.reduce((b, s, i) => (s.band < 5 && s.best > (b < 0 ? -1 : stacks[b].best)) ? i : b, -1);
  const fvi = fv != null ? fv : stacks[fsi].vids.reduce((a, b) => (V[b][4] ?? -1) > (V[a][4] ?? -1) ? b : a);
  const S = stacks[fsi], [tx, ty, tz] = tvPos[fvi];
  const Z = zones, P = (x, y, z) => new THREE.Vector3(x, y, z), FZ = Z[S.band];

  // 0–16 s: the fly-through of the live reel, condensed
  const keys = [
    [0,    P(-40, 150, 150), P(-20, 0, 0)],
    [4,    P(0, 120, 125), P(Z[4].cx * 0.4, 0, 0)],
    [8.5,  P(Z[4].cx + 8, 15, Z[4].d / 2 + 12), P(Z[4].cx, 2, 0)],
    [12,   P(Z[3].cx + 6, 17, Z[3].d / 2 + 14), P(Z[3].cx - 18, 2, 0)],
    [16,   P(S.x + 10, 16, S.z + 16), P(S.x, 1, S.z)]];
  const cp = new THREE.CatmullRomCurve3(keys.map(k => k[1]), false, 'centripetal');
  const ct = new THREE.CatmullRomCurve3(keys.map(k => k[2]), false, 'centripetal');
  const T = keys.map(k => k[0]);
  const u = s => { s = Math.min(Math.max(s, 0), T[T.length - 1]); let i = 0; while (i < T.length - 2 && s > T[i + 1]) i++; const f = (s - T[i]) / (T[i + 1] - T[i]); const e = f < .5 ? 2 * f * f : 1 - Math.pow(-2 * f + 2, 2) / 2; return (i + e) / (T.length - 1); };
  const sm = x => { x = Math.min(1, Math.max(0, x)); return x * x * (3 - 2 * x); };
  const L = (a, b, f) => a.clone().lerp(b, f);
  // close shots: the camera stays nearer than the next row (1.75), so no other stack stands between it and the subject
  // the camera looks down from above the front row and is tilted up (TILT) so the subject sits low in the frame,
  // under the card
  const cA = P(S.x + 0.8, S.top + 4.0, S.z + 1.5), cB = P(S.x + 0.45, S.top + 2.5, S.z + 1.2);
  const cT = P(S.x, S.top + 0.3, S.z);
  const vA = P(tx + 0.6, ty + 2.4, tz + 1.7), vB = P(tx + 0.35, ty + 1.85, tz + 1.6);
  const vT = P(tx, ty, tz + 0.3);
  const TILT = s => THREE.MathUtils.degToRad(12 - 2 * sm((s - T_V0) / (T_V - T_V0)));
  const out = P(S.x - 6, 26, S.z + 30), outT = P(S.x, 0, S.z);
  const T_IN = 16, T_C = 19.4, T_V0 = 25, T_V = 26.6, T_OUT = 32.2, T_END = 32.6;
  function shot(s) {
    if (s <= T_IN) return [cp.getPoint(u(s)), ct.getPoint(u(s))];
    if (s <= T_C) { const f = sm((s - T_IN) / (T_C - T_IN)), p0 = cp.getPoint(1), t0 = ct.getPoint(1);
      const mid = L(p0, cA, 0.5).add(P(0, 3, 0)); const a = L(p0, mid, f), b = L(mid, cA, f);
      return [L(a, b, f), L(t0, cT, sm(f * 1.3))]; }
    if (s <= T_V0) return [L(cA, cB, sm((s - T_C) / (T_V0 - T_C))), cT];
    if (s <= T_V) { const f = sm((s - T_V0) / (T_V - T_V0)); return [L(cB, vA, f), L(cT, vT, f)]; }
    if (s <= T_OUT) return [L(vA, vB, sm((s - T_V) / (T_OUT - T_V))), vT];
    const f = sm((s - T_OUT) / 3.4); return [L(vB, out, f), L(vT, outT, f)];
  }
  const z4 = Z[4];
  const caps = [
    [0, 4, "One week of YouTube's Most Popular.", PERIOD + ' · long-form'],
    [4, 8.5, `${nf.format(V.length)} videos. One TV each.`, 'Each screen: how far the video beat its own channel on day 1.'],
    [8.5, 12, 'Channels that usually get 100K+ views.', `Median day 1: ${fmtV(z4.median)} their usual.`],
    [12, 16, 'Small channels have to beat their usual views by far more to get in.', 'Most Popular takes absolute views.'],
    [16, 19.4, 'Every creator stands on their own videos.', 'Arms up: a video at 50× or more.']];
  const c1 = document.getElementById('cap1'), c2 = document.getElementById('cap2'), cap = c1.parentElement, end = document.getElementById('reelEnd');
  const v = new THREE.Vector3();
  function tapAt(s, t0, p) {
    const k = (s - t0) / 0.7;
    if (k < 0 || k > 1) { tap.style.opacity = 0; return; }
    v.copy(p).project(camera);
    tap.style.left = ((v.x + 1) / 2 * innerWidth) + 'px'; tap.style.top = ((1 - v.y) / 2 * innerHeight) + 'px';
    tap.style.opacity = 1 - k;
    tap.firstChild.style.transform = `scale(${0.3 + k * 1.2})`; tap.lastChild.style.transform = `scale(${1 - k * 0.5})`;
  }
  let shown = null;
  window.__reel = (s) => {
    const [p, t] = shot(s); camera.position.copy(p); camera.lookAt(t); camera.rotateX(TILT(s) * sm((s - T_IN - 1.5) / 2) * (1 - sm((s - T_OUT) / 1.5)));
    const c = caps.find(c => s >= c[0] && s < c[1]);
    if (c) { c1.textContent = c[2]; c2.textContent = c[3]; const a = Math.min(1, (s - c[0]) / 0.35, (c[1] - s) / 0.35); cap.style.opacity = a; cap.style.transform = `translateY(${(1 - a) * 24}px)`; }
    else cap.style.opacity = 0;
    // the taps and the cards: creator at T_C+0.25, video at T_V+0.25, both closed at T_OUT
    const want = s >= T_C + 0.25 && s < T_V - 0.9 ? 'c' : s >= T_V + 0.25 && s < T_OUT ? 'v' : null;
    if (want !== shown) {
      shown = want;
      if (want === 'c') { const sel = {kind:'creator', si:fsi}; showHighlight(sel); showCard(sel, 0, 0, true); }
      else if (want === 'v') { const sel = {kind:'tv', vi:fvi}; showHighlight(sel); showCard(sel, 0, 0, true); }
      else { card.hidden = true; showHighlight(null); }
    }
    if (shown) {
      const k = Math.min(1, (s - (shown === 'c' ? T_C : T_V) - 0.25) / 0.3, ((shown === 'c' ? T_V - 0.9 : T_OUT) - s) / 0.3);
      card.style.opacity = Math.max(0, k); card.style.marginTop = `${(1 - Math.max(0, Math.min(1, k))) * 12}px`;
    }
    tapAt(s, T_C, P(S.x, S.top + 0.75, S.z)); if (s > T_V - 0.1) tapAt(s, T_V, P(tx, ty, tz + 0.3));
    end.style.opacity = Math.min(1, Math.max(0, (s - T_END) / 0.8));
    composer.render();
  };
}

