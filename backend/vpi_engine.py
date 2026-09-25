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
import time
import secrets
import random
import requests
import statistics
import re
from datetime import datetime, timezone, timedelta
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
    formato_da_durata,
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
from quota import QuotaCounter  # noqa: E402

BASELINE_CHANNEL_BATCH = 50   # a brake inside a batch loses at most this batch
WRITE_BATCH = 500


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


def _record(vid, v, entry, res, meta, day, now_iso):
    """One v2 posts row. method_version is written explicitly (default is v1)."""
    views = v["views"]
    vf = _vpi_fields(views, res["baseline"])
    published = v["published_at"]
    age = (day - census_date(published)).days if published else None
    country, category = v["first_slice"]
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
        "detected_at": now_iso,
        "entered_on": day.isoformat(),
        "baseline_computed_at": now_iso,
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
              sleep=time.sleep, now=None) -> dict:
    """One daily reading. Returns the ingest_run row written for the day.

    snapshot_only=True is day 0: snapshot written as permanent, day0_pending
    seeded from it only if the census was complete, nothing else (01 §4).
    A partial run (census incomplete, 403, quota brake, unresolved baselines)
    records the entries it observed and today's views, but never exits and
    never drains the day-0 list: absence is not observable (01 §4).
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
    notes = [f"slice order seed {seed}" if seed is not None else "slice order: caller rng",
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
        census.save_snapshot(client, day, videos, permanent=snapshot_only)

        if snapshot_only:
            if cen["complete"]:
                ids = sorted(videos)
                for i in range(0, len(ids), WRITE_BATCH):
                    client.table("day0_pending").upsert(
                        [{"video_id": v} for v in ids[i:i + WRITE_BATCH]]).execute()
            else:
                notes.append("day 0 incomplete: delete this day's snapshot and re-run day 0")
            row["outcome"] = "ok" if cen["complete"] else "partial"
            row["discards"] = discards
            return row

        # 3. entries: baseline computed now and frozen
        found = census.entries(client, day)
        measured, entry_of = [], {}
        for e in found:
            v = videos.get(e["video_id"])
            if v is None:
                continue
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
        results, meta, unresolved, stopped = {}, {}, [], None
        for i in range(0, len(channels), BASELINE_CHANNEL_BATCH):
            batch = [m for ch in channels[i:i + BASELINE_CHANNEL_BATCH] for m in by_channel[ch]]
            if stopped:
                unresolved.extend(m["video_id"] for m in batch)
                continue
            res, brep = baseline_mod.baselines_for_videos(batch, api_key, session=session,
                                                          sleep=sleep, quota=quota)
            results.update(res)
            meta.update(brep["channels"])
            unresolved.extend(brep.get("unresolved", []))
            if brep["stop_reason"]:
                stopped = brep["stop_reason"]
                notes.append(f"baselines stopped: {stopped}")
        if unresolved:
            notes.append(f"{len(unresolved)} entries left without a baseline, not written")

        records = [_record(vid, videos[vid], entry_of[vid], res, meta.get(videos[vid]["channel_id"], {}),
                           day, now_iso) for vid, res in sorted(results.items())]
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

        # 5. exits and the day-0 list: complete readings only
        run_complete = cen["complete"] and not stopped and not unresolved
        row["exits"] = census.close_exits(client, day, run_complete)
        if run_complete:
            drained = client.rpc("drain_day0_pending", {"d": day.isoformat()}).execute().data or 0
            notes.append(f"day0_pending drained {drained}")
        row["outcome"] = "ok" if run_complete else "partial"
        row["discards"] = discards
        return row
    except Exception as e:
        row["outcome"] = "failed"
        notes.append(f"failed: {type(e).__name__}: {str(e)[:300]}")
        raise
    finally:
        row.update(quota.as_ingest_run())
        row["finished_at"] = datetime.now(timezone.utc).isoformat()
        row["notes"] = "; ".join(notes)
        client.table("ingest_run").upsert(row, on_conflict="day").execute()


def _env_flag(name):
    return (os.getenv(name) or "").strip().lower() in ("1", "true", "yes")


def esegui_un_ciclo(con_scadenze: bool = True) -> dict:
    """One daily reading for today (UTC), configured from the environment.

    SNAPSHOT_ONLY=true -> day 0. IOSA_COUNTRIES=IT,US,DE limits the countries
    (dry run, T-13/T-14). QUOTA_MAX_DAILY lowers the brake, never raises it.
    Writes with the service role (SUPABASE_SERVICE_KEY): posts, trend_snapshot
    and ingest_run are not writable with the public key. con_scadenze is
    ignored: v2 records do not expire (01 section 3).
    """
    key = os.getenv("SUPABASE_SERVICE_KEY") or SUPABASE_KEY
    client = create_client(SUPABASE_URL, key)
    raw = (os.getenv("IOSA_COUNTRIES") or "").strip()
    countries = [c.strip().upper() for c in raw.split(",") if c.strip()] or None
    day = datetime.now(timezone.utc).date()
    return run_daily(client, day, api_key=YOUTUBE_API_KEY, countries=countries,
                     snapshot_only=_env_flag("SNAPSHOT_ONLY"))


def start_engine():
    """No background scheduler in v2: the only trigger is pg_cron calling
    POST /api/ingest/run at 23:59 UTC (02 section 5). Kept so main.py's
    startup hook still has something to call."""
    log.info("v2: no in-process scheduler; ingestion runs only on POST /api/ingest/run.")
    return None
