"""Export the week's long-form records for the 3D room prototype. Read-only."""
import json, os, sys, urllib.request, urllib.parse, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))  # the repo: social.paths (FIX-1e)
from social import paths
env = {}
for line in open(paths.REPO / 'backend' / '.env', encoding='utf-8'):
    if '=' in line and not line.startswith('#'):
        k, v = line.rstrip('\n').split('=', 1); env[k] = v.strip().strip('"')
URL, KEY = env['SUPABASE_URL'].rstrip('/'), env['SUPABASE_SERVICE_KEY']
D0, D1 = sys.argv[1], sys.argv[2]
cols = ('id,external_post_id,content_text,author_name,channel_id,channel_handle,baseline_score,baseline_rule,'
        'entered_on,left_on,days_charting,countries,categories,was_live,vpi_max,views_max,duration_s,'
        'post_daily(day_index,vpi_ratio,views)')
rows, off = [], 0
while True:
    q = (f"{URL}/rest/v1/posts?select={urllib.parse.quote(cols, safe=',()_')}"
         f"&format=eq.LONG&entry_certain=is.true&hidden=not.is.true"
         f"&entered_on=gte.{D0}&entered_on=lte.{D1}&post_daily.day_index=eq.1&order=id")
    req = urllib.request.Request(q, headers={'apikey': KEY, 'Authorization': 'Bearer ' + KEY,
                                             'Range-Unit': 'items', 'Range': f'{off}-{off+999}'})
    chunk = json.load(urllib.request.urlopen(req, timeout=60))
    rows += chunk
    if len(chunk) < 1000: break
    off += 1000
json.dump(rows, open(paths.work() / 'room' / 'raw.json', 'w', encoding='utf-8'), ensure_ascii=False)
print(len(rows))
