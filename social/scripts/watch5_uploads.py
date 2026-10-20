"""Uploads of the five channels of "5 channels to watch #1" (new list, window 27 Sep-14 Oct 2026),
read from the official YouTube Data API: playlistItems.list on the uploads playlist (1 unit/page),
videos.list (1 unit per 50 ids). Format by vpi_core.formato (the index's own rule).
Usage: python3 watch5_uploads.py out.json   (run from renders/social/scripts through its wrapper; reads backend/.env)"""
import json, sys, urllib.request, urllib.parse, pathlib, re
root = pathlib.Path(__file__).resolve().parents[2]   # the repo (FIX-1e: was renders/social/scripts)
sys.path.insert(0, str(root / 'backend'))
from vpi_core import formato
env = dict(l.strip().split('=', 1) for l in open(root / 'backend/.env') if '=' in l and not l.startswith('#'))
KEY = env['YOUTUBE_API_KEY'].strip('"')
CH = {'Kikatsu YT': 'UC17gFEItHnUXw6MlrGqgoog', 'PLAY MAN': 'UCO3Lz5NQb4yvfshcaruxCIg',
      'LaPeceraTONTA': 'UCYrpBQzveDWEgZSJguaZLQQ', 'LOVECARS!TV!': 'UCtLo4nwb3ObCDZ4m8b8u7fA',
      'リメンバー昭和チャンネル': 'UC5_MtTXJKSjHIDDv0WQGNIw'}
FROM, TO = '2026-09-27T00:00:00Z', '2026-10-14T23:59:59Z'
units = 0
def get(ep, **q):
    global units; units += 1
    q['key'] = KEY
    return json.load(urllib.request.urlopen(f'https://www.googleapis.com/youtube/v3/{ep}?' + urllib.parse.urlencode(q)))
def secs(d):
    m = re.match(r'P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', d or '')
    if not m: return 0
    dd, h, mi, s = (int(x or 0) for x in m.groups()); return dd*86400 + h*3600 + mi*60 + s
out = {}
for name, cid in CH.items():
    ids, tok = [], None
    while True:
        q = dict(part='contentDetails', playlistId='UU' + cid[2:], maxResults=50)
        if tok: q['pageToken'] = tok
        r = get('playlistItems', **q)
        pub = [(it['contentDetails']['videoId'], it['contentDetails'].get('videoPublishedAt', '')) for it in r['items']]
        ids += [v for v, p in pub if FROM <= p <= TO]
        tok = r.get('nextPageToken')
        if not tok or (pub and min(p for _, p in pub if p) < FROM): break
    vids = []
    for i in range(0, len(ids), 50):
        r = get('videos', part='snippet,contentDetails,statistics,player,liveStreamingDetails', id=','.join(ids[i:i+50]), maxHeight=1000)
        for it in r['items']:
            sn, cd, pl = it['snippet'], it['contentDetails'], it.get('player', {})
            vids.append({'id': it['id'], 'published': sn['publishedAt'], 'title': sn['title'],
                         'seconds': secs(cd.get('duration')), 'format': formato(secs(cd.get('duration')), pl.get('embedWidth'), pl.get('embedHeight'), sn['publishedAt']),
                         'live': 'liveStreamingDetails' in it, 'views': int(it.get('statistics', {}).get('viewCount', 0))})
    out[name] = {'channel_id': cid, 'uploads': sorted(vids, key=lambda v: v['published'])}
out['_meta'] = {'window': [FROM, TO], 'read_at': __import__('datetime').datetime.utcnow().isoformat() + 'Z', 'units': units}
pathlib.Path(sys.argv[1]).write_text(json.dumps(out, ensure_ascii=False, indent=1))
print('units', units, {k: len(v['uploads']) for k, v in out.items() if k != '_meta'})
