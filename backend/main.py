import sys
import asyncio
import json
import time
import statistics
import threading
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional

# Force ProactorEventLoop policy on Windows to allow Playwright subprocesses
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import os
import re
import secrets
import hashlib
import stripe
import traceback
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, field_validator
from dotenv import load_dotenv
from supabase import create_client

import archivio_targhe
from trophy_pipeline import fulfill_trophy_order, generate_and_publish_trophy
from generate_trophy import (generate_trophy_png, generate_mug_preview_png,
                             impronta_campione_tazza)
from vpi_engine import RunAlreadyExists, esegui_un_ciclo, reading_day, start_engine

from log_iosa import configura, prendi

log = prendi(__name__)

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
SUPABASE_URL = os.getenv("NEXT_PUBLIC_SUPABASE_URL") or os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY") or os.getenv("SUPABASE_KEY")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
log.info(f"DEBUG: FRONTEND_URL is set to: {FRONTEND_URL}")

# Chiave richiesta dagli endpoint amministrativi (creazione prodotti Printify).
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY")

# Spedizione express: riattivare SOLO dopo aver verificato il costo reale del
# corriere su Printify. Finche' e' False viene offerta la sola standard, cosi'
# il cliente non paga un servizio piu' rapido che poi non riceve.
ENABLE_EXPRESS_SHIPPING = os.getenv("ENABLE_EXPRESS_SHIPPING", "false").lower() == "true"

# Interruttore generale degli ordini. Default SPENTO finche' non e' definito
# l'inquadramento fiscale. Per riaccendere: ENABLE_ORDERS=true nel backend e
# NEXT_PUBLIC_ENABLE_ORDERS=true su Vercel. Serve a poter spegnere il negozio in un secondo, per
# esempio finche' l'inquadramento fiscale non e' definito, senza toccare il
# resto del sito: la targa digitale gratuita continua a funzionare.
ENABLE_ORDERS = os.getenv("ENABLE_ORDERS", "false").lower() == "true"

# Catalogo prezzi in centesimi di USD. Prezzo fisso per prodotto.
PRODUCT_CATALOG = {"mug": 1900}
DEFAULT_PRODUCT_KEY = "mug"

# Limita i rendering Chromium simultanei e mette in cache le preview su disco.
RENDER_SEMAPHORE = asyncio.Semaphore(2)
PREVIEW_CACHE_SECONDS = 24 * 60 * 60
RENDERS_DIR = Path(__file__).resolve().parent / "renders"


def _safe_record_id(value) -> str:
    """Rende un record_id sicuro come nome file senza alterare i claim_token."""
    return re.sub(r"[^A-Za-z0-9_-]", "_", str(value or "preview"))[:120]


def _cached_render(record_id: str):
    """Restituisce il PNG gia' renderizzato se e' abbastanza recente."""
    path = RENDERS_DIR / f"trophy_{record_id}.png"
    if path.exists() and (time.time() - path.stat().st_mtime) < PREVIEW_CACHE_SECONDS:
        return path
    return None


# ---------------------------------------------------------------------------
# Memoria a breve delle statistiche
#
# Le due pagine di analisi leggono ogni volta tutte le righe ATTIVE (oltre
# undicimila) e le ricontano in Python. Tre richieste in parallelo - che e'
# esattamente cio' che fa la pagina Insights all'apertura - saturavano il
# servizio gratuito e tornavano 500 a caso. I dati cambiano ogni venti minuti,
# quindi tenerli in memoria per cinque e' abbondantemente sicuro.
_STATISTICHE_CACHE = {}
_STATISTICHE_LOCK = threading.Lock()
STATISTICHE_TTL = 300


def _statistiche_in_memoria(chiave: str, calcola):
    adesso = time.time()
    voce = _STATISTICHE_CACHE.get(chiave)
    if voce and adesso - voce[0] < STATISTICHE_TTL:
        return voce[1]
    # Un solo calcolo alla volta: chi arriva mentre e' in corso aspetta e
    # trova il risultato gia' pronto, invece di rifare lo stesso lavoro.
    with _STATISTICHE_LOCK:
        voce = _STATISTICHE_CACHE.get(chiave)
        if voce and time.time() - voce[0] < STATISTICHE_TTL:
            return voce[1]
        valore = calcola()
        _STATISTICHE_CACHE[chiave] = (time.time(), valore)
        return valore


def _fetch_all_rows(table: str, columns: str, page_size: int = 1000, **filters):
    """
    Legge una tabella oltre il tetto implicito di 1.000 righe di Supabase.

    Su questo progetto max_rows non e' limitato e una singola risposta
    restituisce tutte le righe (verificato: 11.188 in una sola chiamata).
    La paginazione resta come rete di sicurezza, perche' il tetto e' una
    impostazione di progetto che puo' cambiare senza preavviso.
    """
    rows = []
    offset = 0
    while True:
        query = supabase.table(table).select(columns)
        for column, value in filters.items():
            query = query.eq(column, value)
        page = query.range(offset, offset + page_size - 1).execute()
        batch = page.data or []
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return rows


def _build_shipping_options():
    options = [{
        "shipping_rate_data": {
            "type": "fixed_amount",
            "fixed_amount": {"amount": 499, "currency": "usd"},
            "display_name": "Standard Tracked Shipping (US / EU / UK)",
            "delivery_estimate": {
                "minimum": {"unit": "business_day", "value": 3},
                "maximum": {"unit": "business_day", "value": 7},
            },
        }
    }]
    if ENABLE_EXPRESS_SHIPPING:
        options.append({
            "shipping_rate_data": {
                "type": "fixed_amount",
                "fixed_amount": {"amount": 1299, "currency": "usd"},
                "display_name": "Express Shipping",
                "delivery_estimate": {
                    "minimum": {"unit": "business_day", "value": 2},
                    "maximum": {"unit": "business_day", "value": 5},
                },
            }
        })
    return options

if not STRIPE_SECRET_KEY:
    log.warning("⚠️ WARNING: STRIPE_SECRET_KEY not found in .env file!")

stripe.api_key = STRIPE_SECRET_KEY

supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ingest_run is readable only with the service role (RLS, no policy).
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
supabase_service = None
if SUPABASE_URL and SUPABASE_SERVICE_KEY:
    supabase_service = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# Monitoraggio errori opzionale: attivo solo se SENTRY_DSN e' configurato.
SENTRY_DSN = os.getenv("SENTRY_DSN")
if SENTRY_DSN:
    try:
        import sentry_sdk
        sentry_sdk.init(dsn=SENTRY_DSN, traces_sample_rate=0.0)
        log.info("Sentry attivo.")
    except ImportError:
        log.info("SENTRY_DSN configurato ma sentry-sdk non installato.")

configura()
app = FastAPI(title="IOSA Trophy API")

@app.on_event("startup")
def startup_event():
    start_engine()


# --- Ingestione su richiesta, per un cron esterno -----------------------------
# Il servizio web su piano gratuito va in sospensione dopo un quarto d'ora
# senza traffico, e con lui moriva lo scheduler interno. Questo endpoint
# permette a un cron di fuori (Render Cron Job, GitHub Actions, cron-job.org)
# di far partire un giro senza dipendere dal fatto che qualcuno visiti il sito.
INGEST_TRIGGER_TOKEN = (os.getenv("INGEST_TRIGGER_TOKEN") or "").strip()

# Un giro dura minuti. Due giri sovrapposti raddoppierebbero il consumo di
# quota YouTube per gli stessi video, quindi il secondo viene rifiutato.
_ingestione_in_corso = False


# Render's free tier stops a web service after 15 minutes without inbound
# requests, and a background task is not inbound traffic: a reading longer
# than that (a day with baselines) would be killed half-way. While a reading
# runs, the service calls its own public URL (RENDER_EXTERNAL_URL, set by
# Render) every few minutes. Nothing is read from YouTube: no quota.
KEEPALIVE_SECONDS = 240


def _keepalive(stop, url, interval=KEEPALIVE_SECONDS, get=None):
    import urllib.request
    get = get or (lambda u: urllib.request.urlopen(u, timeout=30).read(64))
    while not stop.wait(interval):
        try:
            get(url)
        except Exception as e:                      # a missed ping is not fatal
            log.info("keepalive: %s", e)


def _giro_di_ingestione():
    global _ingestione_in_corso
    stop = threading.Event()
    url = (os.getenv("RENDER_EXTERNAL_URL") or "").rstrip("/")
    if url:
        threading.Thread(target=_keepalive, args=(stop, url + "/"), daemon=True).start()
    try:
        esiti = esegui_un_ciclo()
        log.info("ingestione su richiesta conclusa: %s", esiti)
    except RunAlreadyExists as e:
        log.warning("reading refused: %s", e)
    except Exception as e:
        log.error("reading failed: %s", e)
    finally:
        stop.set()
        _ingestione_in_corso = False


def _ingest_run_for(day):
    """The ingest_run row for a day, read with the service role (RLS: the
    public key sees nothing in ingest_run)."""
    res = (supabase_service.table("ingest_run").select("day, outcome, started_at, finished_at")
           .eq("day", day.isoformat()).execute())
    return (res.data or [None])[0]


@app.post("/api/ingest/run")
def avvia_ingestione(background: BackgroundTasks,
                     authorization: Optional[str] = Header(default=None)):
    """Fa partire un giro di ingestione e risponde subito.

    Il giro dura minuti: tenere aperta la richiesta la farebbe scadere a meta'
    e il cron la segnerebbe come fallita. Quindi 202 e lavoro in background.
    """
    global _ingestione_in_corso

    if not INGEST_TRIGGER_TOKEN:
        raise HTTPException(status_code=503,
                            detail="INGEST_TRIGGER_TOKEN non configurato: endpoint disattivato.")

    atteso = f"Bearer {INGEST_TRIGGER_TOKEN}"
    if not authorization or not secrets.compare_digest(authorization.strip(), atteso):
        raise HTTPException(status_code=401, detail="Token non valido.")

    if _ingestione_in_corso:
        return {"stato": "gia_in_corso",
                "dettaglio": "Un giro e' gia' in esecuzione: questa chiamata non ne avvia un altro."}

    # One reading a day (01 section 4). Without this lock two close calls
    # would double the quota spend. Any existing row for today answers 409,
    # whatever its outcome: the engine refuses a second reading anyway.
    if not supabase_service:
        raise HTTPException(status_code=503,
                            detail="SUPABASE_SERVICE_KEY non configurata: il lock giornaliero non e' verificabile.")
    oggi = reading_day()
    esistente = _ingest_run_for(oggi)
    if esistente:
        raise HTTPException(status_code=409,
                            detail={"day": oggi.isoformat(), "outcome": esistente.get("outcome"),
                                    "dettaglio": "Una lettura per questo giorno esiste gia'."})

    _ingestione_in_corso = True
    background.add_task(_giro_di_ingestione)
    return {"stato": "avviato", "day": oggi.isoformat()}


@app.get("/api/ingest/status")
def stato_ingestione():
    """The latest ingest_run: how the audit is read without opening the database."""
    if not supabase_service:
        raise HTTPException(status_code=503, detail="SUPABASE_SERVICE_KEY non configurata.")
    res = (supabase_service.table("ingest_run").select("*")
           .order("day", desc=True).limit(1).execute())
    return {"latest": (res.data or [None])[0]}

ALLOWED_ORIGINS = [o for o in [
    FRONTEND_URL,
    "http://localhost:3000",
    "https://iosaresearch.org",
    "https://www.iosaresearch.org",
] if o]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TrophyRequest(BaseModel):
    record_id: str = "REC_8F9A2B"
    author: str
    vpi_ratio: str
    level_name: str = "Lvl 5 - Breakout"
    content_title: str
    date_str: str = "2026-08-20"
    e_act: str = "87.2K"
    e_base: str = "10.0K"
    gamma: str = "1.0x"

class CheckoutSessionRequest(BaseModel):
    claimToken: str
    authorHandle: str = "Creator"
    email: str
    name: str
    productType: str = "Official Commemorative Mug ($19.00)"

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        v_clean = v.strip()
        regex = r"^[^\s@]+@[^\s@]+\.[^\s@]+$"
        if not re.match(regex, v_clean):
            raise ValueError("Invalid email format. Please enter a valid email address.")
        return v_clean

MACRO_REGIONS = {
    "North America": ["US", "CA", "MX"],
    "Europe": ["GB", "DE", "FR", "ES", "IT", "NL", "PL", "SE", "NO", "FI", "DK", "CH", "AT", "BE", "PT", "IE"],
    "LATAM": ["BR", "AR", "CL", "CO"],
    "APAC": ["JP", "IN", "AU", "KR", "NZ", "PH", "ID", "TH", "VN"]
}

STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "if", "because", "as", "what", "which",
    "this", "that", "these", "those", "then", "just", "so", "than", "such",
    "both", "through", "about", "against", "between", "into", "throughout",
    "during", "before", "after", "above", "below", "to", "from", "up", "upon",
    "down", "in", "out", "on", "off", "over", "under", "again", "further",
    "then", "once", "here", "there", "when", "where", "why", "how", "all",
    "any", "both", "each", "few", "more", "most", "other", "some", "such",
    "no", "nor", "not", "only", "own", "same", "so", "than", "too", "very",
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "for", "with", "by", "at", "my", "your", "his", "her",
    "its", "our", "their", "it", "i", "you", "he", "she", "we", "they"
}

@app.head("/")
@app.get("/")
def read_root():
    # "archivio_targhe" dice se le targhe gia' rese vengono conservate su
    # Storage. Se e' falso mancano le chiavi nell'ambiente e ogni anteprima
    # viene ricostruita da zero: si vede da fuori, senza guardare i log.
    return {"status": "online", "system": "IOSA Lab Backend",
            "motore": (os.getenv("IOSA_ENGINE_MODE") or "inline").strip().lower(),
            "archivio_targhe": archivio_targhe.attivo()}

# ==============================================================================
# POSTS & FEED ENDPOINTS
# ==============================================================================

def _claim_lookup(token):
    """The record a claim token names: posts first, then the v1 archive.

    The v1 records left posts on 25/09/2026 (02 section 3.6); claim tokens
    already sent must still resolve (08 T-20). claim_record_v1 returns the one
    archived row with that token and nothing else. Both answers carry .data.
    """
    res = supabase.table("posts").select("*").eq("claim_token", token).execute()
    if (res and res.data) or not token:
        return res
    return supabase.rpc("claim_record_v1", {"p_token": token}).execute()


# What /api/posts returns. An explicit list, never "*". claim_token is in it:
# it is the public identifier of a plaque, not a secret (decision 25/09/2026,
# task-log). printify_product_id and comment_sent are internal bookkeeping.
PUBLIC_POST_COLUMNS = (
    "id,window_id,platform,external_post_id,author_handle,author_name,post_url,"
    "content_text,category,engagement_score,baseline_score,vpi_ratio,vpi_level,"
    "vpi_level_name,vpi_color,claim_token,created_at,country,subscribers,status,detected_at,"
    "channel_id,channel_handle,format,entered_on,left_on,days_charting,countries,"
    "categories,baseline_computed_at,baseline_samples,baseline_rule,"
    "baseline_span_days,baseline_video_ids,auto_generated_channel,scale_version,"
    "method_version,gap_days,entry_certain,age_at_first_obs_days,vpi_max,"
    "vpi_max_on,views_max,views_final"
)
PRIVATE_POST_COLUMNS = ("printify_product_id", "comment_sent")


@app.get("/api/posts")
def get_posts(
    min_vpi: float = 0,
    limit: int = 50,
    offset: int = 0,
    category: Optional[str] = None,
    country: Optional[str] = None,
    platform: Optional[str] = None,
    status: Optional[str] = None,
    format: Optional[str] = None,
):
    """v2 records. No VPI floor by default: the index is not censored from
    below (01 section 7). min_vpi > 0 filters, and then excludes records
    whose baseline was not computable (they have no VPI)."""
    try:
        if not supabase:
            return {"posts": [], "total": 0}
        query = (supabase.table("posts").select(PUBLIC_POST_COLUMNS, count="exact")
                 .eq("method_version", "v2"))
        if min_vpi and min_vpi > 0:
            query = query.gte("vpi_ratio", min_vpi)
        if status and status.upper() != "ALL":
            query = query.eq("status", status.upper())
        if format and format.upper() != "ALL":
            query = query.eq("format", format.upper())
        if category and category != "ALL":
            query = query.contains("categories", [category])
        if country and country != "ALL":
            query = query.contains("countries", [country.upper()])
        if platform and platform != "ALL":
            query = query.eq("platform", platform.upper())
        res = query.order("detected_at", desc=True).range(offset, offset + limit - 1).execute()
        return {"posts": res.data or [],
                "total": res.count if res.count is not None else len(res.data or [])}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e) or repr(e))

# ==============================================================================
# ANALYTICS ENDPOINTS - day 1 only, never pooled (01 section 4.2)
# ==============================================================================
#
# Every cross-video figure is read at day_index = 1, the only index every
# record has by construction. Records first seen after a gap
# (entry_certain = false) are left out: these figures filter on the entry
# date. And no figure is ever computed across baseline bands or across
# formats: chart entry needs absolute views, so a pooled figure would move
# with who happened to chart that day. Each cell carries its n.

# Decade bands of the frozen baseline. The docs name the 100 and 100,000
# edges (01 section 8); the intermediate edges are powers of ten.
BASELINE_BANDS = (
    (0, 100, "<100"),
    (100, 1_000, "100-1k"),
    (1_000, 10_000, "1k-10k"),
    (10_000, 100_000, "10k-100k"),
    (100_000, float("inf"), ">=100k"),
)

TIMEFRAMES = {"today": 0, "7d": 7, "30d": 30, "all": None}

DAY1_POST_COLUMNS = (
    "id, external_post_id, format, baseline_score, baseline_rule, country, countries, "
    "category, categories, entered_on, age_at_first_obs_days, entry_certain, "
    "method_version, status, content_text, author_name, author_handle, post_url, "
    "vpi_max, vpi_max_on, days_charting"
)


def baseline_band(baseline):
    if baseline is None:
        return None
    b = float(baseline)
    for lo, hi, name in BASELINE_BANDS:
        if lo <= b < hi:
            return name
    return None


def _median(values):
    return float(statistics.median(values)) if values else None


def _since(timeframe):
    if timeframe not in TIMEFRAMES:
        raise HTTPException(status_code=400,
                            detail=f"timeframe must be one of {sorted(TIMEFRAMES)}")
    days = TIMEFRAMES[timeframe]
    if days is None:
        return None
    return (datetime.now(timezone.utc).date() - timedelta(days=days)).isoformat()


def _day1_rows(since=None, country=None, category=None, format=None):
    """post_daily at day_index = 1, joined to its v2 record, certain entries only."""
    rows, offset, page = [], 0, 1000
    while True:
        q = (supabase.table("post_daily")
             .select(f"day, day_index, views, vpi_ratio, posts!inner({DAY1_POST_COLUMNS})")
             .eq("day_index", 1)
             .eq("posts.method_version", "v2")
             .eq("posts.entry_certain", True))
        if since:
            q = q.gte("posts.entered_on", since)
        if country and country != "ALL":
            q = q.contains("posts.countries", [country.upper()])
        if category and category != "ALL":
            q = q.contains("posts.categories", [category])
        if format and format != "ALL":
            q = q.eq("posts.format", format.upper())
        batch = q.range(offset, offset + page - 1).execute().data or []
        rows.extend(batch)
        if len(batch) < page:
            return rows
        offset += page


def _cells(rows):
    """[{baseline_band, format, n, median_vpi}] over rows that have a VPI."""
    groups = {}
    for r in rows:
        p = r["posts"]
        band = baseline_band(p.get("baseline_score"))
        if band is None or r.get("vpi_ratio") is None:
            continue
        groups.setdefault((band, p["format"]), []).append(float(r["vpi_ratio"]))
    order = [b[2] for b in BASELINE_BANDS]
    return [{"baseline_band": band, "format": fmt, "n": len(v), "median_vpi": _median(v)}
            for (band, fmt), v in sorted(groups.items(), key=lambda kv: (order.index(kv[0][0]), kv[0][1]))]


@app.get("/api/analytics/top10")
def get_top10_analytics(
    timeframe: str = "7d",
    country: Optional[str] = None,
    category: Optional[str] = None,
    format: Optional[str] = None,
    platform: Optional[str] = None,
    limit: int = 300,
):
    """Top VPI on the first day observed in Most Popular (01 section 4.2).

    Not age-adjusted: age at first observation is disclosed with n. The
    timeframe filters on entered_on, the day we first observed the video.
    """
    since = _since(timeframe)
    try:
        if not supabase:
            return {"timeframe": timeframe, "day_index": 1, "n": 0, "top10": []}
        rows = [r for r in _day1_rows(since, country, category, format)
                if r.get("vpi_ratio") is not None]
        rows.sort(key=lambda r: float(r["vpi_ratio"]), reverse=True)
        ages = [r["posts"]["age_at_first_obs_days"] for r in rows
                if r["posts"].get("age_at_first_obs_days") is not None]
        top = rows[:min(max(limit, 10), 1000)]
        return {
            "timeframe": timeframe,
            "day_index": 1,
            "label": "VPI on the first day observed in Most Popular. Not age-adjusted.",
            "n": len(rows),
            "age_at_first_obs_days": {"min": min(ages) if ages else None,
                                      "median": _median(ages),
                                      "max": max(ages) if ages else None},
            "top10": [{**r["posts"], "vpi_day1": float(r["vpi_ratio"]), "views_day1": r["views"],
                       "baseline_band": baseline_band(r["posts"].get("baseline_score"))}
                      for r in top],
        }
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e) or repr(e))


@app.get("/api/analytics/insights")
def get_insights_analytics():
    """Day-1 VPI by country, category and macro-region, each by baseline band
    and format, with n. Never pooled (01 section 4.2)."""
    return _statistiche_in_memoria("insights", _calcola_insights)


def _calcola_insights():
    try:
        if not supabase:
            return {"day_index": 1, "by_country": {}, "by_category": {}, "macro_regions": {}}
        rows = _day1_rows()
        country_to_region = {c: reg for reg, cs in MACRO_REGIONS.items() for c in cs}
        by_country, by_category, by_region = {}, {}, {}
        for r in rows:
            p = r["posts"]
            for c in p.get("countries") or []:
                by_country.setdefault(c, []).append(r)
            for k in p.get("categories") or []:
                by_category.setdefault(k, []).append(r)
            for reg in {country_to_region[c] for c in (p.get("countries") or []) if c in country_to_region}:
                by_region.setdefault(reg, []).append(r)
        return {
            "day_index": 1,
            "baseline_bands": [b[2] for b in BASELINE_BANDS],
            "by_country": {k: _cells(v) for k, v in sorted(by_country.items())},
            "by_category": {k: _cells(v) for k, v in sorted(by_category.items())},
            "macro_regions": {k: _cells(v) for k, v in sorted(by_region.items())},
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e) or repr(e))


@app.get("/api/analytics/keywords")
def get_viral_keywords(min_vpi: float = 5.0, limit: int = 30):
    """Title words of records with day-1 VPI >= min_vpi, per baseline band
    and format, with n. Never pooled (01 section 4.2)."""
    return _statistiche_in_memoria(f"keywords:{min_vpi}:{limit}",
                                   lambda: _calcola_keywords(min_vpi, limit))


def _calcola_keywords(min_vpi: float, limit: int):
    try:
        if not supabase:
            return {"day_index": 1, "min_vpi": min_vpi, "segments": []}
        groups = {}
        for r in _day1_rows():
            p = r["posts"]
            band = baseline_band(p.get("baseline_score"))
            if band is None or r.get("vpi_ratio") is None or float(r["vpi_ratio"]) < min_vpi:
                continue
            groups.setdefault((band, p["format"]), []).append((p.get("content_text") or "", float(r["vpi_ratio"])))
        order = [b[2] for b in BASELINE_BANDS]
        segments = []
        for (band, fmt), items in sorted(groups.items(), key=lambda kv: (order.index(kv[0][0]), kv[0][1])):
            words = {}
            for title, vpi in items:
                for w in set(re.findall(r'\b[a-zA-Z0-9]{3,}\b', title.lower())) - STOP_WORDS:
                    words.setdefault(w, []).append(vpi)
            kws = sorted(({"keyword": w, "frequency": len(v), "median_vpi": _median(v)}
                          for w, v in words.items()),
                         key=lambda k: (k["frequency"], k["median_vpi"]), reverse=True)[:limit]
            segments.append({"baseline_band": band, "format": fmt, "n": len(items), "keywords": kws})
        return {"day_index": 1, "min_vpi": min_vpi, "segments": segments}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e) or repr(e))

# ==============================================================================
# TROPHY & CHECKOUT ENDPOINTS
# ==============================================================================

@app.post("/api/trophy/generate")
async def api_generate_trophy(data: TrophyRequest, x_iosa_admin_key: str = Header(None)):
    if not ADMIN_API_KEY or x_iosa_admin_key != ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        image_path = await generate_trophy_png(
            record_id=data.record_id,
            vpi_score=data.vpi_ratio,
            user_handle=data.author,
            content_title=data.content_title,
            e_act=data.e_act,
            e_base=data.e_base,
            gamma=data.gamma,
            recorded_date=data.date_str,
            level_name=data.level_name
        )

        product_id, variant_id = generate_and_publish_trophy(
            author=data.author,
            vpi_ratio=data.vpi_ratio,
            level_name=data.level_name,
            content_title=data.content_title,
            date_str=data.date_str
        )
        
        return {
            "status": "success", 
            "image_path": image_path,
            "printify_product_id": product_id,
            "printify_variant_id": variant_id
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e) or repr(e))

@app.get("/api/trophy/preview")
async def get_trophy_preview(
    claim_token: str = None,
    recorded_date: str = None,
    measured_date: str = None,
    author: str = "@TEARDOWNMAYHEM", 
    vpi: str = "+8.7x",
    title: str = None,
    e_act: str = "87.2K",
    e_base: str = "10.0K",
    gamma: str = "1.0x",
    level_name: str = None
):
    try:
        resolved_title = title
        resolved_record_id = claim_token
        resolved_level_name = level_name
        req_date = recorded_date
        misura_date = None
        req_misura = measured_date

        if supabase and claim_token:
            try:
                res = _claim_lookup(claim_token)
                
                if res and res.data and len(res.data) > 0:
                    post = res.data[0]
                    author = post.get("author_handle") or author
                    resolved_title = post.get("content_text") or resolved_title
                    resolved_record_id = post.get("claim_token") or claim_token
                    resolved_level_name = post.get("vpi_level_name") or resolved_level_name
                    
                    if post.get("vpi_ratio") is not None:
                        raw_vpi = post.get("vpi_ratio")
                        try:
                            v_float = float(raw_vpi)
                            vpi = f"+{v_float:.1f}x"
                        except (ValueError, TypeError):
                            vpi = str(raw_vpi)
                            if not vpi.startswith("+"):
                                vpi = f"+{vpi}"

                    if post.get("engagement_score") is not None:
                        e_act = str(post.get("engagement_score"))

                    if post.get("baseline_score") is not None:
                        e_base = str(post.get("baseline_score"))

                    if post.get("created_at"):
                        req_date = str(post.get("created_at"))[:10]

                    # La targa porta due date: quando il video e' uscito e
                    # quando lo abbiamo misurato. Il conteggio e' congelato
                    # alla seconda, e senza dirlo la prima si presterebbe a
                    # essere letta come la data delle visualizzazioni.
                    if post.get("detected_at"):
                        misura_date = str(post.get("detected_at"))[:10]
            except Exception as db_err:
                log.info(f"Error fetching post details for trophy preview: {db_err}")
        
        if not resolved_title:
            resolved_title = "Viral Content Title"

        if resolved_record_id:
            cache_key = _safe_record_id(resolved_record_id)
        else:
            # Senza claim_token la targa e' un esempio: la chiave nasce dai
            # parametri, altrimenti due esempi diversi finirebbero sullo stesso
            # file in archivio e il secondo riceverebbe l'immagine del primo.
            impronta = hashlib.sha1("|".join([
                str(author), str(vpi), str(resolved_title), str(e_act),
                str(e_base), str(gamma), str(resolved_level_name),
                str(req_date), str(req_misura),
            ]).encode("utf-8")).hexdigest()[:12]
            cache_key = _safe_record_id(f"preview_{impronta}")
        nome_archivio = f"{cache_key}.png"

        # 1. Archivio su Storage: sopravvive ai riavvii ed e' servito dal CDN,
        #    quindi il backend esce dal percorso. E' il caso normale.
        if archivio_targhe.esiste(nome_archivio):
            return RedirectResponse(archivio_targhe.url_pubblico(nome_archivio),
                                    status_code=307)

        # 2. File locale: vale solo finche' vive questo processo, ma evita di
        #    rendere due volte la stessa targa nello stesso minuto.
        cached = _cached_render(cache_key)
        if cached:
            archivio_targhe.carica(nome_archivio, cached)
            return FileResponse(str(cached), media_type="image/png")

        # 3. Si rende. Dodici-venti secondi, e deve capitare una volta sola
        #    per targa nella vita del progetto.
        async with RENDER_SEMAPHORE:
            cached = _cached_render(cache_key)
            if not cached:
                cached = await generate_trophy_png(
                    record_id=cache_key,
                    vpi_score=vpi,
                    user_handle=author,
                    content_title=resolved_title,
                    e_act=e_act,
                    e_base=e_base,
                    gamma=gamma,
                    recorded_date=req_date or "2026-08-20",
                    measured_date=misura_date or req_misura or req_date or "2026-08-20",
                    level_name=resolved_level_name
                )

        url = archivio_targhe.carica(nome_archivio, cached)
        if url:
            return RedirectResponse(url, status_code=307)
        # Archiviazione non riuscita: si serve comunque il file appena reso e
        # si riprovera' alla prossima richiesta.
        return FileResponse(str(cached), media_type="image/png")
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e) or repr(e))

@app.get("/api/trophy/preview-mug")
async def get_trophy_mug_preview(
    author: str = "@TEARDOWNMAYHEM",
    vpi: str = "+8.7x",
    record_id: str = "PREVIEW_MUG_REC"
):
    try:
        # L'anteprima della tazza e' un campione uguale per tutti: il nome del
        # creator e il VPI non finiscono nell'immagine, come dice la didascalia
        # sotto di essa. Quindi in archivio ne basta una sola, e da li' la
        # prendono tutti dal CDN invece di aspettare venti secondi di
        # impaginazione. Il nome dipende dall'immagine di partenza: se si
        # cambia campione, cambia il nome e l'archivio si rinnova da solo.
        nome_archivio = f"mug_{impronta_campione_tazza()}.png"
        if archivio_targhe.esiste(nome_archivio):
            return RedirectResponse(archivio_targhe.url_pubblico(nome_archivio),
                                    status_code=307)

        async with RENDER_SEMAPHORE:
            image_path = await generate_mug_preview_png(
                record_id=_safe_record_id(record_id),
                vpi_score=vpi,
                user_handle=author
            )

        url = archivio_targhe.carica(nome_archivio, Path(image_path))
        if url:
            return RedirectResponse(url, status_code=307)
        return FileResponse(image_path, media_type="image/png")
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e) or repr(e))

@app.post("/api/claim/initialize/{token}")
async def initialize_claim_product(token: str):
    try:
        if not supabase:
            return {"status": "ready", "token": token}

        db_res = _claim_lookup(token)
        post_data = db_res.data[0] if db_res.data else None

        if not post_data:
            raise HTTPException(status_code=404, detail="Token not found")

        return {"status": "ready", "token": token}

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e) or repr(e))

@app.post("/api/checkout/create-session")
def create_checkout_session(req: CheckoutSessionRequest):
    if not ENABLE_ORDERS:
        raise HTTPException(
            status_code=503,
            detail="Commemorative items are temporarily unavailable. The digital plaque remains free to download."
        )
    try:
        unit_amount = PRODUCT_CATALOG.get(DEFAULT_PRODUCT_KEY, 1900)
        
        vpi_ratio = "+8.7x"
        level_name = None  # se manca, viene calcolato dal VPI
        content_title = "Viral Performance Accreditation"
        date_str = "2026-08-20"
        e_act_meta = "N/A"
        e_base_meta = "N/A"

        if supabase and req.claimToken:
            try:
                res = _claim_lookup(req.claimToken)
                if res.data and len(res.data) > 0:
                    p = res.data[0]
                    raw_vpi = p.get("vpi_ratio", 8.7)
                    try:
                        v_float = float(raw_vpi)
                        vpi_ratio = f"+{v_float:.1f}x"
                    except (ValueError, TypeError):
                        vpi_ratio = str(raw_vpi)
                        if not vpi_ratio.startswith("+"):
                            vpi_ratio = f"+{vpi_ratio}"
                    
                    level_name = p.get("vpi_level_name", level_name)
                    content_title = p.get("content_text") or content_title
                    if p.get("created_at"):
                        date_str = str(p.get("created_at"))[:10]
                    if p.get("engagement_score") is not None:
                        e_act_meta = str(p.get("engagement_score"))
                    if p.get("baseline_score") is not None:
                        e_base_meta = str(p.get("baseline_score"))
            except Exception as err:
                log.info(f"Error fetching metadata for checkout session: {err}")

        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            customer_email=req.email,
            shipping_address_collection={
                'allowed_countries': [
                    'US', 'GB', 'AT', 'BE', 'BG', 'CY', 'CZ', 'DE', 'DK', 'EE', 
                    'ES', 'FI', 'FR', 'GR', 'HR', 'HU', 'IE', 'IT', 'LT', 'LU', 
                    'LV', 'MT', 'NL', 'PL', 'PT', 'RO', 'SE', 'SI', 'SK'
                ]
            },
            shipping_options=_build_shipping_options(),
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': f'IOSA Official Award Trophy — {req.authorHandle}',
                        'description': req.productType,
                    },
                    'unit_amount': unit_amount,
                },
                'quantity': 1,
            }],
            metadata={
                'claim_token': req.claimToken,
                'creator_name': req.authorHandle,
                'recipient_name': req.name,
                'product_type': req.productType,
                'vpi_ratio': vpi_ratio,
                'level_name': level_name,
                'content_title': content_title,
                'date_str': date_str,
                'e_act': e_act_meta,
                'e_base': e_base_meta
            },
            mode='payment',
            success_url=f'{FRONTEND_URL}/claim/{req.claimToken}?status=success',
            cancel_url=f'{FRONTEND_URL}/claim/{req.claimToken}?status=cancelled',
        )
        return {"checkout_url": checkout_session.url}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e) or repr(e))

def _is_duplicate(err) -> bool:
    text = f"{getattr(err, 'code', '')} {err}"
    return "23505" in text or "duplicate key" in text


def _reserve_order(session_id, record, metadata):
    """Reserve a Stripe session in claims before ordering.

    True: reserved, go ahead. False: this session was already handled (a
    repeated webhook). None: the guard cannot run (no service client or no
    session id), and then nothing is ordered. Written with the service role:
    claims is private (SEC-1) and the anon key cannot write it. No personal
    data is stored here: Stripe and Printify hold the address.
    """
    if not supabase_service or not session_id:
        return None
    row = {"stripe_session_id": session_id, "status": "PROCESSING",
           "product_selected": (metadata or {}).get("product_key") or DEFAULT_PRODUCT_KEY}
    if record and record.get("method_version") == "v2" and record.get("id"):
        row["post_id"] = record["id"]           # v1 records live in posts_v1: no FK
    try:
        supabase_service.table("claims").insert(row).execute()
        return True
    except Exception as err:
        if _is_duplicate(err):
            return False
        raise


def _record_order(session_id, record, claim_token, status, product_id):
    """The order's outcome: claims.status, and printify_product_id on the
    record when it is in posts. The archive (posts_v1) is never written: its
    checksum is the proof that the v1 rows were moved unchanged. Service role:
    the anon key has no UPDATE on posts, and that write used to be lost."""
    if not supabase_service:
        return
    try:
        supabase_service.table("claims").update({"status": status}).eq(
            "stripe_session_id", session_id).execute()
        if claim_token and record and record.get("method_version") == "v2":
            supabase_service.table("posts").update({"printify_product_id": product_id}).eq(
                "claim_token", claim_token).execute()
    except Exception as err:
        log.info(f"Failed to record the order state: {err}")


@app.post("/api/webhooks/stripe")
async def stripe_webhook(request: Request, stripe_signature: str = Header(None)):
    payload = await request.body()

    if not STRIPE_WEBHOOK_SECRET:
        log.warning("[WEBHOOK] STRIPE_WEBHOOK_SECRET non configurato: richiesta rifiutata.")
        raise HTTPException(status_code=500, detail="Webhook secret not configured")

    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"Webhook Error: {str(e)}")
    
    if event.get("type") == "checkout.session.completed":
        session = event.get("data", {}).get("object", {})
        metadata = session.get("metadata", {})
        
        claim_token = metadata.get("claim_token")
        stripe_session_id = session.get("id") or ""
        
        shipping_details = session.get("shipping_details") or {}
        customer_details = session.get("customer_details") or {}
        shipping_legacy = session.get("shipping") or {}

        address = shipping_details.get("address") or customer_details.get("address") or shipping_legacy.get("address") or {}
        name = shipping_details.get("name") or customer_details.get("name") or shipping_legacy.get("name") or metadata.get("recipient_name") or "Creator IOSA"

        name_parts = name.strip().split(" ")
        first_name = name_parts[0] if name_parts else "Creator"
        last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else "IOSA"

        country_code = (address.get("country") or "IT").upper()

        shipping_info = {
            "first_name": first_name,
            "last_name": last_name,
            "email": customer_details.get("email", "") or session.get("customer_email", ""),
            "phone": customer_details.get("phone", "") or shipping_details.get("phone", ""),
            "country": country_code,
            "state": address.get("state", "") or "",
            "city": address.get("city", "") or "",
            "line1": address.get("line1", "") or "",
            "line2": address.get("line2", "") or "",
            "postal_code": address.get("postal_code", "") or ""
        }

        author = metadata.get("creator_name", "Creator")
        vpi_ratio = metadata.get("vpi_ratio", "+8.7x")
        level_name = metadata.get("level_name") or None  # se manca, calcolato dal VPI
        content_title = metadata.get("content_title", "Viral Performance Accreditation")
        date_str = metadata.get("date_str", "2026-08-20")
        e_act = metadata.get("e_act", "N/A")
        e_base = metadata.get("e_base", "N/A")
        record = None

        if supabase and claim_token:
            try:
                db_res = _claim_lookup(claim_token)
                if db_res.data and len(db_res.data) > 0:
                    p = db_res.data[0]
                    record = p
                    author = p.get("author_handle") or author
                    raw_vpi = p.get("vpi_ratio") or vpi_ratio
                    try:
                        v = float(raw_vpi)
                        vpi_ratio = f"+{v:.1f}x"
                    except (ValueError, TypeError):
                        vpi_ratio = str(raw_vpi)
                        if not vpi_ratio.startswith("+"):
                            vpi_ratio = f"+{vpi_ratio}"
                    level_name = p.get("vpi_level_name") or level_name
                    content_title = p.get("content_text") or content_title
                    if p.get("created_at"):
                        date_str = str(p.get("created_at"))[:10]
                    if p.get("engagement_score") is not None:
                        e_act = str(p.get("engagement_score"))
                    if p.get("baseline_score") is not None:
                        e_base = str(p.get("baseline_score"))
            except Exception as err:
                log.info(f"Error fetching post details for token {claim_token}: {err}")

        # Idempotency: one Stripe session, one order. Stripe delivers a webhook
        # at least once, so a repeat must not place a second paid Printify
        # order. The session is reserved in claims (private, service role)
        # before anything is ordered; the unique index rejects the second one.
        reserved = _reserve_order(stripe_session_id, record, metadata)
        if reserved is None:
            log.warning("[WEBHOOK] Guard unavailable (no service key or no session id): no order placed.")
            return {"status": "error_recorded", "detail": "idempotency guard unavailable"}
        if reserved is False:
            log.info(f"[WEBHOOK] Session {stripe_session_id} already handled, nessuna azione.")
            return {"status": "already_fulfilled"}

        log.info(f"🚀 STARTING ORDER FULFILLMENT for {author} (Destination: {country_code})...")

        try:
            order_result = fulfill_trophy_order(
                author=author,
                vpi_ratio=vpi_ratio,
                level_name=level_name,
                content_title=content_title,
                date_str=date_str,
                shipping_address=shipping_info,
                e_act=e_act,
                e_base=e_base,
                claim_token=claim_token,
                external_ref=stripe_session_id
            )

            product_id = order_result.get("product_id")
            _record_order(stripe_session_id, record, claim_token, "FULFILLED", product_id)

            log.info(f"✅ FULFILLMENT COMPLETE! Printify Order ID: {order_result.get('order_id')}")

        except Exception as err:
            log.info(f"❌ ERROR DURING ORDER FULFILLMENT: {err}")
            traceback.print_exc()
            _record_order(stripe_session_id, record, claim_token, "FAILED", "FAILED_ORDER_ERROR")

            # Rispondiamo 200: un 500 farebbe ritentare Stripe e ogni tentativo
            # creerebbe un nuovo ordine Printify a pagamento.
            return {"status": "error_recorded", "detail": str(err)}

    return {"status": "success"}