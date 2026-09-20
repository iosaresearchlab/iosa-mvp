import sys
import asyncio
import json
import time
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
from generate_trophy import generate_trophy_png, generate_mug_preview_png
from vpi_engine import esegui_un_ciclo, start_engine

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


def _giro_di_ingestione():
    global _ingestione_in_corso
    try:
        esiti = esegui_un_ciclo()
        log.info("ingestione su richiesta conclusa: %s", esiti)
    finally:
        _ingestione_in_corso = False


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

    _ingestione_in_corso = True
    background.add_task(_giro_di_ingestione)
    return {"stato": "avviato"}

ALLOWED_ORIGINS = [o for o in [
    FRONTEND_URL,
    "http://localhost:3000",
    "https://iosaresearch.com",
    "https://www.iosaresearch.com",
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

@app.get("/api/posts")
def get_posts(
    min_vpi: float = 1.4,
    limit: int = 50,
    offset: int = 0,
    category: Optional[str] = None,
    country: Optional[str] = None,
    platform: Optional[str] = None
):
    """Serves real outliers (VPI >= min_vpi) to the Front-End feed."""
    try:
        if not supabase:
            return {"posts": [], "total": 0}

        query = supabase.table("posts").select("*", count="exact").gte("vpi_ratio", min_vpi).eq("status", "ACTIVE")

        if category and category != "ALL":
            query = query.eq("category", category)
        if country and country != "ALL":
            query = query.eq("country", country)
        if platform and platform != "ALL":
            query = query.eq("platform", platform.upper())

        query = query.order("detected_at", desc=True).range(offset, offset + limit - 1)
        res = query.execute()

        return {
            "posts": res.data or [],
            "total": res.count if res.count is not None else len(res.data or [])
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e) or repr(e))

# ==============================================================================
# ANALYTICS ENDPOINTS
# ==============================================================================

@app.get("/api/analytics/top10")
def get_top10_analytics(
    timeframe: str = "7d",
    country: Optional[str] = None,
    category: Optional[str] = None,
    platform: Optional[str] = None,
    limit: int = 300
):
    """Returns top viral contents with highest VPI from DB for the specified timeframe (7d, 15d, 24h)."""
    try:
        if not supabase:
            return {"timeframe": timeframe, "top10": []}

        if timeframe == "15d":
            cutoff = (datetime.now(timezone.utc) - timedelta(days=15)).isoformat()
        elif timeframe == "24h":
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        else:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

        query = supabase.table("posts").select("*").gte("created_at", cutoff).eq("status", "ACTIVE")

        if country and country != "ALL":
            query = query.eq("country", country)
        if category and category != "ALL":
            query = query.eq("category", category)
        if platform and platform != "ALL":
            query = query.eq("platform", platform.upper())

        fetch_limit = min(max(limit, 10), 1000)
        query = query.order("vpi_ratio", desc=True).limit(fetch_limit)
        res = query.execute()

        return {
            "timeframe": timeframe,
            "top10": res.data or []
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e) or repr(e))

@app.get("/api/analytics/insights")
def get_insights_analytics():
    """Aggregates DB metrics by country, category, and macro-regions."""
    return _statistiche_in_memoria("insights", _calcola_insights)


def _calcola_insights():
    try:
        if not supabase:
            return {"by_country": {}, "by_category": {}, "macro_regions": {}}

        data = _fetch_all_rows("posts", "country, category, vpi_ratio", status="ACTIVE")

        country_stats = {}
        category_stats = {}
        region_stats = {r: {"vpi_sum": 0.0, "count": 0} for r in MACRO_REGIONS}

        country_to_region = {}
        for region, countries in MACRO_REGIONS.items():
            for c in countries:
                country_to_region[c] = region

        for item in data:
            c = item.get("country", "OTHER")
            cat = item.get("category", "Uncategorized")
            vpi = float(item.get("vpi_ratio") or 1.0)

            # Country aggregation
            if c not in country_stats:
                country_stats[c] = {"vpi_sum": 0.0, "count": 0}
            country_stats[c]["vpi_sum"] += vpi
            country_stats[c]["count"] += 1

            # Category aggregation
            if cat not in category_stats:
                category_stats[cat] = {"vpi_sum": 0.0, "count": 0}
            category_stats[cat]["vpi_sum"] += vpi
            category_stats[cat]["count"] += 1

            # Region aggregation
            reg = country_to_region.get(c)
            if reg:
                region_stats[reg]["vpi_sum"] += vpi
                region_stats[reg]["count"] += 1

        by_country = {
            c: {
                "avg_vpi": round(s["vpi_sum"] / s["count"], 2) if s["count"] > 0 else 0.0,
                "outlier_count": s["count"]
            }
            for c, s in country_stats.items()
        }

        by_category = {
            cat: {
                "avg_vpi": round(s["vpi_sum"] / s["count"], 2) if s["count"] > 0 else 0.0,
                "outlier_count": s["count"]
            }
            for cat, s in category_stats.items()
        }

        macro_regions = {
            reg: {
                "avg_vpi": round(s["vpi_sum"] / s["count"], 2) if s["count"] > 0 else 0.0,
                "outlier_count": s["count"]
            }
            for reg, s in region_stats.items()
        }

        return {
            "by_country": by_country,
            "by_category": by_category,
            "macro_regions": macro_regions
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e) or repr(e))

@app.get("/api/analytics/keywords")
def get_viral_keywords(min_vpi: float = 5.0, limit: int = 30):
    """Tokenizes video titles (VPI >= min_vpi) and computes frequency & viral velocity per word."""
    return _statistiche_in_memoria(f"keywords:{min_vpi}:{limit}",
                                   lambda: _calcola_keywords(min_vpi, limit))


def _calcola_keywords(min_vpi: float, limit: int):
    try:
        if not supabase:
            return {"keywords": []}

        rows = _fetch_all_rows("posts", "content_text, vpi_ratio", status="ACTIVE")
        data = [r for r in rows if float(r.get("vpi_ratio") or 0) >= min_vpi]

        kw_stats = {}

        for item in data:
            title = item.get("content_text") or ""
            vpi = float(item.get("vpi_ratio") or min_vpi)
            
            words = re.findall(r'\b[a-zA-Z0-9]{3,}\b', title.lower())
            seen_in_title = set()
            
            for w in words:
                if w not in STOP_WORDS and w not in seen_in_title:
                    seen_in_title.add(w)
                    if w not in kw_stats:
                        kw_stats[w] = {"frequency": 0, "vpi_sum": 0.0}
                    kw_stats[w]["frequency"] += 1
                    kw_stats[w]["vpi_sum"] += vpi

        result = []
        for word, s in kw_stats.items():
            avg_vpi = round(s["vpi_sum"] / s["frequency"], 2)
            result.append({
                "keyword": word,
                "frequency": s["frequency"],
                "viral_velocity": avg_vpi
            })

        result.sort(key=lambda x: (x["frequency"], x["viral_velocity"]), reverse=True)

        return {"keywords": result[:limit]}
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

        if supabase and claim_token:
            try:
                res = supabase.table("posts").select("*").eq("claim_token", claim_token).execute()
                
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
            except Exception as db_err:
                log.info(f"Error fetching post details for trophy preview: {db_err}")
        
        if not resolved_title:
            resolved_title = "Viral Content Title"

        cache_key = _safe_record_id(resolved_record_id or "preview")
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
        async with RENDER_SEMAPHORE:
            image_path = await generate_mug_preview_png(
                record_id=_safe_record_id(record_id),
                vpi_score=vpi,
                user_handle=author
            )
        return FileResponse(image_path, media_type="image/png")
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e) or repr(e))

@app.post("/api/claim/initialize/{token}")
async def initialize_claim_product(token: str):
    try:
        if not supabase:
            return {"status": "ready", "token": token}

        db_res = supabase.table("posts").select("*").eq("claim_token", token).execute()
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
                res = supabase.table("posts").select("*").eq("claim_token", req.claimToken).execute()
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
        already_fulfilled = False

        if supabase and claim_token:
            try:
                db_res = supabase.table("posts").select("*").eq("claim_token", claim_token).execute()
                if db_res.data and len(db_res.data) > 0:
                    p = db_res.data[0]
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

                    # Idempotenza: se l'ordine e' gia' stato evaso non lo ripetiamo.
                    prev = p.get("printify_product_id")
                    if prev and not str(prev).startswith("FAILED"):
                        already_fulfilled = True
            except Exception as err:
                log.info(f"Error fetching post details for token {claim_token}: {err}")

        if already_fulfilled:
            log.info(f"[WEBHOOK] Ordine gia' evaso per {claim_token}, nessuna azione.")
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
            if supabase and claim_token and product_id:
                supabase.table("posts").update({"printify_product_id": product_id}).eq("claim_token", claim_token).execute()
                
            log.info(f"✅ FULFILLMENT COMPLETE! Printify Order ID: {order_result.get('order_id')}")
            
        except Exception as err:
            log.info(f"❌ ERROR DURING ORDER FULFILLMENT: {err}")
            traceback.print_exc()
            
            if supabase and claim_token:
                try:
                    supabase.table("posts").update({"printify_product_id": "FAILED_ORDER_ERROR"}).eq("claim_token", claim_token).execute()
                except Exception as db_err:
                    log.info(f"Failed to update DB error state: {db_err}")

            # Rispondiamo 200: un 500 farebbe ritentare Stripe e ogni tentativo
            # creerebbe un nuovo ordine Printify a pagamento.
            return {"status": "error_recorded", "detail": str(err)}

    return {"status": "success"}