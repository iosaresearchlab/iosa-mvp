# social/ — IOSA social tooling (versioned)

FIX-1e (20/10/2026). The code and the templates that publish IOSA's social
posts live here, under git and CI. The working folder stays on the owner's PC,
`renders/social/` (outside git: `renders/` is in `.gitignore`): the queue, the
media, the featured registry, the audio, and the credentials one level up in
`renders/`.

| Here | What |
|---|---|
| `publish_api.py` | Bluesky, Instagram, Threads through their official APIs (`--dry-run`: what would go out, no network, no writes) |
| `templates/` | card, reel and motion templates (`card_*.html`, `reel_*.html`, GSAP), their renderers (`render_*.py`), examples, `iosa-motion-SKILL.md` |
| `room/` | Breakout Room reel: `make_launch_reel.py`, `reel.py`, `reel_mode.js`, `export_room.py`; the page itself is `frontend/public/room/index.html` |
| `scripts/` | one-off analyses of published pieces |
| `xtext.py`, `xtext_tlds.py` | X's weighted length, twitter-text v3 (URLs and bare domains 23, CJK and emoji 2, NFC) |
| `validate_spec.py` | rejects a spec a platform would refuse; `publish_api.py` runs it before publishing anything |
| `paths.py` | where the code is (`social/`) and where it works (`IOSA_SOCIAL_WORK`, default `renders/social`) |
| `wrappers.py` | writes the thin wrappers of `renders/social/` |
| `tests/` | `pytest social -q`, run by CI with the rest |

The scheduled tasks keep their commands: `renders/social/publish_api.py`,
`renders/social/templates/render_*.py` and the others are wrappers that find
the repo and run the code here (`python social/wrappers.py` rewrites them).
A template named by file name (`render_card.py card_top10.html ...`) is read
from the current folder when it is there, otherwise from `social/templates`.
In the cloud workspace, stage `social/` together with what you render: the
staged layout keeps the folder structure, so the wrappers find it.
