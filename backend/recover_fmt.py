"""FMT-2: the records of the past brought under the Short rule.

docs/02-technical-specification.md section 4.10; 01 section 1.1; 08 FMT-2.
Owner decision 04/10/2026 (option A): every record from INDEX_START_DATE
follows YouTube's definition of a Short, paid only with the quota the daily
reading leaves unused. One run a day (pg_cron 06:00 UTC -> POST
/api/recover/run -> run()).

Phase 1, the records never opened: for each day from INDEX_START_DATE to the
last day read before FMT-1, oldest first, the day's entries (present in its
snapshot, absent from the last complete reading before it: entries_of_day)
that the snapshot stores as SHORT and that have no record. videos.list with
the shape; the long-form ones open the record the night would have opened
(vpi_engine._record, baseline.py), entered that day, with reprocessed_at and
baseline_computed_at saying the baseline was read late; then every later day
is replayed for it from the stored snapshots (table, or the archive in
Storage): daily views, VPI, peak, exit. The numerators cost nothing.

Phase 2, the records opened under the duration-only rule (format_rule
'duration_180'), oldest entered_on first. The items of each record's window
in the channel inventory that the recovery must know are read (videos.list
with the shape; duration, views, privacy in the same unit): those still
unknown, and those that were unknown when FMT-1 started (fmt2_null_items)
and that a night has since found long-form, whose duration it did not keep.
The record changes exactly when an item of its window is long-form now and
180 s or shorter: the old rule made it a Short, the new one makes it a
candidate. Unchanged: format_rule only, every other value to the bit
(baseline_v2 is a function of the candidate set). Changed: baseline_v2 on the
new candidate set with views read now, every post_daily VPI from its stored
views, the record's VPI fields; the old values first into fmt2_history, all
in one transaction (fmt2_replace_baseline).

Out of FMT-2 (architect, 04/10/2026): night 1, the records entered before
INDEX_START_DATE (reference only).

Phase 3 (owner's go-ahead, 04/10/2026), after phase 1 and the rest of phase
2, on leftover quota: the records whose window the capped inventory has
dropped since their baseline read. Their channels' uploads are listed again
down to the uploads of that read; the dropped ones are classified with
videos.list in memory (never stored beyond the 150 cap); then the same
judgement as phase 2. Left under the old rule, in fmt2_left and counted
(fmt2_run.records_uncovered), only the records whose check cannot be
complete: an item that had to be classified and videos.list no longer
returns, an item unknown at FMT-1 the channel no longer lists, a channel
whose uploads cannot be listed.
Declared, counted in the run notes: a record a night has opened later under
FMT-1 for a video phase 1 would open earlier keeps the night's record.

Priority to the daily reading: nothing is done unless the reading of the day
that has just closed (UTC) is finished with a complete census and no record
of that day waits for the morning pass. Budget: 9,900 - units already in
quota_ledger for today's Pacific date - 200, on a QuotaCounter that stops at
it. The state lives in the database (fmt2_run, posts): a run stopped at any
call resumes from there.
"""

from __future__ import annotations

import json
import time
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests

import baseline as baseline_mod
import census
import retention
import vpi_core as core
from quota import QUOTA_HARD_MAX, QuotaCounter, QuotaExhausted, record_ledger

PACIFIC = ZoneInfo("America/Los_Angeles")
UNCOUNTED_MARGIN = 200          # calls no run counts: scripts, measurements (02 §4.10)
VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
BLOCK = 50
GROUP = 500                     # phase 1: entries whose shapes are read before one baseline call
PHASE2_RECORDS = 200            # phase 2: records per block
RETRIES = 2
TIMEOUT_S = 30
WAITING = ("quota_stop", "read_failed")
SHAPE_PART = "snippet,contentDetails,player,liveStreamingDetails"     # phase 1
ITEM_PART = "contentDetails,statistics,status,player"                 # phase 2, baseline.py phase 3


class Stop(Exception):
    """403, the brake, or a read that keeps failing: the run ends here."""


# --- the budget -------------------------------------------------------------------


def pacific_day(t: datetime) -> date:
    return t.astimezone(PACIFIC).date()


def ledger_units(client, now: datetime) -> int:
    """Units already spent in the Pacific quota day of `now`."""
    day = pacific_day(now)
    rows = client.table("quota_ledger").select("at,units").execute().data or []
    return sum(int(r["units"]) for r in rows
               if pacific_day(_ts(r["at"])) == day)


def budget(client, now: datetime) -> int:
    return QUOTA_HARD_MAX - ledger_units(client, now) - UNCOUNTED_MARGIN


DEADLINE_MARGIN = timedelta(minutes=5)


def quota_day_end(now: datetime) -> datetime:
    """The end of the Pacific quota day of `now` (Google's reset), in UTC."""
    nxt = datetime.combine(pacific_day(now) + timedelta(days=1), datetime.min.time(), PACIFIC)
    return nxt.astimezone(timezone.utc)


class DayQuota(QuotaCounter):
    """The recovery's counter: its budget belongs to one Pacific quota day, so
    it also stops before that day ends. A unit spent after the reset would be
    counted against the next day, the day of the next reading."""

    def __init__(self, limit, deadline, clock=None):
        super().__init__(limit=limit)
        self.deadline = deadline
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def mark(self, endpoint):
        if self.clock() >= self.deadline:
            self.braked = True
            raise QuotaExhausted(f"the quota day ends at {self.deadline.isoformat()}")
        super().mark(endpoint)


def _ts(v) -> datetime:
    t = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def _d(v) -> date:
    return date.fromisoformat(str(v)[:10])


# --- the gate -------------------------------------------------------------------


def gate(client, now: datetime, runs: list[dict]) -> str | None:
    """None when the recovery may run; otherwise why not."""
    day = now.astimezone(timezone.utc).date() - timedelta(days=1)
    row = next((r for r in runs if _d(r["day"]) == day), None)
    if row is None:
        return f"no reading of {day}"
    if not row.get("finished_at"):
        return f"the reading of {day} is not finished"
    if row.get("census_complete") is not True:
        return f"the census of {day} is not complete"
    waiting = (client.table("posts").select("id").eq("method_version", "v2")
               .eq("entered_on", day.isoformat()).in_("baseline_rule", list(WAITING))
               .execute().data) or []
    if waiting:
        return f"{len(waiting)} records of {day} wait for the morning pass"
    return None


# --- reads ------------------------------------------------------------------------


def _videos(http, quota, api_key, ids, part, sleep):
    """videos.list on <= 50 ids, 1 unit per attempt, marked before it is sent.
    {id: item} for the ids returned; Stop on a 403, the brake or a read that
    still fails after the retries."""
    params = {"part": part, "id": ",".join(ids), "maxResults": BLOCK,
              "maxHeight": core.EMBED_MAX_HEIGHT, "key": api_key}
    why = None
    for attempt in range(RETRIES + 1):
        try:
            quota.mark("videos")
        except QuotaExhausted as e:
            raise Stop(str(e))
        try:
            res = http.get(VIDEOS_URL, params=params, timeout=TIMEOUT_S)
        except requests.RequestException as e:
            why = f"network: {type(e).__name__}"
        else:
            if res.status_code == 200:
                return {it["id"]: it for it in res.json().get("items", [])}
            if res.status_code == 403:
                raise Stop("403 on videos")
            why = f"HTTP {res.status_code}"
            if res.status_code < 500:
                break
        if attempt < RETRIES:
            sleep(2 ** attempt)
    raise Stop(f"videos.list failed: {why}")


def _format_of(item, published_at):
    seconds = core.parse_iso_duration((item.get("contentDetails") or {}).get("duration", ""))
    player = item.get("player") or {}
    w, h = player.get("embedWidth"), player.get("embedHeight")
    return core.formato(seconds, w, h, published_at), seconds, w, h


class Snapshots:
    """Stored censuses, by day: the table while the day is in the retention
    window, the archive in Storage once it has left it (an exact copy,
    02 section 3.1). Each is checked against the count its census recorded.

    Only the view counts are kept between days (about 3 MB a day); a day's
    full rows (about 40 MB) live only while that day is being worked. The
    run of 06/10 kept every full day it had read and the process died
    loading a seventh while it held six (fmt2_run 1)."""

    def __init__(self, client, storage, runs):
        self.client, self.storage = client, storage
        self.seen = {_d(r["day"]): r.get("videos_seen") for r in runs}
        self.views = {}

    def rows(self, day: date) -> dict:
        lines = [r["line"] for r in _rpc_all(self.client, "snapshot_export",
                                             {"p_day": day.isoformat()}, "video_id")]
        if not lines:
            try:
                lines = retention.decode(self.storage.get(f"{retention.PREFIX}/{day.isoformat()}.jsonl.gz"))
            except retention.ArchiveError as e:
                raise Stop(f"the snapshot of {day} is neither in the table nor readable "
                           f"in the archive: {e}")
        rows = {}
        for line in lines:
            x = json.loads(line)
            rows[x["video_id"]] = x
        del lines
        if self.seen.get(day) is not None and len(rows) != self.seen[day]:
            raise Stop(f"the snapshot of {day} holds {len(rows)} videos, "
                       f"its census counted {self.seen[day]}")
        self.views.setdefault(day, {v: x.get("views") for v, x in rows.items()})
        return rows

    def views_of(self, day: date) -> dict:
        if day not in self.views:
            self.rows(day)
        return self.views[day]


def _ledger_open(client):
    """The run's quota_ledger row, opened at 0 before the first unit and kept
    at the run's total at every save: a process that dies leaves its units
    counted up to the last save (the run of 06/10 died with none). None when
    it cannot be written; the run then appends its row at the end."""
    try:
        return client.table("quota_ledger").insert({"source": "recovery", "units": 0}).execute().data[0]["id"]
    except Exception:                                    # noqa: BLE001
        return None


def _ledger_set(client, ledger_id, units) -> str | None:
    try:
        client.table("quota_ledger").update({"units": int(units)}).eq("id", ledger_id).execute()
        return None
    except Exception as e:                               # noqa: BLE001
        return f"quota_ledger not updated: {type(e).__name__}: {str(e)[:200]}"


def _rpc_all(client, fn, params, order):
    out, start = [], 0
    while True:
        page = (client.rpc(fn, params).order(order)
                .range(start, start + census.RPC_PAGE - 1).execute().data) or []
        out.extend(page)
        if len(page) < census.RPC_PAGE:
            return out
        start += census.RPC_PAGE


# --- the run ----------------------------------------------------------------------


def run(client, *, api_key, now=None, storage=None, session=None, sleep=time.sleep,
        clock=None) -> dict:
    """One recovery run. {"skipped": reason} when it does nothing. `clock`
    (tests) answers the current time for the quota-day deadline; by default
    the run's own start plus the time elapsed."""
    now = now or datetime.now(timezone.utc)
    if clock is None:
        t0 = time.monotonic()
        clock = lambda: now + timedelta(seconds=time.monotonic() - t0)   # noqa: E731
    runs = sorted(client.table("ingest_run").select("*").execute().data or [], key=lambda r: str(r["day"]))
    why = gate(client, now, runs)
    if why:
        return {"skipped": why}
    first_fmt1 = next((_d(r["day"]) for r in runs if "unknown_shape" in (r.get("discards") or {})), None)
    if first_fmt1 is None:
        return {"skipped": "no reading under FMT-1 yet"}
    history = client.table("fmt2_run").select("*").execute().data or []
    done_days = {_d(x) for h in history for x in (h.get("days_done") or [])}
    days = [_d(r["day"]) for r in runs
            if core.INDEX_START_DATE <= str(r["day"])[:10] < first_fmt1.isoformat()]
    todo = [d for d in days if d not in done_days]
    known_left = _left_ids(client)
    left = [r for r in (client.table("posts").select("id").eq("method_version", "v2")
                        .eq("format_rule", core.FORMAT_RULE_BEFORE).gte("entered_on", core.INDEX_START_DATE)
                        .limit(len(known_left) + 1).execute().data or []) if r["id"] not in known_left]
    if not todo and not left:
        return {"skipped": "nothing to do: every day of phase 1 done, no record under the old rule"}
    limit = budget(client, now)
    if limit <= 0:
        return {"skipped": f"no budget left today ({limit})"}

    deadline = quota_day_end(now) - DEADLINE_MARGIN
    if now >= deadline:
        return {"skipped": f"too close to the end of the quota day ({deadline.isoformat()})"}
    quota = DayQuota(limit, deadline, clock)
    http = session or requests.Session()
    storage = storage if storage is not None else retention.SupabaseStorage.from_env()
    cursor = next((h.get("cursor") for h in sorted(history, key=lambda h: h["id"], reverse=True)
                   if h.get("cursor")), None)
    st = {"days_done": [], "records_checked": 0, "records_opened": 0, "baselines_changed": 0,
          "phase": 1 if todo else 2, "cursor": cursor, "notes": [f"budget {limit} units"]}
    me = client.table("fmt2_run").insert({"started_at": now.isoformat(), "phase": st["phase"],
                                          "notes": "running"}).execute().data[0]
    ledger = _ledger_open(client)

    def save(final=False):
        row = {"days_done": [d.isoformat() for d in st["days_done"]],
               "records_checked": st["records_checked"], "records_opened": st["records_opened"],
               "baselines_changed": st["baselines_changed"], "phase": st["phase"],
               "records_uncovered": st.get("records_uncovered"),
               "phase3_pages": st.get("phase3_pages"), "phase3_videos": st.get("phase3_videos"),
               "cursor": st["cursor"], "units": quota.total, "notes": "; ".join(st["notes"])}
        if final:
            row["finished_at"] = datetime.now(timezone.utc).isoformat()
        client.table("fmt2_run").update(row).eq("id", me["id"]).execute()
        if ledger is not None and not final:
            _ledger_set(client, ledger, quota.total)

    snaps = Snapshots(client, storage, runs)
    try:
        for d in todo:
            _phase1_day(client, d, runs, snaps, st, quota, http, api_key, sleep, now, save)
            st["days_done"].append(d)
            st["cursor"] = None
            save()
        st["phase"] = 2
        _phase2(client, st, quota, http, api_key, sleep, now, save)
        st["phase"] = 3
        _phase3(client, st, quota, http, api_key, sleep, now, save)
        st["notes"].append("finished: nothing left within reach")
    except Stop as e:
        st["notes"].append(f"stopped: {e}")
    except Exception as e:                               # noqa: BLE001
        st["notes"].append(f"failed: {type(e).__name__}: {str(e)[:300]}")
        raise
    finally:
        if st.get("phase3_pages") is not None:
            st["notes"].append(f"phase 3: {st['phase3_pages']} playlist pages, "
                               f"{st['phase3_videos']} videos.list calls")
        try:
            st["records_uncovered"] = len(_left_ids(client))
            st["notes"].append(f"{st['records_uncovered']} records left under the old rule in all "
                               f"(fmt2_left); this run: {st.get('left_gone', 0)} with an item no longer "
                               f"returned, {st.get('left_unlisted', 0)} whose uploads cannot be listed")
        except Exception as e:                           # noqa: BLE001
            st["notes"].append(f"fmt2_left not read: {type(e).__name__}")
        st["notes"].append(f"{quota.total} units")
        failed = (record_ledger(client, "recovery", quota.total) if ledger is None
                  else _ledger_set(client, ledger, quota.total))
        if failed:
            st["notes"].append(failed)
        save(final=True)
    return {"units": quota.total, **{k: st.get(k) for k in ("records_checked", "records_opened",
                                                            "baselines_changed", "phase",
                                                            "records_uncovered")},
            "days_done": [d.isoformat() for d in st["days_done"]], "notes": st["notes"]}


# --- phase 1 ----------------------------------------------------------------------


def _phase1_day(client, d, runs, snaps, st, quota, http, api_key, sleep, now, save):
    """Open, as of day d, the long-form records the duration-only rule left out."""
    import vpi_engine as eng                     # the night's own record writer

    run_d = next(r for r in runs if _d(r["day"]) == d)
    ref = max((_d(r["day"]) for r in runs if _d(r["day"]) < d and r.get("census_complete") is True),
              default=None)
    if ref is None:
        return                                   # day 0: no entry is observable
    rows = snaps.rows(d)
    before = set(snaps.views_of(ref))
    gap = 0 if ref == d - timedelta(days=1) else (d - ref).days
    entry = {"gap_days": gap, "entry_certain": ref == d - timedelta(days=1)}
    after = (st["cursor"] or {}).get("after") if (st["cursor"] or {}).get("day") == d.isoformat() else None
    cands = sorted(v for v, x in rows.items()
                   if v not in before and x.get("format") == core.FORMATO_SHORT
                   and (after is None or v > after))
    later = [_d(r["day"]) for r in runs if _d(r["day"]) > d and r.get("finished_at")]
    observed = str(run_d["started_at"])
    for g in range(0, len(cands), GROUP):
        group = cands[g:g + GROUP]
        have = {}
        for i in range(0, len(group), 1000):
            for p in (client.table("posts").select("id,external_post_id,entered_on,duration_s")
                      .in_("external_post_id", group[i:i + 1000]).execute().data or []):
                have[p["external_post_id"]] = p
        mine = [have[v] for v in group if v in have and str(have[v]["entered_on"])[:10] == d.isoformat()
                and have[v].get("duration_s") is not None]
        elsewhere = [v for v in group if v in have and have[v] not in mine]
        if elsewhere:
            st["notes"].append(f"{d}: {len(elsewhere)} entries already have a record of another day")
        ask = [v for v in group if v not in have]
        longs = {}
        for i in range(0, len(ask), BLOCK):
            items = _videos(http, quota, api_key, ask[i:i + BLOCK], SHAPE_PART, sleep)
            for vid, it in items.items():
                fmt, seconds, w, h = _format_of(it, rows[vid].get("published_at"))
                if fmt != core.FORMATO_LONG:
                    continue
                if rows[vid].get("views") is None:
                    continue                             # as the night: no views, no record
                sn = it.get("snippet") or {}
                longs[vid] = {"channel_id": rows[vid]["channel_id"], "format": core.FORMATO_LONG,
                              "published_at": rows[vid]["published_at"], "views": rows[vid]["views"],
                              "countries": set(rows[vid]["countries"]),
                              "categories": set(rows[vid]["categories"]),
                              "title": sn.get("title"), "channel_title": sn.get("channelTitle"),
                              "duration_s": seconds, "shape": core.shape_of(w, h),
                              "live": bool((it.get("liveStreamingDetails") or {}).get("actualStartTime"))}
        st["records_checked"] += len(ask)
        opened = _open(client, d, longs, entry, observed, quota, http, api_key, sleep, now, eng)
        st["records_opened"] += len(opened)
        replay = opened + [(p["id"], p["external_post_id"]) for p in mine]
        if replay:
            _replay(client, d, replay, later, runs, snaps, eng)
        st["cursor"] = {"day": d.isoformat(), "after": group[-1]}
        save()


def _open(client, d, longs, entry, observed, quota, http, api_key, sleep, now, eng):
    """Baselines (baseline.py, window anchored to each video's publication,
    read now) and the records, as the night of d would have written them."""
    if not longs:
        return []
    measured = [{"video_id": v, "channel_id": x["channel_id"], "format": x["format"],
                 "published_at": x["published_at"]} for v, x in sorted(longs.items())]
    res, brep = baseline_mod.baselines_for_videos(
        measured, api_key, session=http, sleep=sleep, quota=quota,
        inventory=baseline_mod.SupabaseInventory(client), today=now.date())
    if brep["stop_reason"]:
        raise Stop(f"baselines: {brep['stop_reason']}")
    if brep.get("unresolved"):
        raise Stop(f"baselines: {len(brep['unresolved'])} unresolved after the retries")
    stamp = datetime.now(timezone.utc).isoformat()
    records = [eng._record(v, longs[v], entry, res[v], brep["channels"].get(longs[v]["channel_id"], {}),
                           d, observed, stamp, stamp) for v in sorted(res)]
    out = []
    for i in range(0, len(records), eng.WRITE_BATCH):
        for r in client.table("posts").insert(records[i:i + eng.WRITE_BATCH]).execute().data or []:
            out.append((r["id"], r["external_post_id"]))
    return out


def _replay(client, d, recs, later, runs, snaps, eng):
    """Day d and every later day for these records, from the stored
    snapshots, as the nights did: views and VPI where the video is present
    with a view count, the exit on the first complete reading without it."""
    rows = (client.table("posts").select("id,external_post_id,baseline_score,status")
            .in_("id", [p for p, _ in recs]).execute().data) or []
    base = {r["id"]: (float(r["baseline_score"]) if r["baseline_score"] is not None else None) for r in rows}
    active = {r["id"]: r["external_post_id"] for r in rows}
    complete = {_d(r["day"]): r.get("census_complete") is True for r in runs}
    applied = {p: [] for p in active}
    for day in [d] + later:
        views = snaps.views_of(day)
        payload, gone = [], []
        for pid, vid in active.items():
            if vid in views:
                if views[vid] is not None:
                    payload.append({"post_id": str(pid), "views": float(views[vid]),
                                    **eng._vpi_fields(float(views[vid]), base[pid])})
                    applied[pid].append(float(views[vid]))
            elif day != d and complete.get(day):
                gone.append(pid)
        for i in range(0, len(payload), eng.WRITE_BATCH):
            client.rpc("apply_daily_views", {"d": day.isoformat(),
                                             "rows": payload[i:i + eng.WRITE_BATCH]}).execute()
        for pid in gone:
            n = len(client.table("post_daily").select("day").eq("post_id", pid).execute().data or [])
            client.table("posts").update({
                "status": "CLOSED", "left_on": day.isoformat(), "days_charting": n,
                "views_final": applied[pid][-1] if applied[pid] else None,
            }).eq("id", pid).eq("status", "ACTIVE").execute()
            active.pop(pid)


# --- phase 2 ----------------------------------------------------------------------


def covers(inv, lo) -> bool:
    """The inventory holds every upload of the channel back to `lo`. A capped
    inventory holds the 150 most recent uploads, so it covers `lo` only when
    the oldest of them is not newer; an uncapped one, when it has been read
    back past `lo` or to the end of the playlist."""
    if inv is None:
        return False
    if inv.get("capped"):
        held = baseline_mod._recent(inv)
        return bool(held) and held[-1][1][0] <= lo
    cbt = inv.get("covered_back_to")
    return bool(inv.get("ended")) or (cbt is not None and cbt <= lo)


def nothing_newer(inv, read_epoch) -> bool:
    """The inventory holds no upload published after the record's baseline
    read. It drops an old item only when it adds a newer one, so nothing was
    dropped since: it holds exactly the candidates of that read (the 150 cap
    applied then, and is the rule)."""
    return inv is not None and all(e <= read_epoch for e, _ in inv["items"].values())


def baseline_read_epoch(r) -> int:
    """When the record's baseline was read: baseline_computed_at, else the
    earliest the reading of its day could have read it (23:59 UTC)."""
    if r.get("baseline_computed_at"):
        return baseline_mod._epoch(r["baseline_computed_at"])
    d = _d(r["entered_on"])
    return int(datetime(d.year, d.month, d.day, 23, 59, tzinfo=timezone.utc).timestamp())


def _left_ids(client) -> set:
    """Records the recovery has left under the old rule (fmt2_left)."""
    return {str(r["post_id"]) for r in (client.table("fmt2_left").select("post_id").execute().data or [])}


def _leave(client, recs, reason, st):
    if not recs:
        return
    client.table("fmt2_left").upsert([{"post_id": r["id"], "reason": reason} for r in recs],
                                     on_conflict="post_id").execute()
    st["left_" + reason] = st.get("left_" + reason, 0) + len(recs)


def _bounds(r):
    ref = baseline_mod._epoch(r["created_at"])
    return ref - core.BASELINE_MAX_AGE_DAYS * 86400, ref - core.BASELINE_MIN_AGE_DAYS * 86400


def _whole(inv, r) -> bool:
    """The inventory holds the record's window in full: it reaches the
    window's start, or holds no upload published after the record's
    baseline read (it drops an old item only when it adds a newer one, so
    it holds exactly that read's candidates)."""
    return covers(inv, _bounds(r)[0]) or nothing_newer(inv, baseline_read_epoch(r))


def _judge(client, recs, pools, held, nulls, read, gone, store, invs, quota, http, api_key, sleep, st):
    """Phase 2's judgement on records whose window is known in full.

    pools[r.id]: [(epoch, video_id)], the candidates of the record's
    baseline read (its 150 most recent uploads); held[v]: the inventory
    format of v, absent when the inventory no longer holds v (dropped by the
    cap: phase 3, classified in memory, never stored). What must be known is
    read: unknown formats, dropped items, and items unknown at FMT-1 a night
    has since found long-form (their duration was not kept). A record
    changes when an item of its window is long-form now and 180 s or
    shorter. Not classifiable, left under the old rule in fmt2_left: an item
    that had to be read and videos.list no longer returns, or an item
    unknown at FMT-1 that the channel no longer lists.
    """
    def window(r):
        lo, hi = _bounds(r)
        return [(e, v) for e, v in pools[r["id"]] if lo <= e <= hi and v != r["external_post_id"]]

    def must_know(r, v):
        f = held.get(v, "DROPPED")
        return f is None or f == "DROPPED" or (f == core.FORMATO_LONG and v in nulls.get(r["channel_id"], {}))

    need, owner, epoch_of = set(), {}, {}
    for r in recs:
        for e, v in window(r):
            owner[v], epoch_of[v] = r["channel_id"], e
            if v not in read and v not in gone and must_know(r, v):
                need.add(v)
    _read_items(sorted(need), owner, epoch_of, invs, read, gone, store, quota, http, api_key, sleep)

    def lost(r):
        lo, hi = _bounds(r)
        if any(v in gone for e, v in window(r) if must_know(r, v)):
            return True
        listed = {v for _, v in pools[r["id"]]}
        return any(v not in listed and e is not None and lo <= e <= hi and v != r["external_post_id"]
                   for v, e in nulls.get(r["channel_id"], {}).items())

    same, changed, out = [], [], []
    for r in recs:
        if lost(r):
            out.append(r)
            continue
        hit = any(v in read and read[v][0] == core.FORMATO_LONG and read[v][1] <= core.SHORT_MAX_SECONDS
                  for _, v in window(r))
        (changed if hit else same).append(r)
    _leave(client, out, "gone", st)
    if same:
        _mark(client, [r["id"] for r in same])
        st["records_checked"] += len(same)
    for r in changed:
        def fmt(v):
            return read[v][0] if v in read else held.get(v)
        ask = sorted(v for _, v in window(r) if fmt(v) == core.FORMATO_LONG and v not in read and v not in gone)
        _read_items(ask, owner, epoch_of, invs, read, gone, store, quota, http, api_key, sleep)
        samples = [{"video_id": v, "published_at": baseline_mod._iso(e), "views": read[v][2]}
                   for e, v in window(r) if v in read and read[v][0] == core.FORMATO_LONG]
        res = core.baseline_v2(samples, r["external_post_id"], r["created_at"])
        _replace(client, r, res)
        st["records_checked"] += 1
        st["baselines_changed"] += 1


def _records(client, skip, n):
    return (client.table("posts")
            .select("id,external_post_id,channel_id,created_at,entered_on,baseline_computed_at,"
                    "baseline_rule,engagement_score")
            .eq("method_version", "v2").eq("format_rule", core.FORMAT_RULE_BEFORE)
            .gte("entered_on", core.INDEX_START_DATE)
            .order("entered_on").order("id")
            .range(skip, skip + n - 1).execute().data) or []


def _nulls(client, chans):
    out = {}
    for i in range(0, len(chans), 200):
        for x in (client.table("fmt2_null_items").select("channel_id,ids,epochs")
                  .in_("channel_id", chans[i:i + 200]).execute().data or []):
            out[x["channel_id"]] = dict(zip(x["ids"], x.get("epochs") or [None] * len(x["ids"])))
    return out


def _phase2(client, st, quota, http, api_key, sleep, now, save):
    """Records from INDEX_START_DATE under the duration-only rule (night 1,
    before the series, is out of FMT-2: architect, 04/10/2026) whose window
    the inventory holds in full (_whole). The others wait for phase 3."""
    store = baseline_mod.SupabaseInventory(client)
    read, gone = {}, set()
    left = _left_ids(client)
    skip = 0
    seen = set()                    # a record is judged at most once per run, whatever happens
    st["phase3_waiting"] = 0
    while True:
        recs = _records(client, skip, PHASE2_RECORDS)
        if not recs:
            break
        again = [r for r in recs if r["id"] in seen]
        if again:                   # still under the old rule after its judgement: never loop on it
            skip += len(again)
            st["notes"].append(f"{len(again)} records still under the old rule after their judgement")
            recs = [r for r in recs if r["id"] not in seen]
            if not recs:
                continue
        seen.update(r["id"] for r in recs)
        no_base = [r["id"] for r in recs if r["baseline_rule"] in WAITING]
        if no_base:                 # no baseline, no candidate set: nothing can change
            _mark(client, no_base)
            st["records_checked"] += len(no_base)
        recs = [r for r in recs if r["baseline_rule"] not in WAITING]
        invs = store.load(sorted({r["channel_id"] for r in recs}))
        waiting = [r for r in recs if str(r["id"]) not in left and not _whole(invs.get(r["channel_id"]), r)]
        known = [r for r in recs if str(r["id"]) in left]
        recs = [r for r in recs if str(r["id"]) not in left and _whole(invs.get(r["channel_id"]), r)]
        st["phase3_waiting"] += len(waiting)
        pools, held = {}, {}
        for r in recs:
            inv = invs[r["channel_id"]]
            pools[r["id"]] = [(e, v) for v, (e, _) in baseline_mod._recent(inv)]
            held.update({v: f for v, (_, f) in inv["items"].items()})
        before = st.get("left_gone", 0)
        _judge(client, recs, pools, held, _nulls(client, sorted({r["channel_id"] for r in recs})),
               read, gone, store, invs, quota, http, api_key, sleep, st)
        skip += len(waiting) + len(known) + st.get("left_gone", 0) - before
        save()


PLAYLIST_URL = "https://www.googleapis.com/youtube/v3/playlistItems"
CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"


def _get(http, quota, endpoint, url, params, sleep):
    """One counted call besides videos.list: a dict, None on a 404; Stop on a
    403, the brake, or a read that keeps failing."""
    why = None
    for attempt in range(RETRIES + 1):
        try:
            quota.mark(endpoint)
        except QuotaExhausted as e:
            raise Stop(str(e))
        try:
            res = http.get(url, params=params, timeout=TIMEOUT_S)
        except requests.RequestException as e:
            why = f"network: {type(e).__name__}"
        else:
            if res.status_code == 200:
                return res.json()
            if res.status_code == 404:
                return None
            if res.status_code == 403:
                raise Stop(f"403 on {endpoint}")
            why = f"HTTP {res.status_code}"
            if res.status_code < 500:
                break
        if attempt < RETRIES:
            sleep(2 ** attempt)
    raise Stop(f"{endpoint} failed: {why}")


def _phase3(client, st, quota, http, api_key, sleep, now, save):
    """The records whose window the capped inventory has dropped since their
    baseline read (owner's go-ahead, 04/10/2026). Per channel: its uploads
    playlist read again from the newest until it lists, for the channel's
    earliest baseline read, the 150 uploads published by then (or passes
    every window's start, or ends). Each record's pool is the 150 most
    recent uploads published by its own read: the candidates of that read.
    The items the inventory dropped are classified with videos.list in
    memory, never stored in channel_inventory beyond the 150 cap; then phase
    2's judgement. Declared: an upload deleted from the channel since the
    read is not listed any more and nothing shows it, except an item unknown
    at FMT-1, which fmt2_null_items keeps."""
    store = baseline_mod.SupabaseInventory(client)
    read, gone = {}, set()
    left = _left_ids(client)
    pending, skip = [], 0
    while True:                                          # what phase 2 left to us
        recs = _records(client, skip, 1000)
        if not recs:
            break
        skip += len(recs)
        recs = [r for r in recs if str(r["id"]) not in left and r["baseline_rule"] not in WAITING]
        invs = store.load(sorted({r["channel_id"] for r in recs}))
        pending += [r for r in recs if not _whole(invs.get(r["channel_id"]), r)]
    by_ch = {}
    for r in pending:
        by_ch.setdefault(r["channel_id"], []).append(r)
    st.setdefault("phase3_pages", 0)
    st.setdefault("phase3_videos", 0)
    chans = sorted(by_ch)
    for i in range(0, len(chans), BLOCK):
        block = chans[i:i + BLOCK]
        data = _get(http, quota, "channels", CHANNELS_URL,
                    {"part": "contentDetails", "id": ",".join(block), "maxResults": BLOCK,
                     "key": api_key}, sleep) or {}
        uploads = {it["id"]: ((it.get("contentDetails") or {}).get("relatedPlaylists") or {}).get("uploads")
                   for it in data.get("items", [])}
        invs = store.load(block)
        nulls = _nulls(client, block)
        for ch in block:
            recs = by_ch[ch]
            if not uploads.get(ch) or ch not in invs:
                _leave(client, recs, "unlisted", st)
                continue
            first_read = min(baseline_read_epoch(r) for r in recs)
            oldest_lo = min(_bounds(r)[0] for r in recs)
            listed, token, missing = [], None, False
            while True:
                params = {"part": "contentDetails", "maxResults": BLOCK, "playlistId": uploads[ch],
                          "key": api_key}
                if token:
                    params["pageToken"] = token
                page = _get(http, quota, "playlist", PLAYLIST_URL, params, sleep)
                st["phase3_pages"] += 1
                if page is None:
                    missing = True
                    break
                for it in page.get("items", []):
                    cd = it.get("contentDetails") or {}
                    if cd.get("videoId") and cd.get("videoPublishedAt"):
                        listed.append((baseline_mod._epoch(cd["videoPublishedAt"]), cd["videoId"]))
                token = page.get("nextPageToken")
                if not token or sum(1 for e, _ in listed if e <= first_read) >= baseline_mod.INVENTORY_MAX \
                        or (listed and min(e for e, _ in listed) < oldest_lo):
                    break
            if missing:
                _leave(client, recs, "unlisted", st)
                continue
            listed.sort(key=lambda x: (x[0], x[1]), reverse=True)
            pools = {r["id"]: [x for x in listed if x[0] <= baseline_read_epoch(r)][:baseline_mod.INVENTORY_MAX]
                     for r in recs}
            held = {v: f for v, (_, f) in invs[ch]["items"].items()}
            units = quota.per_endpoint["videos"]
            try:
                _judge(client, recs, pools, held, nulls, read, gone, store, invs, quota, http, api_key,
                       sleep, st)
            finally:
                st["phase3_videos"] += quota.per_endpoint["videos"] - units
            save()


def _read_items(ids, owner, epoch_of, invs, read, gone, store, quota, http, api_key, sleep):
    """Phase-3 read of baseline.py: duration, shape, views, privacy, 1 unit per
    50 ids. For an item the inventory holds, the format is stored in it
    (formato(); UNKNOWN and no duration as NONE, not samples), and an item
    not returned or not public is removed, as a night removes it. An item the
    inventory no longer holds (dropped by the cap) is classified in memory
    only. Each block is saved before the next is sent."""
    for i in range(0, len(ids), BLOCK):
        block = ids[i:i + BLOCK]
        items = _videos(http, quota, api_key, block, ITEM_PART, sleep)
        touched = set()
        for v in block:
            ch = owner[v]
            inv = invs.get(ch)
            it = items.get(v)
            held = inv["items"].get(v) if inv else None
            if it is None or (it.get("status") or {}).get("privacyStatus", "public") != "public":
                gone.add(v)
                if held is not None:
                    inv["items"].pop(v, None)
                    touched.add(ch)
                continue
            fmt, seconds, _, _ = _format_of(it, baseline_mod._iso(held[0] if held else epoch_of[v]))
            fmt = fmt if fmt in (core.FORMATO_SHORT, core.FORMATO_LONG) else "NONE"
            if held is not None:
                held[1] = fmt
                touched.add(ch)
            raw = (it.get("statistics") or {}).get("viewCount")
            read[v] = (fmt, seconds, int(raw) if raw is not None else None)
        if touched:
            store.save({ch: invs[ch] for ch in touched})


def _mark(client, ids):
    for i in range(0, len(ids), 200):
        (client.table("posts").update({"format_rule": core.FORMAT_RULE})
         .in_("id", ids[i:i + 200]).eq("format_rule", core.FORMAT_RULE_BEFORE).execute())


def _replace(client, r, res):
    """The new baseline, every daily VPI from its stored views, the record's
    VPI fields: one transaction, the old values kept first (fmt2_history)."""
    import vpi_engine as eng
    days = sorted((client.table("post_daily").select("day,views").eq("post_id", r["id"])
                   .execute().data or []), key=lambda x: str(x["day"]))
    base = res["baseline"]
    daily, peak, peak_on = [], None, None
    for x in days:
        vf = eng._vpi_fields(float(x["views"]), base)
        daily.append({"day": str(x["day"])[:10], "vpi_ratio": vf["vpi_ratio"], "vpi_level": vf["vpi_level"]})
        if vf["vpi_ratio"] is not None and (peak is None or vf["vpi_ratio"] > peak):
            peak, peak_on = vf["vpi_ratio"], str(x["day"])[:10]
    last = float(days[-1]["views"]) if days else (
        float(r["engagement_score"]) if r.get("engagement_score") is not None else None)
    current = eng._vpi_fields(last, base)
    payload = {"baseline_score": base, "baseline_samples": res["samples"], "baseline_rule": res["rule"],
               "baseline_span_days": res["span_days"], "baseline_video_ids": res["video_ids"],
               "baseline_computed_at": datetime.now(timezone.utc).isoformat(),
               **current, "vpi_max": peak, "vpi_max_on": peak_on, "daily": daily}
    client.rpc("fmt2_replace_baseline", {"p_post_id": str(r["id"]), "p": payload}).execute()
