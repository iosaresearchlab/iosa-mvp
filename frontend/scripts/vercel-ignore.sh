#!/bin/bash
# Vercel "Ignored Build Step" (FIX-1d, 23/10/2026). Exit 0 = skip this build,
# exit 1 = build. Every production deploy starts the ISR cache again, so every
# creator page a crawler then visits is a new ISR write; most commits touch
# only backend/, docs/, social/ or tests/. Skip when nothing under frontend/
# changed since the last deployed commit. When that commit is unknown or not
# in the clone, build.
echo "node $(node -v 2>/dev/null)"     # FIX-1h: the build's Node version in its log
prev="${VERCEL_GIT_PREVIOUS_SHA:-}"
if [ -z "$prev" ] || ! git cat-file -e "${prev}^{commit}" 2>/dev/null; then
  echo "build: no previous deployed commit to compare"
  exit 1
fi
if git diff --quiet "$prev" HEAD -- .; then
  echo "skip: nothing under frontend/ changed since ${prev:0:7}"
  exit 0
fi
echo "build: frontend/ changed since ${prev:0:7}"
exit 1
