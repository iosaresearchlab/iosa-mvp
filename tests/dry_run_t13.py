"""T-13: dry run on 3 countries against the REAL YouTube API.

docs/08-implementation-plan.md T-13. Writes nothing to production: the v2
engine runs against a scratch PostgreSQL (pgserver, every migration in
supabase/migrations/ applied verbatim) through tests/pg_client.py.

Two phases, one QuotaCounter with QUOTA_MAX_DAILY = 2000 across both:
  census     vpi_engine.run_daily(snapshot_only=True) on IT, US, DE
  baselines  baseline.baselines_for_videos() on every video of that snapshot,
             as if each were an entry, in batches of 50 channels in a seeded
             random order, until the brake. This measures the real cost of
             the baseline (02 section 4.4): a second reading minutes later
             would have almost no entries.

A device shell call lasts at most 180 s, so the run is resumable: state
(counter included) is saved to STATE after every batch, and the brake is
applied to the cumulative total. Every HTTP response is also tallied by
status in a wrapping session, as an internal check on the counter.

    QUOTA_MAX_DAILY=2000 python tests/dry_run_t13.py census
    QUOTA_MAX_DAILY=2000 python tests/dry_run_t13.py baselines   # repeat until done
    python tests/dry_run_t13.py report > docs/t13-dry-run.json

The API key is read from backend/.env (CRLF-safe) and never printed.
"""

import json
import os
import random
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SUPABASE_URL", "http://127.0.0.1:54321")   # vpi_engine import only
os.environ.setdefault("SUPABASE_KEY", "not-used")

import requests  # noqa: E402

STATE = Path(os.environ.get("T13_STATE", Path.home() / "t13_state.json"))
# Kill-proof record: one line per HTTP attempt, written and flushed BEFORE the
# request is sent. Added after the first run lost a batch's count to a shell
# timeout (see docs/t13-dry-run.md).
CALL_LOG = Path(os.environ.get("T13_CALL_LOG", Path.home() / "t13_calls.log"))
COUNTRIES = ["IT", "US", "DE"]
SEED = 20260925
BUDGET_S = 90      # a batch takes ~60 s: it never straddles a 175 s shell limit


def api_key():
    for line in (ROOT / "backend" / ".env").read_text(encoding="utf-8").splitlines():
        line = line.strip().replace("\r", "")
        if line.startswith("YOUTUBE_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("YOUTUBE_API_KEY not found in backend/.env")


class TallySession(requests.Session):
    def __init__(self, tally):
        super().__init__()
        self.tally = tally

    def get(self, url, **kw):
        ep = url.rsplit("/", 1)[-1]
        if ep == "videos" and (kw.get("params") or {}).get("chart") == "mostPopular":
            ep = "chart"
        with open(CALL_LOG, "a") as log:
            log.write(f"{now()} {ep}\n")
            log.flush()
            os.fsync(log.fileno())
        try:
            r = super().get(url, **kw)
        except requests.RequestException:
            self.tally[f"{ep}:network"] += 1
            raise
        self.tally[f"{ep}:{r.status_code}"] += 1
        return r


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load():
    return json.loads(STATE.read_text()) if STATE.exists() else None


def save(st):
    STATE.write_text(json.dumps(st, indent=1, default=str))


def counter_from(st):
    from quota import QuotaCounter
    c = QuotaCounter()
    c.per_endpoint.update(st["counter"])
    return c


def census():
    import pgserver
    import psycopg
    import vpi_engine as eng
    from quota import QuotaCounter
    from tests.conftest import MIGRATIONS, POSTS_STUB, SUPABASE_STUB
    from tests.pg_client import PgClient

    if load():
        raise SystemExit(f"{STATE} exists: the census already ran")
    srv = pgserver.get_server(str(Path.home() / "pgdata-t13"), cleanup_mode="stop")
    with psycopg.connect(srv.get_uri(), autocommit=True) as c:
        c.execute("drop database if exists t13")
        c.execute("create database t13")
    uri = srv.get_uri().replace("/postgres?", "/t13?")
    conn = psycopg.connect(uri, autocommit=True)
    with conn.cursor() as cur:
        cur.execute(SUPABASE_STUB)
        cur.execute(POSTS_STUB)
        for f in MIGRATIONS:
            cur.execute(f.read_text(encoding="utf-8"))
    counter, tally = QuotaCounter(), Counter()
    started = now()
    day = datetime.now(timezone.utc).date()
    row = eng.run_daily(PgClient(conn), day, api_key=api_key(), countries=COUNTRIES,
                        snapshot_only=True, quota=counter, session=TallySession(tally),
                        rng=random.Random(SEED))
    with conn.cursor() as cur:
        cur.execute("select video_id, channel_id, format, published_at::text from trend_snapshot where day = %s", (day,))
        snap = cur.fetchall()
        cur.execute("select to_jsonb(r) from ingest_run r where day = %s", (day,))
        stored = cur.fetchone()[0]
    save({"limit": counter.limit, "day": day.isoformat(), "started": started, "census_finished": now(),
          "census_row": row, "ingest_run_stored": stored,
          "counter": dict(counter.per_endpoint), "census_counter": dict(counter.per_endpoint),
          "tally": dict(tally), "snapshot": snap, "next_batch": 0, "batches": [], "done": False})
    print(f"census: outcome={row['outcome']} quota_total={row['quota_total']} "
          f"videos={len(snap)} slices_ok={row.get('slices_ok')} 404={row.get('slices_404')}")


def baselines():
    import baseline as bl
    st = load()
    if not st or st["done"]:
        raise SystemExit("nothing to do")
    by_channel = {}
    for vid, ch, fmt, pub in st["snapshot"]:
        by_channel.setdefault(ch, []).append({"video_id": vid, "channel_id": ch, "format": fmt,
                                              "published_at": pub.replace(" ", "T")})
    channels = sorted(by_channel)
    random.Random(SEED).shuffle(channels)
    batches = [channels[i:i + 50] for i in range(0, len(channels), 50)]
    counter, tally = counter_from(st), Counter(st["tally"])
    t0 = time.monotonic()
    key = api_key()
    max_batches = int(os.environ.get("T13_MAX_BATCHES", "0")) or len(batches)
    ran = 0
    while (st["next_batch"] < len(batches) and time.monotonic() - t0 < BUDGET_S
           and ran < max_batches):
        ran += 1
        chs = batches[st["next_batch"]]
        measured = [m for ch in chs for m in by_channel[ch]]
        before = dict(counter.per_endpoint)
        res, rep = bl.baselines_for_videos(measured, key, quota=counter, session=TallySession(tally))
        spent = {k: counter.per_endpoint[k] - before.get(k, 0) for k in counter.per_endpoint}
        rules = Counter(r["rule"] for r in res.values())
        st["batches"].append({"index": st["next_batch"], "channels": len(chs), "videos": len(measured),
                              "units": spent, "resolved": len(res), "rules": dict(rules),
                              "unresolved": len(rep.get("unresolved", [])),
                              "playlist_missing": rep["playlist_missing"],
                              "stop_reason": rep["stop_reason"], "at": now()})
        st["next_batch"] += 1
        st["counter"], st["tally"] = dict(counter.per_endpoint), dict(tally)
        if rep["stop_reason"]:
            st["done"], st["stopped"] = True, rep["stop_reason"]
        save(st)
        if st["done"]:
            break
    if st["next_batch"] >= len(batches):
        st["done"] = True
    st["last_call_finished"] = now()
    save(st)
    print(f"batches done={st['next_batch']}/{len(batches)} total={sum(counter.per_endpoint.values())} "
          f"done={st['done']} stop={st.get('stopped')}")


def report():
    st = load()
    full = [b for b in st["batches"] if not b["stop_reason"]]
    units = Counter()
    for b in full:
        units.update(b["units"])
    ch = sum(b["channels"] for b in full)
    vids = sum(b["videos"] for b in full)
    tally = st["tally"]
    http_by_ep = Counter()
    for k, v in tally.items():
        http_by_ep[k.split(":")[0]] += v
    out = {
        "window_utc": {"start": st["started"], "end": st.get("last_call_finished")},
        "countries": COUNTRIES, "limit": st["limit"], "seed": SEED,
        "counter": st["counter"], "counter_total": sum(st["counter"].values()),
        "http_responses_by_endpoint": dict(http_by_ep), "http_status_tally": tally,
        "census": {"row": st["census_row"], "videos_in_snapshot": len(st["snapshot"]),
                   "units": st["census_counter"]},
        "baselines_completed_batches": {"batches": len(full), "channels": ch, "videos": vids,
                                        "units": dict(units),
                                        "units_per_channel": round(sum(units.values()) / ch, 3) if ch else None,
                                        "units_per_video": round(sum(units.values()) / vids, 3) if vids else None,
                                        "rules": dict(sum((Counter(b["rules"]) for b in full), Counter()))},
        "stopped": st.get("stopped"),
        "batches": st["batches"],
    }
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    {"census": census, "baselines": baselines, "report": report}[sys.argv[1]]()
