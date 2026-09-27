"""27/09/2026: is itemCount < 5 a safe skip? Checked on night 1's real records.

For every channel of a night-1 record that was actually read (standard or
not_computable), read the uploads playlist id (channels.list, 50 per unit) and
its itemCount (playlists.list, 50 per unit). A standard record on a channel
with itemCount < 5 would be a false skip; a not_computable record on such a
channel is the saving. Every call is logged before it is sent. The API key is
read from backend/.env and never printed.

    python tests/verify_itemcount.py > docs/itemcount-check-2026-09-27.json
"""

import json
import sys
import time
from collections import Counter
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
LOG = Path.home() / "itemcount_calls.log"


def env():
    out = {}
    for line in (ROOT / "backend" / ".env").read_text(encoding="utf-8").splitlines():
        k, _, v = line.strip().partition("=")
        out[k] = v.strip().strip('"')
    return out


def main():
    e = env()
    url, svc, key = e["SUPABASE_URL"], e["SUPABASE_SERVICE_KEY"], e["YOUTUBE_API_KEY"]
    hdr = {"apikey": svc, "Authorization": f"Bearer {svc}"}
    rows, off = [], 0
    while True:
        r = requests.get(f"{url}/rest/v1/posts", headers={**hdr, "Range": f"{off}-{off + 999}"},
                         params={"select": "channel_id,baseline_rule,format", "entered_on": "eq.2026-09-26",
                                 "baseline_rule": "in.(standard,not_computable)"}, timeout=60)
        r.raise_for_status()
        batch = r.json()
        rows += batch
        if len(batch) < 1000:
            break
        off += 1000
    rules = {}
    for x in rows:
        rules.setdefault(x["channel_id"], set()).add(x["baseline_rule"])
    chans = sorted(rules)
    calls = Counter()
    log = LOG.open("a", encoding="utf-8")

    def get(ep, params):
        log.write(f"{time.time():.3f} {ep}\n"); log.flush()
        calls[ep] += 1
        r = requests.get(f"https://www.googleapis.com/youtube/v3/{ep}", params={**params, "key": key}, timeout=30)
        r.raise_for_status()
        return r.json()

    uploads = {}
    for i in range(0, len(chans), 50):
        d = get("channels", {"part": "contentDetails", "id": ",".join(chans[i:i + 50]), "maxResults": 50})
        for it in d.get("items", []):
            uploads[it["id"]] = it["contentDetails"]["relatedPlaylists"]["uploads"]
    pls = sorted(uploads.values())
    owner = {v: k for k, v in uploads.items()}
    count = {}
    for i in range(0, len(pls), 50):
        d = get("playlists", {"part": "contentDetails", "id": ",".join(pls[i:i + 50]), "maxResults": 50})
        for it in d.get("items", []):
            count[owner[it["id"]]] = it["contentDetails"]["itemCount"]
    uu_rule = sum(1 for c, u in uploads.items() if u != "UU" + c[2:])
    out = {
        "channels": len(chans),
        "with_uploads_id": len(uploads), "with_item_count": len(count),
        "uploads_id_not_UC_to_UU": uu_rule,
        "standard_channels": sum("standard" in r for r in rules.values()),
        "standard_with_itemcount_lt5": sorted(c for c, r in rules.items()
                                              if "standard" in r and count.get(c, 99) < 5),
        "not_computable_only_channels": sum(r == {"not_computable"} for r in rules.values()),
        "not_computable_with_itemcount_lt5": sum(1 for c, r in rules.items()
                                                 if r == {"not_computable"} and count.get(c, 99) < 5),
        "calls": dict(calls), "units": sum(calls.values()),
    }
    json.dump(out, sys.stdout, indent=1)


if __name__ == "__main__":
    main()
