"""Deep dive #1 (new list) fingerprints, window 27 Sep-14 Oct 2026 (18 daily readings).
Inputs: 2026-10-15-watch5-uploads.json (official API, watch5_uploads.py) and, from Supabase
(queries in the comments), the days each channel had a record in post_daily and the ids ever observed.
Presence = readings with a video of the channel in Most Popular / 18.
Hit rate = long, non-live uploads published in the window ever observed in Most Popular / those uploads.
Cadence = UTC days with a long, non-live upload / 18.
On time = long, non-live uploads within 60 min of the channel's median upload time (UTC clock)."""
import json, statistics, datetime as dt
U = json.load(open('2026-10-15-watch5-uploads.json'))
# select distinct d.day from post_daily d join posts p on p.id=d.post_id where p.method_version='v2' and p.channel_id=:c and d.day between '2026-09-27' and '2026-10-14'
def rng(a, b): 
    s, e = dt.date.fromisoformat(a), dt.date.fromisoformat(b); return {str(s + dt.timedelta(i)) for i in range((e - s).days + 1)}
PRES = {
 'Kikatsu YT': rng('2026-09-27','2026-10-14'),
 'PLAY MAN': rng('2026-09-27','2026-10-06') | rng('2026-10-11','2026-10-14'),
 'LaPeceraTONTA': rng('2026-10-01','2026-10-14'),
 'LOVECARS!TV!': rng('2026-10-02','2026-10-07') | rng('2026-10-12','2026-10-14'),
 'リメンバー昭和チャンネル': rng('2026-09-27','2026-10-06') | rng('2026-10-08','2026-10-14'),
}
# select external_post_id from posts where external_post_id in (<all ids of the uploads file>)
OBS = set('0sxMuG9cw5U 2jjC6XfB-lQ 6RrcVlIHx_k 8YivzLHCuYg BVzO5NXB0XE CVEWd9W7VTE cx-rXlZtP5w DlrGFyP0LpI fDTQtHZaG6k FRkR0eSECK4 GCC3VVKXe40 gQgAEVM-OIA gr9sKIjbdy8 h2BXCM8n7gk hs9g1cRGaZI iDBLC-xz5M0 kbUMb1NQAYY N2e-URaY2dA qA9uMaOE_uc qW3LFajc3Dw rsLgh7jFhPo SgdA_PQJbtQ UnlQwUcjaGo uOaart2b9nk vKr-iBFMaOA'.split())
N = 18
res = {}
for name, v in U.items():
    if name == '_meta': continue
    longs = [u for u in v['uploads'] if u['format'] == 'LONG' and not u['live']]
    mins = [int(u['published'][11:13]) * 60 + int(u['published'][14:16]) for u in longs]
    med = statistics.median(mins)
    ontime = sum(1 for m in mins if min(abs(m - med), 1440 - abs(m - med)) <= 60)
    days = {u['published'][:10] for u in longs}
    hits = [u for u in longs if u['id'] in OBS]
    res[name] = dict(pres=round(100 * len(PRES[name]) / N), hit=round(100 * len(hits) / len(longs)),
                     cad=round(100 * len(days) / N), time=round(100 * ontime / len(longs)),
                     raw=dict(pres=f"{len(PRES[name])}/{N}", hit=f"{len(hits)}/{len(longs)}", cad=f"{len(days)}/{N}",
                              time=f"{ontime}/{len(longs)}", median_utc=f"{int(med//60):02d}:{int(med%60):02d}"))
print(json.dumps(res, ensure_ascii=False, indent=1))
json.dump(res, open('fingerprints_out.json', 'w'), ensure_ascii=False, indent=1)
