---
name: iosa-motion
description: Use for every IOSA video or reel (story reels, Top 10 / watch5 countdowns, deep-dive explainers): GSAP timeline template, sound cues, render_motion.py, review frames.
---

# IOSA motion: how every video and reel is made (owner-approved 16/10/2026)

The reference is the deep-dive reel on Kikatsu YT, approved by the owner on 17/10 as v6
(`renders/social/review/2026-10-16/reel-kikatsu-v6.mp4`, template `renders/social/templates/reel_story_channel_v2.html`).
Countdown templates: Friday Top 10 `renders/social/templates/reel_top10_v2.html` (data: rank, x, title, channel,
flag, views, usual per row, from the published `<date>-top10.json`) and Monday 5 channels to watch
`renders/social/templates/reel_watch5_v2.html` (data: name, flag, meta, usual, points per row, from the published
`<date>-watch5.json`), both approved 17/10. Breakout reel for Instagram `renders/social/templates/reel_breakout.html`
(23/10, under owner review; data from the breakout spec: country, country_name, usual, views, x, asof, title, channel,
subs_line, first_line, why, optional cta; example `example_reel_breakout.json`; 16.8 s, 504 frames). Every new video
starts from these templates and this method. The older
frame-by-frame templates (`reel_top10.html`, `reel_watch5.html`, `reel.html`, `render_reel_video.py`) are retired.

## The method

1. **One paused GSAP timeline per video.** GSAP 3.13 with DrawSVGPlugin and MotionPathPlugin, loaded from
   the files next to the template (`gsap.min.js`, `DrawSVGPlugin.min.js`, `MotionPathPlugin.min.js`, Apache
   free licence since 3.13). `window.render = t => tl.seek(t, false)`: every frame is a pure function of t.
   No CSS transitions, no `requestAnimationFrame`, no `Date.now()`, no randomness without a fixed seed.
2. **Data in, never numbers in the HTML.** The template reads its JSON from `?d=`. Every figure comes from
   our readings (`posts`, `post_daily`, `channel_inventory`) or the official API, with the reading date.
3. **Motion rules**
   - Scene changes use `PUSH(from, to, t, d)`: the outgoing and the incoming scene move together
     (yPercent ±14, blur 18px, scale 0.96/1.04, `power3.inOut`). Never a cut, never fade-out then fade-in.
   - Entrances: `IN(selector, t)` — opacity, y 60, blur 14px → 0, `power3.out`, word stagger 0.06.
     No exit animations except at the hand-off and the last scene.
   - Shared elements carry the story across scenes (the 18 squares: grid → strip → chart lane). Prefer
     transforming what is on screen over replacing it.
   - Lines draw with DrawSVG on a smooth path (Catmull-Rom → cubic Bézier), with a bright tip riding it
     on MotionPath and the number counting in sync. Bars grow with `attr: {y, height}`, never `scaleY`
     on SVG rects.
   - One slow camera push for the whole piece (`#world` scale 1 → 1.035, background drift).
   - Safe area for Instagram: y 250–1500 on 1080×1920. Footer CTA always `iosaresearch.org`.
4. **Sound is written next to the motion.** Each tween that deserves a sound registers a cue in the
   same place: `cue(t, 'whoosh'|'tick'|'whirr'|'ding'|'pluck'|'riser'|'hit'|'impact', {...})`. `PUSH`
   adds its whoosh itself. The template exposes `window.CUES` and `window.DURATION`. Audio is synthesized
   by the renderer (no third-party audio, nothing to license). **Music in front, effects underneath
   (owner, 16–17/10):** a 120 BPM track in A minor whose downbeat lands on the first hand-off; sections change
   texture (filtered intro, groove building in scene 2, full from scene 3, lighter in the middle, full to the
   end) but a slow leveler keeps the loudness within about ±1.5 dB, so no section swells. Effects sit 18 dB
   under the music and never narrate the motion: no clock ticks, no bells, no counting blips (those cue kinds
   are muted in `KIND_DB`); soft whooshes on the hand-offs, a soft riser and the logo impact; the one
   exception is the note of each bar in a chart, kept audible (+6 dB on the effects bus). −16.5 LUFS, stereo.
   An owner-supplied track (e.g. made with Suno) replaces the synthesized one: `--music <file> [--music-offset s]`;
   the cue effects stay on top at the same levels. A track with a voice that counts fixes the on-screen times: pass
   them in the data (`times`, `outro_at`, `duration`) so each item appears 0.1 s before its spoken number. The two
   countdown tracks and their exact times are in the playbook ("The two countdowns have their own soundtrack").
   Retiming a track: separate the stems (vocals, bass, drums, other), find the tempo and the downbeats on the drums
   (librosa), cut and repeat whole bars of the instrumental at downbeats (12 ms crossfades, the incoming piece
   starting 12 ms early so the grid does not drift), and place each spoken word, taken from the vocal stem, at the
   grid point you want; check the result with a spectrogram or whisper. To change only the sound: `--remix <existing.mp4>` keeps the frames and rebuilds the audio in seconds.
5. **Render:** `python3 -I render_motion.py <template.html> <data.json> <out.mp4> --workers 2`
   (1080×1920, 30 fps, H.264 + AAC, faststart). Run it in the background; a 26 s video takes minutes.
   The script stops if the page throws an error or a frame is missing.
6. **Check before anything leaves:** pull 6–8 frames (`ffmpeg -ss <t> -frames:v 1`) at the middle of each
   scene and at each transition; look at them: text inside the safe area, no overlaps, numbers equal to
   the JSON, the footer visible. Listen once to the first 5 seconds.
7. **Owner review:** every NEW video type goes to Migert for review before its first publication
   (review/<date>/). Later episodes of an approved type go out with the slot, frames checked as in step 6.

## Text in videos

Fact-led, never didactic. No "excusatio non petita": we state how we read (Most Popular), never why it is
not a limit. Never "entered trending": "first observed in Most Popular". Age-indexed, never age-adjusted.
Two formats never compared. Channels are named with neutral words and the period stated.

## Files

- Template and libraries: `renders/social/templates/reel_story_channel_v2.html`, `gsap.min.js`,
  `DrawSVGPlugin.min.js`, `MotionPathPlugin.min.js`
- Renderer: `renders/social/templates/render_motion.py`
- Countdown tracks: `renders/social/templates/audio/top10-countdown-suno.mp3`, `watch5-countdown-suno-v3.mp3`
  (stems of the Monday one in `audio/stems/`)
- Example data: `renders/social/review/2026-10-16/reel-kikatsu-v2.json`, `review/2026-10-17/reel-top10-2-suno.json`,
  `review/2026-10-17/reel-watch5-1-suno3.json`

## Charts in videos

Value labels never sit on another spike, dot or label: the watch5 template tries above, right, left, then higher, and
keeps a right gutter for the `usual 1×` / `2×` line labels. Look at the frame where every spike of a row is up.
