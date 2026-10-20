"""Where the social tooling's code is and where it works (FIX-1e, 20/10/2026).

The code and the templates are versioned here, in the repo's social/. The
working folder (queue, media, credentials, the featured registry) stays
renders/social/ on the owner's PC, outside git: renders/ is in .gitignore.
The thin wrappers in renders/social/ (written by social/wrappers.py) set
IOSA_SOCIAL_WORK to that folder and hand over to the code here.
"""
import os
import pathlib

CODE = pathlib.Path(__file__).resolve().parent          # social/
REPO = CODE.parent                                      # the repository (C:\Work\iosa-lab)


def work() -> pathlib.Path:
    """renders/social: queue, media, featured.json."""
    return pathlib.Path(os.environ.get("IOSA_SOCIAL_WORK") or REPO / "renders" / "social")


def renders() -> pathlib.Path:
    """renders/: the API credentials (bluesky.txt, instagram_token.json, threads_token.json)."""
    return work().parent


def template(name) -> pathlib.Path:
    """A template given as a path: the path itself when it exists (relative to
    the current folder, as before), otherwise the file of that name in
    social/templates."""
    p = pathlib.Path(name)
    if p.exists():
        return p.resolve()
    q = CODE / "templates" / p.name
    if q.exists():
        return q
    raise FileNotFoundError(f"template {name}: not in the current folder nor in {CODE / 'templates'}")
