"""The v2 ingestion engine: one reading a day (docs/01 section 4).

run_daily() is the daily procedure: census of the category charts ->
snapshot -> entries (baseline computed and frozen) -> today's views for every
charting record -> exits (complete runs only) -> run report in ingest_run.
It is triggered only by POST /api/ingest/run (pg_cron, 23:59 UTC): there is
no background scheduler.

The v1 entry point fetch_and_ingest_real_youtube_content() is kept, unchanged,
in archive/backend/vpi_engine_v1.py for one release (08 T-10, rollback).
Kept here for v1 only: get_channel_video_samples() and
fetch_channels_metadata(), used by refresh_showcase.py on the v1 records. The
second platform's branch was archived at T-11, under archive/backend/.
"""
import os
import json
import time
import secrets
import random
import requests
import statistics
import re
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client

from vpi_core import (
    BASELINE_MAX_AGE_DAYS,
    BASELINE_MIN_AGE_DAYS,
    CAMPAIGN_DAYS,
    MIN_BASELINE_SAMPLES,
    MIN_BASELINE_VIEWS,
    baseline_from_samples,
    MIN_VPI_FOR_INGESTION,
    FORMATO_SHORT,
    FORMATO_LONG,
    formato_da_durata,   # v1 only (get_channel_video_samples)
    FORMAT_RULE,
    TTLCache,
    age_in_days,
    calculate_vpi_ratio,
    get_vpi_metadata,
    is_short_duration,
    parse_iso_duration,
    round_vpi,
)

from log_iosa import configura, prendi

log = prendi(__name__)


# Load environment variables
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)

SUPABASE_URL = os.getenv("NEXT_PUBLIC_SUPABASE_URL") or os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY") or os.getenv("SUPABASE_KEY")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

# YouTube OAuth 2.0 Credentials for dynamic token generation
YOUTUBE_CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID")
YOUTUBE_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET")
YOUTUBE_REFRESH_TOKEN = os.getenv("YOUTUBE_REFRESH_TOKEN")


BASE_DOMAIN = os.getenv("NEXT_PUBLIC_SITE_URL", "https://iosaresearch.org")
OPTOUT_EMAIL = os.getenv("OPTOUT_EMAIL", "iosa.research.lab@gmail.com")

# Maximum subscriber threshold (increased to 1.5M to include small/medium channels)
MAX_SUBSCRIBERS = 1_500_000 
MIN_SUBSCRIBERS = 1_000

# Countries and categories: one definition, in census.py (T-07). 19 and 27
# are gone: they returned 404 in all 34 countries.
from census import CATEGORY_MAP, TARGET_COUNTRIES  # noqa: E402

# I template di commento automatico su YouTube sono stati rimossi il 20/09/2026.
# Promettevano 'certified report', 'accredited award' e 'official physical trophy':
# linguaggio falso (non accreditiamo nessuno, non esiste nessun premio fisico) e
# commento automatico sotto i video altrui, cioe' spam secondo le regole di YouTube.
# Il contatto con i creator passa solo dall'outreach via email, dove il testo e' scritto
# a mano, porta la data di rilevazione e dice che non c'e' niente da pagare.

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("❌ Missing Supabase credentials in environment variables.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# ------------------------------------------------ v1 only (refresh_showcase.py)

def get_channel_video_samples(channel_id: str):
    """Campioni per la baseline, separati per formato.

    Costa 3 unita' di quota (channels + playlistItems + videos) e viene fatta
    una volta sola per canale. Le ultime 50 pubblicazioni arrivano tutte nella
    stessa risposta, Short e video lunghi insieme: prima i video lunghi
    venivano scartati qui e la quota spesa per leggerli buttata via. Adesso si
    tengono entrambi i gruppi, quindi estendere l'indice ai video lunghi non
    costa una sola unita' in piu'.

    Restituisce {"SHORT": [...], "LONG": [...]} con dizionari
    {video_id, views, age_days}, oppure None se la chiamata non e' andata a
    buon fine. Dizionario con liste vuote e None sono cose diverse: il primo
    significa "nessun video utile", il secondo "non lo so", e solo il secondo
    deve lasciare intatto un dato gia' salvato.
    """
    try:
        ch_url = f"https://www.googleapis.com/youtube/v3/channels?part=contentDetails&id={channel_id}&key={YOUTUBE_API_KEY}"
        ch_res = requests.get(ch_url, timeout=10)
        if ch_res.status_code != 200:
            return None
        ch_items = ch_res.json().get("items", [])
        if not ch_items:
            return None

        uploads_playlist_id = ch_items[0].get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
        if not uploads_playlist_id:
            return None

        playlist_url = f"https://www.googleapis.com/youtube/v3/playlistItems?part=contentDetails&playlistId={uploads_playlist_id}&maxResults=50&key={YOUTUBE_API_KEY}"
        pl_res = requests.get(playlist_url, timeout=10)
        if pl_res.status_code != 200:
            return None
        pl_items = pl_res.json().get("items", [])
        if not pl_items:
            return []

        video_ids = [
            item["contentDetails"]["videoId"]
            for item in pl_items
            if "contentDetails" in item and "videoId" in item["contentDetails"]
        ]
        if not video_ids:
            return []

        stats_url = (
            "https://www.googleapis.com/youtube/v3/videos"
            f"?part=snippet,contentDetails,statistics&id={','.join(video_ids)}&key={YOUTUBE_API_KEY}"
        )
        stats_res = requests.get(stats_url, timeout=10)
        if stats_res.status_code != 200:
            return None

        now = datetime.now(timezone.utc)
        campioni = {FORMATO_SHORT: [], FORMATO_LONG: []}
        for v_item in stats_res.json().get("items", []):
            duration = parse_iso_duration(v_item.get("contentDetails", {}).get("duration", ""))
            formato = formato_da_durata(duration)
            if formato is None:
                continue
            views_str = v_item.get("statistics", {}).get("viewCount")
            if views_str is None:
                continue
            age_days = age_in_days(v_item.get("snippet", {}).get("publishedAt"), now)
            if age_days is None:
                continue
            campioni[formato].append({
                "video_id": v_item.get("id"),
                "views": float(views_str),
                "age_days": age_days,
            })
        return campioni
    except Exception:
        return None


def fetch_channels_metadata(channel_ids: list) -> dict:
    """Iscritti e handle reale dei canali. Una chiamata ogni 50 id, 1 unita' di quota."""
    if not channel_ids:
        return {}
    
    # L'endpoint channels accetta al massimo 50 id per chiamata: passandone di
    # piu' YouTube risponde 400 e la vecchia versione restituiva {} in silenzio,
    # per cui quasi ogni record finiva con la sentinella 999_999_999 al posto
    # degli iscritti. Si spezza quindi in blocchi da 50.
    unici = list(set(channel_ids))
    channels_data = {}

    for inizio in range(0, len(unici), 50):
        blocco = unici[inizio:inizio + 50]
        ids_str = ",".join(blocco)
        url = (
            "https://www.googleapis.com/youtube/v3/channels"
            f"?part=snippet,statistics&id={ids_str}&key={YOUTUBE_API_KEY}"
        )
        try:
            res = requests.get(url, timeout=10)
            if res.status_code != 200:
                log.info(f"[SUBS] channels.list ha risposto {res.status_code} "
                      f"per un blocco di {len(blocco)} canali: iscritti ignoti.")
                continue
        except Exception as exc:
            log.warning(f"[SUBS] channels.list non raggiungibile: {exc}")
            continue

        for item in res.json().get("items", []):
            stats = item.get("statistics", {})
            # Quando il canale nasconde il numero di iscritti si scrive None:
            # una sentinella numerica verrebbe letta come un valore vero.
            if stats.get("hiddenSubscriberCount") or "subscriberCount" not in stats:
                subs = None
            else:
                subs = int(stats["subscriberCount"])
            # customUrl e' l'handle vero del canale ("@qesek"). Finora l'handle
            # veniva inventato dal titolo togliendo gli spazi, e per molti canali
            # punta a un canale diverso o inesistente.
            handle = (item.get("snippet", {}).get("customUrl") or "").strip()
            channels_data[item["id"]] = {
                "subscribers": subs,
                "handle": handle if handle.startswith("@") else None,
            }

    return channels_data

# ==============================================================================
# v2 DAILY RUN (docs/01-methodology-protocol.md section 4; 02 section 2)
# ==============================================================================

import census  # noqa: E402
import baseline as baseline_mod  # noqa: E402
import retention  # noqa: E402
from quota import QuotaCounter, record_ledger  # noqa: E402

BASELINE_CHANNEL_BATCH = 50   # a brake inside a batch loses at most this batch
WRITE_BATCH = 500


QUOTA_STOP_RESULT = {"baseline": None, "samples": 0, "rule": "quota_stop",
                     "span_days": None, "video_ids": []}
READ_FAILED_RESULT = {**QUOTA_STOP_RESULT, "rule": "read_failed"}

# 01 section 1, 27/09/2026: the perimeter is long-form only, a temporary
# scope reduction forced by the quota. The census is not affected.
MEASURED_FORMATS = ("LONG",)


class RunAlreadyExists(Exception):
    """An ingest_run row for this day exists: one reading a day."""


def _vpi_fields(views, base):
    """VPI, level, name, colour; all None without a baseline (01 section 2).

    The ratio is stored at full precision: the level is assigned on the full
    value and rounding is a display concern.
    """
    if base is None or views is None:
        return {"vpi_ratio": None, "vpi_level": None,
                "vpi_level_name": None, "vpi_color": None}
    ratio = float(views) / float(base)
    level, name, color = get_vpi_metadata(ratio)
    return {"vpi_ratio": ratio, "vpi_level": level,
            "vpi_level_name": name, "vpi_color": color}


def _handle(meta):
    h = (meta.get("custom_url") or "").strip()
    return h if h.startswith("@") else None


def _first_slice(v):
    """The slice a record names as its country and category.

    The nightly census keeps the first slice it read the video in (the read
    order is shuffled). A day reprocessed from its snapshot has the sets but
    not the pairs: it names the first country and category in canonical
    order (reprocess_day, INC-1). Neither is used by any statistic.
    """
    if v.get("first_slice"):
        return v["first_slice"]
    return (sorted(v["countries"], key=census.TARGET_COUNTRIES.index)[0],
            sorted(v["categories"], key=int)[0])


def _record(vid, v, entry, res, meta, day, observed_iso, baseline_iso=None, reprocessed_iso=None):
    """One v2 posts row. method_version is written explicitly (default is v1).

    observed_iso: when the census saw the video (the reading's start).
    baseline_iso: when its channel's baseline was actually read; None when
    no baseline was read (quota_stop, read_failed).
    reprocessed_iso: set only when the record was written by reprocess_day,
    after the night: the late baseline read stays visible in the data.
    """
    views = v["views"]
    vf = _vpi_fields(views, res["baseline"])
    published = v["published_at"]
    age = (day - census_date(published)).days if published else None
    country, category = _first_slice(v)
    handle = _handle(meta)
    return {
        "platform": "YOUTUBE",
        "format": v["format"],
        "external_post_id": vid,
        "channel_id": v["channel_id"],
        "channel_handle": handle,
        "author_handle": handle,
        "author_name": v.get("channel_title") or meta.get("title"),
        "subscribers": meta.get("subscribers"),
        "post_url": f"https://www.youtube.com/watch?v={vid}",
        "content_text": v.get("title"),
        "category": census.CATEGORY_MAP[category],
        "country": country,
        "countries": sorted(v["countries"], key=census.TARGET_COUNTRIES.index),
        "categories": [census.CATEGORY_MAP[k] for k in sorted(v["categories"], key=int)],
        "engagement_score": views,
        "baseline_score": res["baseline"],
        **vf,
        "claim_token": f"iosa_{secrets.token_urlsafe(12)}",
        "status": "ACTIVE",
        "created_at": published,
        "detected_at": observed_iso,
        "entered_on": day.isoformat(),
        "baseline_computed_at": baseline_iso,
        "reprocessed_at": reprocessed_iso,
        "baseline_samples": res["samples"],
        "baseline_rule": res["rule"],
        "baseline_span_days": res["span_days"],
        "baseline_video_ids": res["video_ids"],
        "auto_generated_channel": handle is None,
        "method_version": "v2",
        "gap_days": entry["gap_days"],
        "entry_certain": entry["entry_certain"],
        "age_at_first_obs_days": age,
        "vpi_max": vf["vpi_ratio"],
        "vpi_max_on": day.isoformat() if vf["vpi_ratio"] is not None else None,
        "views_max": views,
        # FMT-1 (01 section 1.1): what classified the record, checkable
        # afterwards without another read
        "duration_s": v.get("duration_s"),
        "shape": v.get("shape"),
        "was_live": v.get("live"),
        "format_rule": FORMAT_RULE,
    }


def census_date(published_at):
    return datetime.fromisoformat(str(published_at).replace("Z", "+00:00")).date()


def _rpc_all(client, fn, params, order):
    out, start = [], 0
    while True:
        page = (client.rpc(fn, params).order(order)
                .range(start, start + census.RPC_PAGE - 1).execute().data) or []
        out.extend(page)
        if len(page) < census.RPC_PAGE:
            return out
        start += census.RPC_PAGE


def _is_unique_violation(exc):
    text = f"{getattr(exc, 'code', '')} {exc}"
    return "23505" in text or "duplicate key" in text


def run_daily(client, day, *, api_key, countries=None, categories=None,
              snapshot_only=False, quota=None, session=None, rng=None,
              sleep=time.sleep, now=None, storage=None, rerun=False) -> dict:
    """One daily reading. Returns the ingest_run row written for the day.

    rerun=True is the second attempt on a day whose census is not complete
    (failed before it, incomplete, or a run that died before recording it):
    the census is read again, a complete census already on record never is.
    The snapshot becomes the union of both attempts: a video seen by either
    was observed present that day. The day's quota counts both attempts
    against one brake. Work of the first attempt that succeeded (records
    already written) is not repeated: entries exclude existing records.

    snapshot_only=True is day 0: the snapshot and nothing else (01 §4).
    After a complete census, the snapshot retention (02 section 3.1): every
    day older than the 7-day window is archived to Storage, verified, then
    deleted (retention.py). storage=None means Supabase Storage from the
    environment. A retention failure is noted and deletes nothing more; it
    never changes the reading's outcome.
    Two completeness states, kept apart (02 section 4.6, 27/09/2026):
      - the census: complete or not. It alone decides outcome ('ok' or
        'partial'), so whether the day is the next reference, whether exits
        are closed, and whether entries are certain. A partial census
        observes presence, not absence (01 §4).
      - the baselines: baselines_complete. It decides only each record,
        through its baseline_rule. Entries the brake did not reach are
        recorded without a VPI, 'quota_stop' (an incident, counted); entries
        whose reads failed after the retries, 'read_failed'.
    Perimeter (01 §1, 27/09/2026): only long-form entries open a record
    (01 §1.1, FMT-1: everything that is not a Short as YouTube defines it;
    UNKNOWN never opens one). The census still reads and stores every video,
    Shorts included.
    """
    countries = list(countries or census.TARGET_COUNTRIES)
    categories = list(categories or census.CATEGORY_MAP)
    quota = quota if quota is not None else QuotaCounter()
    started = now or datetime.now(timezone.utc)
    now_iso = started.isoformat()
    if rng is None:
        seed = secrets.randbits(32)
        rng = random.Random(seed)
    else:
        seed = None
    prior, prior_notes = {}, []
    if rerun:
        found = client.table("ingest_run").select("*").in_("day", [day.isoformat()]).execute().data or []
        if not found:
            raise ReprocessRefused(f"{day}: no first attempt to follow")
        first = found[0]
        if first.get("census_complete") is True:
            raise ReprocessRefused(f"{day}: the census is complete, it is never read again: "
                                   "reprocess_day finishes the processing")
        prior = {k: first.get(k) or 0 for k in QuotaCounter().as_ingest_run()}
        prior_notes = [n for n in (first.get("notes") or "").split("; ") if n]
        prior_notes = [f"first attempt started {first.get('started_at')}, "
                       f"{'outcome ' + str(first.get('outcome')) if first.get('finished_at') else 'never finished'}"] \
            + [("first attempt " + n) if n.startswith("failed: ") else n for n in prior_notes]
        # one brake for the day: the second attempt gets what the first left
        quota = QuotaCounter(limit=max(1, quota.limit - prior.get("quota_total", 0)))
        client.table("ingest_run").update({"started_at": now_iso, "finished_at": None,
                                           "outcome": None}).eq("day", day.isoformat()).execute()
    else:
        try:
            client.table("ingest_run").insert(
                {"day": day.isoformat(), "started_at": now_iso}).execute()
        except Exception as e:
            if _is_unique_violation(e):
                raise RunAlreadyExists(f"ingest_run for {day} already exists") from e
            raise

    row = {"day": day.isoformat(), "started_at": now_iso, "outcome": "failed",
           "entries": 0, "new_channels": 0, "updated": 0, "exits": 0,
           "discards": {}, "notes": None}
    notes = prior_notes + ([f"second attempt at {now_iso}"] if rerun else []) + [
        f"slice order seed {seed}" if seed is not None else "slice order: caller rng",
        f"countries {len(countries)}, categories {len(categories)}",
        f"quota limit {quota.limit}"]
    try:
        videos, cen = census.read_charts(countries, categories, api_key, session=session,
                                         sleep=sleep, quota=quota, rng=rng)
        row.update({k: cen[k] for k in ("slices_ok", "slices_404", "slices_error",
                                        "videos_seen", "channels_seen")})
        discards = dict(cen["discards"])
        if cen["stop_reason"]:
            notes.append(f"census stopped: {cen['stop_reason']}")
        census.save_snapshot(client, day, videos)
        _analyze_snapshot(client, notes)
        if rerun:
            stored = _snapshot_videos(client, day)
            extra = sorted(set(stored) - set(videos))
            if extra:
                for vid in extra:
                    videos[vid] = stored[vid]
                for vid, t in _titles(extra, api_key, session=session, quota=quota).items():
                    videos[vid].update(t)
            row["videos_seen"] = len(videos)
            notes.append(f"snapshot = union of both attempts: {len(videos) - len(extra)} read now, "
                         f"{len(extra)} seen only by the first attempt")
        # The census is on record from here, whatever breaks after it: a
        # complete census is the next day's reference and the starting point
        # of reprocess_day (INC-1, owner decision 29/09/2026).
        row["census_complete"] = bool(cen["complete"])
        _persist(client, row, notes, quota)

        if snapshot_only:
            if not cen["complete"]:
                notes.append("day 0 incomplete: not a reference, the next reading is day 0 again")
            else:
                _retention(client, day, notes, storage)
            row["outcome"] = "ok" if cen["complete"] else "partial"
            row["discards"] = discards
            return row

        _process(client, day, videos, row, notes, discards, quota, api_key=api_key,
                 census_complete=bool(cen["complete"]), observed_iso=now_iso,
                 session=session, sleep=sleep, storage=storage)
        return row
    except Exception as e:
        row["outcome"] = "failed"
        notes.append(f"failed: {type(e).__name__}: {str(e)[:300]}")
        raise
    finally:
        row.update({k: v + prior.get(k, 0) for k, v in quota.as_ingest_run().items()})
        row["finished_at"] = datetime.now(timezone.utc).isoformat()
        # FMT-2: this attempt's units, in the quota day's ledger
        failed_ledger = record_ledger(client, "second attempt" if rerun else "reading", quota.total)
        if failed_ledger:
            notes.append(failed_ledger)
        row["notes"] = "; ".join(notes)
        client.table("ingest_run").upsert(row, on_conflict="day").execute()


def _process(client, day, videos, row, notes, discards, quota, *, api_key, census_complete,
             observed_iso, session=None, sleep=time.sleep, storage=None, reprocessed_iso=None):
    """Everything after the census: entries, baselines, records, daily views,
    exits, retention. Shared by the nightly run and reprocess_day, so a day
    reprocessed from its snapshot follows the same rules, line for line.
    `videos` is the census: from the charts at night, from the stored
    snapshot when reprocessed. Sets the row's counters and outcome.
    """
    # 3. entries: baseline computed now and frozen
    found = census.entries(client, day)
    measured, entry_of = [], {}
    entering_all, entering_long = set(), set()
    for e in found:
        v = videos.get(e["video_id"])
        if v is None:
            continue
        entering_all.add(v["channel_id"])
        if v["format"] not in MEASURED_FORMATS:
            discards["out_of_perimeter_" + str(v["format"]).lower()] = \
                discards.get("out_of_perimeter_" + str(v["format"]).lower(), 0) + 1
            continue
        entering_long.add(v["channel_id"])
        if v["views"] is None:
            discards["no_views"] = discards.get("no_views", 0) + 1
            continue
        entry_of[e["video_id"]] = e
        measured.append({"video_id": e["video_id"], "channel_id": v["channel_id"],
                         "format": v["format"], "published_at": v["published_at"]})
    by_channel = {}
    for m in measured:
        by_channel.setdefault(m["channel_id"], []).append(m)
    channels = sorted(by_channel)
    results, meta, unresolved, quota_stopped, stopped = {}, {}, [], [], None
    read_at = {}
    store = baseline_mod.SupabaseInventory(client)
    run_state = baseline_mod.new_run_state()
    # how much of today's turnover the inventory already holds: no role
    # in the budget; it tells when Shorts can come back (27/09/2026)
    known_all = store.known(entering_all)
    row.update({"entering_channels": len(entering_all),
                "entering_channels_in_inventory": len(known_all),
                "entering_long_channels": len(entering_long),
                "entering_long_in_inventory": len(known_all & entering_long)})
    base_units_before = quota.total
    breps = []
    for i in range(0, len(channels), BASELINE_CHANNEL_BATCH):
        batch = [m for ch in channels[i:i + BASELINE_CHANNEL_BATCH] for m in by_channel[ch]]
        if stopped:
            quota_stopped.extend(m["video_id"] for m in batch)
            continue
        res, brep = baseline_mod.baselines_for_videos(
            batch, api_key, session=session, sleep=sleep, quota=quota,
            inventory=store, run_state=run_state, today=day)
        stamp = datetime.now(timezone.utc).isoformat()
        for vid in res:
            read_at[vid] = stamp
        results.update(res)
        meta.update(brep["channels"])
        breps.append(brep)
        if brep["stop_reason"]:
            stopped = brep["stop_reason"]
            quota_stopped.extend(brep.get("unresolved", []))
            notes.append(f"baselines stopped: {stopped}")
        else:
            unresolved.extend(brep.get("unresolved", []))
    # 01 §2: entries the brake did not reach are valid records without a
    # VPI; so are entries whose reads failed after the retries
    for vid in quota_stopped:
        results[vid] = QUOTA_STOP_RESULT
    for vid in unresolved:
        results[vid] = READ_FAILED_RESULT
    if quota_stopped:
        discards["quota_stop"] = len(quota_stopped)
        notes.append(f"INCIDENT: {len(quota_stopped)} entries recorded without a VPI (quota_stop)")
    if unresolved:
        discards["read_failed"] = len(unresolved)
        notes.append(f"{len(unresolved)} entries recorded without a VPI after failed reads "
                     f"(read_failed)")
    base_units = quota.total - base_units_before
    n_ch = len(channels)
    agg = {k: sum(b.get(k, 0) for b in breps) for k in (
        "quota_channels", "quota_playlists", "quota_playlist", "quota_videos",
        "skipped_by_item_count", "videos_checked", "videos_skipped_other_format")}
    notes.append(
        f"baselines: {base_units} units for {n_ch} channels = "
        f"{(base_units / n_ch) if n_ch else 0:.2f} per channel (channels {agg['quota_channels']}, "
        f"itemCount {agg['quota_playlists']}, uploads {agg['quota_playlist']}, videos "
        f"{agg['quota_videos']}); skipped by itemCount {agg['skipped_by_item_count']}; videos "
        f"checked {agg['videos_checked']}, other-format not checked "
        f"{agg['videos_skipped_other_format']}")
    notes.append(f"entering channels in the inventory: {len(known_all)}/{len(entering_all)} all "
                 f"formats, {len(known_all & entering_long)}/{len(entering_long)} long-form")
    row["baselines_complete"] = not stopped and not unresolved

    records = [_record(vid, videos[vid], entry_of[vid], res, meta.get(videos[vid]["channel_id"], {}),
                       day, observed_iso, read_at.get(vid), reprocessed_iso)
               for vid, res in sorted(results.items())]
    for i in range(0, len(records), WRITE_BATCH):
        client.table("posts").insert(records[i:i + WRITE_BATCH]).execute()
    row["entries"] = len(records)
    row["new_channels"] = len({r["channel_id"] for r in records})

    # 4. today's views for every charting v2 record, the new ones included
    tracked = _rpc_all(client, "tracked_of_day", {"d": day.isoformat()}, "post_id")
    payload = []
    for t in tracked:
        if t["views"] is None:
            continue
        base = float(t["baseline_score"]) if t["baseline_score"] is not None else None
        payload.append({"post_id": str(t["post_id"]), "views": float(t["views"]),
                        **_vpi_fields(float(t["views"]), base)})
    updated = 0
    for i in range(0, len(payload), WRITE_BATCH):
        updated += client.rpc("apply_daily_views",
                              {"d": day.isoformat(), "rows": payload[i:i + WRITE_BATCH]}).execute().data or 0
    row["updated"] = updated

    # 5. exits: a complete census observes absence, whatever the baselines
    row["exits"] = census.close_exits(client, day, census_complete)
    if census_complete:
        _retention(client, day, notes, storage)
    row["outcome"] = "ok" if census_complete else "partial"
    row["discards"] = discards
    return row


def _persist(client, row, notes, quota):
    """Write the run row as it stands. Never raises: the finally writes it again."""
    try:
        # outcome stays empty while the processing runs: it is written at the end
        snap = {**row, **quota.as_ingest_run(), "notes": "; ".join(notes), "outcome": None}
        client.table("ingest_run").upsert(snap, on_conflict="day").execute()
    except Exception as e:
        log.warning("ingest_run not persisted after the census: %s", e)


def _analyze_snapshot(client, notes):
    """Fresh statistics on trend_snapshot before entries_of_day (INC-1).

    The day's rows were just written; planned on stale statistics the entry
    query could exceed the API's 8 s statement timeout (reading of
    2026-09-28). A failure here is noted and never fatal: the index on
    posts(external_post_id) keeps the query fast without it.
    """
    try:
        client.rpc("analyze_snapshot", {}).execute()
    except Exception as e:
        notes.append(f"analyze_snapshot failed: {type(e).__name__}: {str(e)[:200]}")


def _retention(client, day, notes, storage=None):
    """Snapshot retention after a complete census. Never raises."""
    try:
        store = storage if storage is not None else retention.SupabaseStorage.from_env()
        notes.append(retention.note(day, retention.purge(client, store, day)))
    except Exception as e:
        notes.append(f"RETENTION FAILED: {type(e).__name__}: {str(e)[:300]}; "
                     "no day deleted after the failure")


class ReprocessRefused(Exception):
    """reprocess_day will not run on this day: the reason is the message."""


def _snapshot_videos(client, day):
    """The stored census of a day: {video_id: {channel_id, format, published_at,
    views, countries, categories, duration_s, shape, live}}, from
    trend_snapshot, every row. duration_s, shape and live (FMT-1) are what the
    census stored, so a day finished from its snapshot writes the same values
    as the night; absent (None) in a snapshot written before FMT-1."""
    rows = _rpc_all(client, "snapshot_export", {"p_day": day.isoformat()}, "video_id")
    out = {}
    for r in rows:
        x = json.loads(r["line"])
        out[x["video_id"]] = {"channel_id": x["channel_id"], "format": x["format"],
                              "published_at": x["published_at"], "views": x["views"],
                              "countries": set(x["countries"]), "categories": set(x["categories"]),
                              "duration_s": x.get("duration_s"), "shape": x.get("shape"),
                              "live": x.get("live")}
    return out


def _titles(video_ids, api_key, *, session=None, quota):
    """Titles and channel titles for the records to be written: videos.list,
    snippet only, 50 ids per unit. Descriptive fields, not the measurement:
    the views come from the snapshot, never from this read."""
    http = session or requests
    out = {}
    ids = sorted(video_ids)
    for i in range(0, len(ids), 50):
        quota.mark("videos")
        res = http.get("https://www.googleapis.com/youtube/v3/videos",
                       params={"part": "snippet", "id": ",".join(ids[i:i + 50]),
                               "maxResults": 50, "key": api_key}, timeout=30)
        if res.status_code != 200:
            continue
        for item in res.json().get("items", []):
            sn = item.get("snippet", {})
            out[item["id"]] = {"title": sn.get("title"), "channel_title": sn.get("channelTitle")}
    return out


def _complete_baselines(client, day, videos, notes, quota, *, api_key, session=None,
                        sleep=time.sleep, reprocessed_iso):
    """Baselines for the day's records written without one (quota_stop,
    read_failed): read now, frozen now, VPI on the day's snapshot views.
    A record that already has a baseline is never touched (01 section 2)."""
    recs = [r for r in _rpc_all(client, "records_of_day", {"d": day.isoformat()}, "post_id")
            if r["baseline_rule"] in ("quota_stop", "read_failed") and r["external_post_id"] in videos]
    if not recs:
        return 0, 0
    by_id = {r["external_post_id"]: {**r, "id": r["post_id"]} for r in recs}
    measured = [{"video_id": r["external_post_id"], "channel_id": r["channel_id"],
                 "format": r["format"], "published_at": r["created_at"]} for r in recs]
    by_channel = {}
    for m in measured:
        by_channel.setdefault(m["channel_id"], []).append(m)
    store = baseline_mod.SupabaseInventory(client)
    run_state = baseline_mod.new_run_state()
    done, stopped = 0, None
    channels = sorted(by_channel)
    for i in range(0, len(channels), BASELINE_CHANNEL_BATCH):
        if stopped:
            break
        batch = [m for ch in channels[i:i + BASELINE_CHANNEL_BATCH] for m in by_channel[ch]]
        res, brep = baseline_mod.baselines_for_videos(
            batch, api_key, session=session, sleep=sleep, quota=quota,
            inventory=store, run_state=run_state, today=day)
        stamp = datetime.now(timezone.utc).isoformat()
        rows, views = [], []
        for vid, r in res.items():
            v = videos[vid]["views"]
            rows.append({"post_id": by_id[vid]["id"], "baseline_score": r["baseline"],
                         "baseline_rule": r["rule"], "baseline_samples": r["samples"],
                         "baseline_span_days": r["span_days"], "baseline_video_ids": r["video_ids"],
                         "baseline_computed_at": stamp, "reprocessed_at": reprocessed_iso,
                         **_vpi_fields(v, r["baseline"])})
            if v is not None:
                views.append({"post_id": by_id[vid]["id"], "views": float(v),
                              **_vpi_fields(float(v), r["baseline"])})
        if rows:
            done += client.rpc("complete_baselines", {"d": day.isoformat(), "rows": rows}).execute().data or 0
        if views:
            client.rpc("apply_daily_views", {"d": day.isoformat(), "rows": views}).execute()
        if brep["stop_reason"]:
            stopped = brep["stop_reason"]
            notes.append(f"baselines stopped: {stopped}")
    return len(recs), done


def _catch_up(client, day, later_day):
    """Replay a later day for the records entered on `day`: their views and
    VPI on `later_day` (from its snapshot) and the exits it observed. The
    same functions the night uses; for the other records they change
    nothing (same views, same frozen baseline, already closed)."""
    mine = {r["post_id"] for r in _rpc_all(client, "records_of_day", {"d": day.isoformat()}, "post_id")}
    tracked = _rpc_all(client, "tracked_of_day", {"d": later_day.isoformat()}, "post_id")
    payload = []
    for t in tracked:
        if t["post_id"] not in mine or t["views"] is None:
            continue
        base = float(t["baseline_score"]) if t["baseline_score"] is not None else None
        payload.append({"post_id": str(t["post_id"]), "views": float(t["views"]),
                        **_vpi_fields(float(t["views"]), base)})
    views = 0
    for i in range(0, len(payload), WRITE_BATCH):
        views += client.rpc("apply_daily_views", {"d": later_day.isoformat(),
                                                  "rows": payload[i:i + WRITE_BATCH]}).execute().data or 0
    exits = census.close_exits(client, later_day, True)
    return {"views": views, "exits": exits}


def reprocess_day(client, day, *, api_key, quota=None, session=None, sleep=time.sleep,
                  storage=None, now=None) -> dict:
    """Finish the processing of a day whose chart census is complete (INC-1).

    The stored snapshot is the census, already paid for: the charts are
    never read again. Does what the night did not: entries against the
    previous complete census, baselines and VPI for the long-form entries,
    daily views, exits, retention; then baselines for the day's records left
    without one (quota_stop, read_failed). Records it writes or completes
    carry reprocessed_at and the actual baseline read time. The run report is
    rewritten with what was done.

    Refuses a day with no complete census, a snapshot that is not the one the
    census counted, or a reading still in progress. Later days already read
    are caught up for this day's records, in order, from their snapshots;
    refused if one of them is not a finished complete census with its
    snapshot intact.
    """
    started = now or datetime.now(timezone.utc)
    stamp = started.isoformat()
    rows = client.table("ingest_run").select("*").in_("day", [day.isoformat()]).execute().data or []
    if not rows:
        raise ReprocessRefused(f"{day}: no reading")
    row = dict(rows[0])
    if row.get("census_complete") is not True:
        raise ReprocessRefused(f"{day}: the census is not complete")
    if row.get("finished_at") is None:
        raise ReprocessRefused(f"{day}: a reading is in progress")
    later = sorted((r for r in (client.table("ingest_run").select("*").execute().data or [])
                    if str(r["day"])[:10] > day.isoformat()), key=lambda r: str(r["day"]))
    # Later days are caught up for this day's records (views, VPI, exits), in
    # order, from their own snapshots: each must be a complete census whose
    # snapshot is still the one it counted, or nothing is done.
    for r in later:
        d = str(r["day"])[:10]
        if r.get("census_complete") is not True or r.get("finished_at") is None:
            raise ReprocessRefused(f"{day}: the later reading of {d} is not a finished complete census")
        n = len(_rpc_all(client, "snapshot_export", {"p_day": d}, "video_id"))
        if n != (r.get("videos_seen") or -1):
            raise ReprocessRefused(f"{day}: the later snapshot of {d} holds {n} videos, "
                                   f"its census counted {r.get('videos_seen')}")
    videos = _snapshot_videos(client, day)
    if len(videos) != (row.get("videos_seen") or -1):
        raise ReprocessRefused(f"{day}: the snapshot holds {len(videos)} videos, "
                               f"the census counted {row.get('videos_seen')}")

    quota = quota if quota is not None else QuotaCounter()
    before = {k: row.get(k) or 0 for k in quota.as_ingest_run()}
    old_notes = [n for n in (row.get("notes") or "").split("; ") if n]
    notes = [n if not n.startswith("failed: ") else f"processing failed at {row.get('finished_at')}: {n[8:]}"
             for n in old_notes]
    notes.append(f"reprocessed at {stamp} by reprocess_day: census from the stored snapshot "
                 f"({len(videos)} videos), charts not read again")
    for k in ("id", "entries", "new_channels", "updated", "exits", "baselines_complete"):
        row.pop(k, None)
    row.update({"entries": 0, "new_channels": 0, "updated": 0, "exits": 0})
    discards = dict(row.get("discards") or {})
    observed = str(row["started_at"])
    try:
        # titles for the entries that will become records (not stored in the snapshot)
        found = census.entries(client, day)
        want = {e["video_id"] for e in found if e["video_id"] in videos
                and videos[e["video_id"]]["format"] in MEASURED_FORMATS}
        for vid, t in _titles(want, api_key, session=session, quota=quota).items():
            videos[vid].update(t)
        title_units = quota.total
        _process(client, day, videos, row, notes, discards, quota, api_key=api_key,
                 census_complete=True, observed_iso=observed, session=session, sleep=sleep,
                 storage=storage, reprocessed_iso=stamp)
        n_left, n_done = _complete_baselines(client, day, videos, notes, quota, api_key=api_key,
                                             session=session, sleep=sleep, reprocessed_iso=stamp)
        for r in later:
            caught = _catch_up(client, day, date.fromisoformat(str(r["day"])[:10]))
            notes.append(f"caught up {str(r['day'])[:10]} for this day's records: "
                         f"{caught['views']} daily views, {caught['exits']} exits")
        entered = _rpc_all(client, "records_of_day", {"d": day.isoformat()}, "post_id")
        waiting = sum(r["baseline_rule"] in ("quota_stop", "read_failed") for r in entered)
        row["entries"] = len(entered)
        row["baselines_complete"] = waiting == 0
        notes.append(f"reprocess: titles {title_units} units; {n_done}/{n_left} records completed "
                     f"that were written without a baseline; {waiting} still without a VPI; "
                     f"{quota.total} units in this pass")
        row["outcome"] = "ok"
        return row
    except Exception as e:
        row["outcome"] = "failed"
        notes.append(f"reprocess failed: {type(e).__name__}: {str(e)[:300]}")
        raise
    finally:
        spent = quota.as_ingest_run()
        for k, v in spent.items():
            row[k] = before.get(k, 0) + v
        row["reprocessed_at"] = stamp
        row["finished_at"] = datetime.now(timezone.utc).isoformat()
        failed_ledger = record_ledger(client, "reprocess", quota.total)    # FMT-2
        if failed_ledger:
            notes.append(failed_ledger)
        row["notes"] = "; ".join(notes)
        row["discards"] = discards
        client.table("ingest_run").upsert(row, on_conflict="day").execute()


def _env_flag(name):
    return (os.getenv(name) or "").strip().lower() in ("1", "true", "yes")


READING_DAY_OFFSET = timedelta(hours=1)


def reading_day(now: datetime | None = None):
    """The day a reading belongs to (02 section 5).

    The reading is triggered at 23:59 UTC and the second attempt at 00:30 UTC
    the next morning: both belong to the day just closed. One hour back from
    the trigger time covers both and leaves any daytime manual run on its own
    date.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("reading_day wants an aware datetime")
    return (now.astimezone(timezone.utc) - READING_DAY_OFFSET).date()


def has_complete_reading_before(client, day) -> bool:
    """True when a reading with a complete census exists for a day before `day`
    (INC-1b: the census, not the outcome of what followed it).

    Without one there is no reference to compare against (01 section 4), so
    the reading is day 0: census and snapshot only. This makes day 0
    automatic, with no environment flag to set and then remember to unset; a
    partial day 0 is not a reference, so the next night is day 0 again.
    """
    res = client.table("ingest_run").select("*").in_("census_complete", [True]).execute()
    return any(str(r["day"])[:10] < day.isoformat() for r in (res.data or []))


def esegui_un_ciclo(con_scadenze: bool = True, rerun: bool = False) -> dict:
    """One daily reading for the reading day (UTC), configured from the environment.

    Day 0 (census only) when no complete reading exists before the reading
    day; SNAPSHOT_ONLY=true forces it. IOSA_COUNTRIES=IT,US,DE limits the countries
    (dry run, T-13/T-14). QUOTA_MAX_DAILY lowers the brake, never raises it.
    Writes with the service role (SUPABASE_SERVICE_KEY): posts, trend_snapshot
    and ingest_run are not writable with the public key. con_scadenze is
    ignored: v2 records do not expire (01 section 3).
    """
    key = os.getenv("SUPABASE_SERVICE_KEY") or SUPABASE_KEY
    client = create_client(SUPABASE_URL, key)
    raw = (os.getenv("IOSA_COUNTRIES") or "").strip()
    countries = [c.strip().upper() for c in raw.split(",") if c.strip()] or None
    day = reading_day()
    snapshot_only = _env_flag("SNAPSHOT_ONLY") or not has_complete_reading_before(client, day)
    return run_daily(client, day, api_key=YOUTUBE_API_KEY, countries=countries,
                     snapshot_only=snapshot_only, rerun=rerun)


def riprendi_un_giorno(day) -> dict:
    """reprocess_day for `day`, configured from the environment (service role)."""
    key = os.getenv("SUPABASE_SERVICE_KEY") or SUPABASE_KEY
    client = create_client(SUPABASE_URL, key)
    return reprocess_day(client, day, api_key=YOUTUBE_API_KEY)


def start_engine():
    """No background scheduler in v2: the only trigger is pg_cron calling
    POST /api/ingest/run at 23:59 UTC (02 section 5). Kept so main.py's
    startup hook still has something to call."""
    log.info("v2: no in-process scheduler; ingestion runs only on POST /api/ingest/run.")
    return None
