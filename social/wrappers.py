"""Write the thin wrappers of renders/social/ (FIX-1e, 20/10/2026).

    python social/wrappers.py [renders/social]      # default: <repo>/renders/social

The scheduled tasks keep their commands (`cd renders/social && python3
publish_api.py queue/x.json`, `python3 -I render_card.py ...` from
renders/social/templates): each entry point there becomes a few lines that
find the repo and run the versioned code in social/. Rewrites only the
entry points listed in ENTRY_POINTS; queue, media and credentials are not
touched.
"""
import pathlib
import sys

ENTRY_POINTS = [
    "publish_api.py",
    "notifications.py",
    "bsky_engage.py",
    "validate_spec.py",
    "templates/render_breakout.py",
    "templates/render_card.py",
    "templates/render_motion.py",
    "templates/render_reel.py",
    "templates/render_reel_video.py",
    "room/export_room.py",
    "room/make_launch_reel.py",
    "room/reel.py",
    "scripts/fingerprints.py",
    "scripts/watch5_uploads.py",
]

WRAPPER = '''"""Thin wrapper (FIX-1e, 20/10/2026): the code is versioned in the repo, social/{rel}.
Run it exactly as before. This file finds the repo and hands over; written by social/wrappers.py."""
import os, pathlib, runpy, sys
REL = "{rel}"
work = pathlib.Path(__file__).resolve().parents[{depth}]          # renders/social
os.environ.setdefault("IOSA_SOCIAL_WORK", str(work))
for root in [os.environ.get("IOSA_REPO", "")] + [str(p) for p in work.parents] + ["/home/claude/iosa-mvp"]:
    target = pathlib.Path(root) / "social" / REL if root else None
    if target and target.is_file() and target.resolve() != pathlib.Path(__file__).resolve():
        break
else:
    sys.exit("social/" + REL + " not found: stage the folder C:\\\\Work\\\\iosa-lab\\\\social next to renders, "
             "or set IOSA_REPO to the repository")
sys.argv[0] = str(target)
runpy.run_path(str(target), run_name="__main__")
'''


def wrapper(rel: str) -> str:
    return WRAPPER.format(rel=rel, depth=rel.count("/"))


def write(work: pathlib.Path) -> list:
    done = []
    for rel in ENTRY_POINTS:
        p = work / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(wrapper(rel), encoding="utf-8")
        done.append(p)
    return done


if __name__ == "__main__":
    here = pathlib.Path(__file__).resolve().parent
    work = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else here.parent / "renders" / "social"
    for p in write(work):
        print("wrapper", p)
