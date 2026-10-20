"""Renders plaques away from Render and puts them in the archive (FIX-1a).

Run by .github/workflows/plaques.yml on a GitHub runner, which has the memory
Chromium needs; the backend on Render only serves what is archived (307) and
answers 202 for the rest. The arguments and the archive name come from
plaque_spec.build, the same function /api/trophy/preview uses, so the file
uploaded here is the file the endpoint looks for.

    python render_plaques.py --token iosa_a iosa_b    # these plaques
    python render_plaques.py --mug                    # the mug sample

Needs SUPABASE_URL and SUPABASE_SERVICE_KEY. No YouTube quota. A plaque
already in the archive is never rendered again. Exit code 1 if any plaque
that should exist could not be rendered or uploaded.
"""
import argparse
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

import archivio_targhe          # noqa: E402
import generate_trophy          # noqa: E402
import plaque_spec              # noqa: E402

OUT = "renders"


def _client():
    from supabase import create_client
    url = (os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL") or "").strip()
    key = (os.getenv("SUPABASE_SERVICE_KEY") or "").strip()
    if not (url and key):
        sys.exit("SUPABASE_URL and SUPABASE_SERVICE_KEY are required")
    return create_client(url, key)


def render_token(client, token, render=generate_trophy._render_png_sync):
    """'archived', 'rendered', 'refused:<state>', 'missing' or 'failed:<why>'."""
    res = plaque_spec.claim_lookup(client, token)
    post = (res.data or [None])[0] if res else None
    if not post:
        return "missing"
    refused, name, kwargs = plaque_spec.build(post, claim_token=token)
    if refused:
        return f"refused:{refused}"
    if archivio_targhe.esiste(name):
        return "archived"
    path = render(output_dir=OUT, **kwargs)
    url = archivio_targhe.carica(name, Path(path))
    return "rendered" if url else "failed:upload"


def render_mug(render=generate_trophy._render_mug_preview_sync):
    name = plaque_spec.mug_archive_name()
    if archivio_targhe.esiste(name):
        return "archived"
    path = render("PREVIEW_MUG_REC", "+8.7x", "@TEARDOWNMAYHEM", OUT)
    return "rendered" if archivio_targhe.carica(name, Path(path)) else "failed:upload"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--token", nargs="*", default=[])
    ap.add_argument("--mug", action="store_true")
    a = ap.parse_args(argv)
    if not archivio_targhe.attivo():
        print("FAIL: the archive is not configured (SUPABASE_URL, SUPABASE_SERVICE_KEY)")
        return 1

    client = _client()
    tokens = [t.strip() for t in a.token if t.strip()]
    failed = 0
    if a.mug:
        out = render_mug()
        print(f"mug {plaque_spec.mug_archive_name()}: {out}")
        failed += out.startswith("failed")
    for token in tokens:
        t0 = time.monotonic()
        try:
            out = render_token(client, token)
        except Exception as e:
            out = f"failed:{type(e).__name__}: {e}"
        print(f"{token}: {out} ({time.monotonic() - t0:.1f} s)")
        failed += out.startswith("failed") or out == "missing"
    print(f"{len(tokens)} plaques, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
