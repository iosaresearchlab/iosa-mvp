#!/bin/sh
# FIX-1a: rebuilds backend/trophy_tailwind.css, the Tailwind CSS inlined in
# the plaque (generate_trophy.TROPHY_HTML_TEMPLATE) instead of the play CDN
# script. Run it after changing a class in generate_trophy.py. Measured
# 20/10/2026: plaques rendered with it and with the CDN differ in 0 pixels.
set -e
cd "$(dirname "$0")/.."
tmp=$(mktemp -d)
printf '@tailwind base;\n@tailwind components;\n@tailwind utilities;\n' > "$tmp/in.css"
cp backend/generate_trophy.py "$tmp/content.html"
npx -y tailwindcss@3.4.17 -i "$tmp/in.css" -o backend/trophy_tailwind.css --content "$tmp/content.html" --minify
rm -rf "$tmp"
