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
from apscheduler.schedulers.background import BackgroundScheduler

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

# Cache persistenti: a budget zero la quota API e' la risorsa piu' scarsa.
_SHORT_CHECK_CACHE = TTLCache("short_checks", 30 * 86400)
_BASELINE_CACHE = TTLCache("channel_baselines", 7 * 86400)

# Intervallo fra due cicli di ingestion, in minuti.
INGEST_INTERVAL_MINUTES = int(os.getenv("INGEST_INTERVAL_MINUTES", "60"))

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

# TikTok OAuth 2.0 Credentials for dynamic token generation (API v2)
TIKTOK_CLIENT_KEY = os.getenv("TIKTOK_CLIENT_KEY")
TIKTOK_CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET")

BASE_DOMAIN = os.getenv("NEXT_PUBLIC_SITE_URL", "https://iosaresearch.com")
OPTOUT_EMAIL = os.getenv("OPTOUT_EMAIL", "iosa.research.lab@gmail.com")

# Maximum subscriber threshold (increased to 1.5M to include small/medium channels)
MAX_SUBSCRIBERS = 1_500_000 
MIN_SUBSCRIBERS = 1_000

# Global Country/Category map (Expanded global rotation)
TARGET_COUNTRIES = [
    'US', 'IT', 'GB', 'DE', 'FR', 'ES', 'BR', 'JP', 'IN', 'CA', 'AU',
    'MX', 'AR', 'KR', 'NL', 'PL', 'SE', 'NO', 'FI', 'DK', 'ZA', 'TR',
    'CH', 'AT', 'BE', 'PT', 'IE', 'NZ', 'CL', 'CO', 'PH', 'ID', 'TH', 'VN'
]

CATEGORY_MAP = {
    '1': 'Film & Animation',
    '2': 'Autos & Vehicles',
    '10': 'Music',
    '15': 'Pets & Animals',
    '17': 'Sports',
    '19': 'Travel & Events',
    '20': 'Gaming',
    '22': 'People & Blogs',
    '23': 'Comedy',
    '24': 'Entertainment',
    '25': 'News & Politics',
    '26': 'Howto & Style',
    '27': 'Education',
    '28': 'Tech',
    '29': 'Nonprofits & Activism'
}

# I template di commento automatico su YouTube sono stati rimossi il 20/09/2026.
# Promettevano 'certified report', 'accredited award' e 'official physical trophy':
# linguaggio falso (non accreditiamo nessuno, non esiste nessun premio fisico) e
# commento automatico sotto i video altrui, cioe' spam secondo le regole di YouTube.
# Il contatto con i creator passa solo dall'outreach via email, dove il testo e' scritto
# a mano, porta la data di rilevazione e dice che non c'e' niente da pagare.

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("❌ Missing Supabase credentials in environment variables.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def is_real_youtube_short(video_id: str):
    """
    Verifica se un video e' realmente uno Short interrogando il router HTTP di
    YouTube (200 = Short, redirect = video normale).

    L'API ufficiale non espone questo flag, quindi la verifica HTTP resta
    necessaria. Tre regole la rendono sostenibile:
      - viene chiamata una sola volta per video, mai dentro i cicli di baseline;
      - l'esito e' messo in cache per 30 giorni;
      - se la rete fallisce restituisce None ("non so"), non False, cosi' un
        timeout non fa scartare in silenzio un video valido.
    """
    cached = _SHORT_CHECK_CACHE.get(video_id)
    if cached is not None:
        return cached

    url = f"https://www.youtube.com/shorts/{video_id}"
    try:
        response = requests.head(url, allow_redirects=False, timeout=5)
    except requests.RequestException:
        return None

    if response.status_code == 200:
        _SHORT_CHECK_CACHE.set(video_id, True)
        return True
    if response.status_code in (301, 302, 303, 307, 308):
        _SHORT_CHECK_CACHE.set(video_id, False)
        return False
    # 429 o altri errori: non sappiamo, meglio non decidere.
    return None


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


def get_channel_recent_videos_baseline(channel_id: str, formato: str,
                                       exclude_video_id: str = None):
    """Baseline del canale per un formato. Vedi le due funzioni sopra."""
    campioni = get_channel_video_samples(channel_id)
    if campioni is None:
        return None, 0
    return baseline_from_samples(campioni.get(formato, []), exclude_video_id)


def _cached_channel_baseline(channel_id: str, formato: str = FORMATO_SHORT,
                             exclude_video_id: str = None):
    """Baseline del canale per formato, con cache su file (7 giorni).

    In cache finiscono i campioni grezzi di entrambi i formati, non la mediana:
    cosi' misurare uno Short e un video lungo dello stesso canale costa una
    sola lettura, e cambiare le regole della baseline non obbliga a buttare
    via la cache.
    """
    campioni = _BASELINE_CACHE.get(channel_id)
    if campioni is None:
        campioni = get_channel_video_samples(channel_id)
        if campioni is None:
            return None, 0
        _BASELINE_CACHE.set(channel_id, campioni)
    return baseline_from_samples(campioni.get(formato, []), exclude_video_id)


def _filter_already_ingested(video_ids: list) -> set:
    """Restituisce gli id gia' presenti in tabella, in una sola query."""
    if not video_ids:
        return set()
    found = set()
    for i in range(0, len(video_ids), 100):
        chunk = video_ids[i:i + 100]
        try:
            res = supabase.table("posts").select("external_post_id").in_("external_post_id", chunk).execute()
            found.update(row["external_post_id"] for row in (res.data or []))
        except Exception as e:
            log.error(f"Errore nel controllo duplicati: {e}")
    return found


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

def fetch_and_ingest_real_youtube_content():
    """
    Scansiona i trending YouTube e registra gli outlier in Supabase.

    Ordine delle operazioni pensato per la quota: prima i filtri che non
    costano chiamate (durata, eta' di pubblicazione), poi il controllo
    duplicati in blocco, e solo alla fine le baseline, che sono la voce piu'
    cara del ciclo.
    """
    if not YOUTUBE_API_KEY:
        log.warning("YOUTUBE_API_KEY mancante in .env. Ingestion saltata.")
        return

    other_countries = [c for c in TARGET_COUNTRIES if c != 'US']
    selected_countries = ['US'] + random.sample(other_countries, k=2)
    selected_category_ids = random.sample(list(CATEGORY_MAP.keys()), k=1)

    log.info(f"[{datetime.now().strftime('%H:%M:%S')}] Scansione YouTube Shorts "
          f"(paesi: {selected_countries}, categorie: {[CATEGORY_MAP[c] for c in selected_category_ids]})...")

    scanned_total = 0
    skipped_duration = 0
    skipped_age = 0
    skipped_not_short = 0
    skipped_vpi = 0
    skipped_auto = 0
    ingeriti_per_formato = {FORMATO_SHORT: 0, FORMATO_LONG: 0}
    skipped_baseline = 0
    already_exists = 0
    total_ingested = 0

    now_dt = datetime.now(timezone.utc)

    for country in selected_countries:
        for cat_id in selected_category_ids:
            cat_name = CATEGORY_MAP[cat_id]
            items = []

            url_p1 = (
                "https://www.googleapis.com/youtube/v3/videos?"
                "part=snippet,contentDetails,statistics&chart=mostPopular&maxResults=50"
                f"&regionCode={country}&videoCategoryId={cat_id}&key={YOUTUBE_API_KEY}"
            )

            try:
                res1 = requests.get(url_p1, timeout=10)
                if res1.status_code == 403:
                    log.warning(f"[QUOTA] YouTube ha risposto 403 per {country}/{cat_name}: "
                          f"quota giornaliera probabilmente esaurita. Ciclo interrotto.")
                    return
                if res1.status_code == 404:
                    log.warning(f"YouTube 404 per {country}/{cat_name}: combinazione non disponibile.")
                    continue
                if res1.status_code != 200:
                    log.info(f"YouTube {res1.status_code} per {country}/{cat_name}: {res1.text[:200]}")
                    continue

                data1 = res1.json()
                items.extend(data1.get("items", []))
                next_page_token = data1.get("nextPageToken")

                if next_page_token:
                    res2 = requests.get(f"{url_p1}&pageToken={next_page_token}", timeout=10)
                    if res2.status_code == 200:
                        items.extend(res2.json().get("items", []))
            except Exception as e:
                log.error(f"Errore di rete per {country}/{cat_name}: {e}")
                continue

            if not items:
                continue

            # --- filtri a costo zero: durata ed eta' di pubblicazione ---
            candidates = []
            for vid_data in items:
                scanned_total += 1
                duration = parse_iso_duration(vid_data.get("contentDetails", {}).get("duration", ""))
                formato = formato_da_durata(duration)
                if formato is None:
                    # Durata assente o nulla: dirette, premiere, video rimossi.
                    skipped_duration += 1
                    continue
                vid_data["_formato"] = formato

                published_at = vid_data["snippet"].get("publishedAt")
                age_days = age_in_days(published_at, now_dt)
                if age_days is None or age_days > CAMPAIGN_DAYS:
                    skipped_age += 1
                    continue

                candidates.append(vid_data)

            if not candidates:
                continue

            # --- controllo duplicati in una sola query, prima di spendere quota ---
            existing_ids = _filter_already_ingested([c["id"] for c in candidates])
            new_candidates = [c for c in candidates if c["id"] not in existing_ids]
            already_exists += len(candidates) - len(new_candidates)
            if not new_candidates:
                continue

            channels_meta = fetch_channels_metadata([c["snippet"]["channelId"] for c in new_candidates])

            for vid_data in new_candidates:
                vid_id = vid_data["id"]
                snippet = vid_data["snippet"]

                formato = vid_data["_formato"]

                # La verifica HTTP serve solo a smascherare i video corti che
                # YouTube non pubblica come Short. Su un video lungo non ha
                # niente da dire, quindi non si spende una richiesta.
                # None = non so, accettiamo (la durata e' gia' compatibile)
                # invece di scartare in silenzio.
                if formato == FORMATO_SHORT:
                    short_check = is_real_youtube_short(vid_id)
                    if short_check is False:
                        skipped_not_short += 1
                        continue

                ch_id = snippet["channelId"]
                views = float(vid_data["statistics"].get("viewCount", 0))

                ch_info = channels_meta.get(ch_id) or {}
                subscribers = ch_info.get("subscribers")
                channel_handle = ch_info.get("handle")

                # I canali "X - Topic" sono Art Track generati da YouTube per i
                # cataloghi musicali: non hanno handle, non c'e' un creator
                # dietro e la mediana dei loro Shorts non descrive nessuno.
                # Non sono outlier da misurare ne' persone da contattare.
                if not channel_handle:
                    skipped_auto += 1
                    continue

                baseline, samples = _cached_channel_baseline(
                    ch_id, formato, exclude_video_id=vid_id
                )
                if not baseline or baseline < MIN_BASELINE_VIEWS:
                    skipped_baseline += 1
                    continue

                vpi_ratio = calculate_vpi_ratio(views, baseline)
                if vpi_ratio <= MIN_VPI_FOR_INGESTION:
                    skipped_vpi += 1
                    continue

                vpi_level, level_name, vpi_color = get_vpi_metadata(vpi_ratio)
                claim_token = f"iosa_{secrets.token_urlsafe(12)}"
                now_utc = datetime.now(timezone.utc).isoformat()

                try:
                    supabase.table("posts").insert({
                        "platform": "YOUTUBE",
                        "format": formato,
                        "external_post_id": vid_id,
                        # Se YouTube ci da' l'handle vero lo si usa; il ripiego
                        # derivato dal titolo resta solo per i canali senza handle.
                        "author_handle": channel_handle or f"@{snippet['channelTitle'].replace(' ', '')}",
                        "channel_id": ch_id,
                        "channel_handle": channel_handle,
                        "author_name": snippet["channelTitle"],
                        "subscribers": subscribers,
                        "post_url": f"https://www.youtube.com/watch?v={vid_id}",
                        "content_text": snippet["title"],
                        "category": cat_name,
                        "country": country,
                        "engagement_score": views,
                        "baseline_score": baseline,
                        "vpi_ratio": round_vpi(vpi_ratio),
                        "vpi_level": vpi_level,
                        "vpi_level_name": level_name,
                        "vpi_color": vpi_color,
                        "claim_token": claim_token,
                        "status": "ACTIVE",
                        "comment_sent": False,
                        "created_at": snippet["publishedAt"],
                        "detected_at": now_utc
                    }).execute()
                    total_ingested += 1
                    ingeriti_per_formato[formato] += 1
                except Exception as e:
                    log.error(f"Insert fallito per {vid_id}: {e}")

    _SHORT_CHECK_CACHE.purge_expired()
    _BASELINE_CACHE.purge_expired()
    _SHORT_CHECK_CACHE.save()
    _BASELINE_CACHE.save()

    log.info("[INGESTION YOUTUBE]")
    log.info(f"   video analizzati:               {scanned_total}")
    log.info(f"   scartati per durata:            {skipped_duration}")
    log.info(f"   scartati fuori finestra 15gg:   {skipped_age}")
    log.info(f"   scartati perche' non Short:     {skipped_not_short}")
    log.info(f"   gia' presenti nel DB:           {already_exists}")
    log.info(f"   scartati canali auto-generati:  {skipped_auto}")
    log.info(f"   scartati per baseline assente o < {MIN_BASELINE_VIEWS}: {skipped_baseline}")
    log.info(f"   scartati per VPI <= {MIN_VPI_FOR_INGESTION}:        {skipped_vpi}")
    log.info(f"   NUOVI INSERITI:                 {total_ingested}")
    log.info(f"      di cui Short:                {ingeriti_per_formato[FORMATO_SHORT]}")
    log.info(f"      di cui video lunghi:         {ingeriti_per_formato[FORMATO_LONG]}\n")


# ==============================================================================
# TIKTOK INGESTION ENGINE (OFFICIAL API v2)
# ==============================================================================

def get_tiktok_access_token() -> str:
    """Generates an Access Token using TikTok OAuth Client Credentials (API v2)."""
    if not TIKTOK_CLIENT_KEY or not TIKTOK_CLIENT_SECRET:
        return ""
    url = "https://open.tiktokapis.com/v2/oauth/token/"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    payload = {
        "client_key": TIKTOK_CLIENT_KEY,
        "client_secret": TIKTOK_CLIENT_SECRET,
        "grant_type": "client_credentials"
    }
    try:
        res = requests.post(url, headers=headers, data=payload, timeout=10)
        if res.status_code == 200:
            data = res.json()
            return data.get("access_token") or data.get("data", {}).get("access_token", "")
        return ""
    except Exception:
        return ""

def get_tiktok_user_baseline(author_handle: str) -> float | None:
    """Calculates baseline as the MEDIAN play count of recent videos for a TikTok user using TikTok API v2."""
    access_token = get_tiktok_access_token()
    if not access_token:
        return None
    try:
        clean_handle = author_handle.lstrip("@")
        url = "https://open.tiktokapis.com/v2/research/video/query/"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "query": {
                "and": [
                    {"field_name": "username", "operation": "EQ", "field_values": [clean_handle]}
                ]
            },
            "max_count": 20
        }
        res = requests.post(url, headers=headers, json=payload, timeout=10)
        if res.status_code != 200:
            return None
        
        data = res.json().get("data", {})
        videos = data.get("videos") or data.get("posts") or data.get("items") or []
        if not videos:
            return None

        play_counts = []
        for v in videos:
            cnt = v.get("view_count") if v.get("view_count") is not None else v.get("play_count")
            if cnt is not None:
                play_counts.append(float(cnt))

        if not play_counts:
            return None

        median_baseline = float(statistics.median(play_counts))
        return median_baseline if median_baseline > 0 else None
    except Exception:
        return None

def fetch_and_ingest_tiktok_content():
    """Scans TikTok trending videos and ingests outliers into Supabase using TikTok API v2."""
    log.info(f"📡 [{datetime.now().strftime('%H:%M:%S')}] Deep scanning TikTok...")
    
    if not TIKTOK_CLIENT_KEY or not TIKTOK_CLIENT_SECRET:
        log.warning("⚠️ TIKTOK_CLIENT_KEY o TIKTOK_CLIENT_SECRET non configurati. Scansione TikTok saltata.")
        return

    access_token = get_tiktok_access_token()
    if not access_token:
        log.error("⚠️ Impossibile generare Access Token TikTok. Scansione TikTok saltata.")
        return

    selected_countries = random.sample(TARGET_COUNTRIES, k=3)
    scanned_total = 0
    skipped_vpi = 0
    skipped_baseline = 0
    already_exists = 0
    total_ingested = 0

    tiktok_user_baseline_cache = {}

    for country in selected_countries:
        try:
            url = "https://open.tiktokapis.com/v2/research/video/query/"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            payload = {
                "query": {
                    "and": [
                        {"field_name": "region_code", "operation": "EQ", "field_values": [country]}
                    ]
                },
                "max_count": 30
            }
            res = requests.post(url, headers=headers, json=payload, timeout=10)
            
            if res.status_code != 200:
                log.error(f"⚠️ Errore API TikTok ({res.status_code}) per paese {country}")
                continue

            data = res.json().get("data", {})
            items = data.get("videos") or data.get("posts") or data.get("items") or []
            if not items:
                continue

            for item in items:
                scanned_total += 1
                video_id = item.get("id") or item.get("id_str")
                author = item.get("author", {}) if isinstance(item.get("author"), dict) else {}
                author_handle = item.get("username") or author.get("handle") or "creator"
                author_name = item.get("user_name") or author.get("name") or author_handle
                followers = int(item.get("follower_count") or author.get("followers") or 0)
                title = item.get("video_description") or item.get("title") or ""
                views = float(item.get("view_count") if item.get("view_count") is not None else item.get("play_count", 0))
                category = item.get("category", "Entertainment")
                
                created_ts = item.get("create_time") or item.get("created_at")
                if isinstance(created_ts, (int, float)):
                    published_at = datetime.fromtimestamp(created_ts, tz=timezone.utc).isoformat()
                elif isinstance(created_ts, str):
                    published_at = created_ts
                else:
                    published_at = datetime.now(timezone.utc).isoformat()

                if not video_id:
                    continue

                if author_handle not in tiktok_user_baseline_cache:
                    baseline = get_tiktok_user_baseline(author_handle)
                    tiktok_user_baseline_cache[author_handle] = baseline
                else:
                    baseline = tiktok_user_baseline_cache[author_handle]

                if not baseline or baseline < MIN_BASELINE_VIEWS:
                    skipped_baseline += 1
                    continue

                vpi_ratio = calculate_vpi_ratio(views, baseline)
                if vpi_ratio <= MIN_VPI_FOR_INGESTION:
                    skipped_vpi += 1
                    continue

                vpi_level, level_name, vpi_color = get_vpi_metadata(vpi_ratio)
                claim_token = f"iosa_{secrets.token_urlsafe(12)}"
                now_utc = datetime.now(timezone.utc).isoformat()

                existing = supabase.table("posts").select("id").eq("external_post_id", str(video_id)).execute()
                if existing.data:
                    already_exists += 1
                    continue

                formatted_handle = author_handle if author_handle.startswith("@") else f"@{author_handle}"

                supabase.table("posts").insert({
                    "platform": "TIKTOK",
                    "external_post_id": str(video_id),
                    "author_handle": formatted_handle,
                    "author_name": author_name,
                    "subscribers": followers,
                    "post_url": f"https://www.tiktok.com/{formatted_handle}/video/{video_id}",
                    "content_text": title,
                    "category": category,
                    "country": country,
                    "engagement_score": views,
                    "baseline_score": baseline,
                    "vpi_ratio": round_vpi(vpi_ratio),
                    "vpi_level": vpi_level,
                    "vpi_level_name": level_name,
                    "vpi_color": vpi_color,
                    "claim_token": claim_token,
                    "status": "ACTIVE",
                    "comment_sent": False,
                    "created_at": published_at,
                    "detected_at": now_utc
                }).execute()
                total_ingested += 1

        except Exception as e:
            log.error(f"⚠️ Eccezione scansione TikTok per paese {country}: {e}")
            continue

    log.info("📊 [LOG TIKTOK INGESTION SUMMARY]")
    log.info(f"   ├─ Video analizzati in totale: {scanned_total}")
    log.info(f"   ├─ Scartati per baseline assente o < {MIN_BASELINE_VIEWS}: {skipped_baseline}")
    log.info(f"   ├─ Scartati per VPI <= 1.0: {skipped_vpi}")
    log.info(f"   ├─ Già presenti nel DB: {already_exists}")
    log.info(f"   └─ NUOVI INSERITI NEL DB: {total_ingested}\n")

def mark_expired_campaign_data():
    """
    Chiude la finestra di 15 giorni.

    Il conteggio parte da detected_at, non dalla data di pubblicazione: un
    creator rilevato oggi ha 15 giorni pieni per il claim, non i giorni
    residui dalla pubblicazione del video.
    """
    log.info("Verifica record fuori finestra (> 15 giorni dal rilevamento)...")
    cutoff_date = (datetime.now(timezone.utc) - timedelta(days=CAMPAIGN_DAYS)).isoformat()
    try:
        res = (
            supabase.table("posts")
            .update({"status": "EXPIRED"})
            .lt("detected_at", cutoff_date)
            .eq("status", "ACTIVE")
            .execute()
        )
        expired_count = len(res.data) if res.data else 0
        log.info(f"{expired_count} record marcati come EXPIRED.")
    except Exception as e:
        log.error(f"Errore durante la chiusura dei vecchi record: {e}")


# ==============================================================================
# OUTREACH VIA YOUTUBE COMMENTS - DISABLED / COMMENTED OUT TO PREVENT BAN
# ==============================================================================

def dispatch_cautious_outreach():
    """OUTREACH DISABLED: YouTube comments deactivated to prevent platform spam flags."""
    log.warning("🛑 Outreach via commenti YouTube disattivato permanentemente.")
    return

def esegui_un_ciclo(con_scadenze: bool = True) -> dict:
    """Un giro completo di ingestione. E\' l\'unita\' di lavoro del motore.

    Esiste separata dallo scheduler perche\' il motore deve poter girare in tre
    modi diversi: dentro il servizio web, come processo a se\', o chiamata da un
    cron esterno. Prima esisteva solo il primo, e il primo muore quando il
    servizio web va in sospensione.

    Ogni pezzo e\' isolato: se YouTube fallisce, TikTok e le scadenze vengono
    comunque eseguiti, e l\'esito di ciascuno finisce nel riepilogo.
    """
    esiti = {}
    passi = [("youtube", fetch_and_ingest_real_youtube_content),
             ("tiktok", fetch_and_ingest_tiktok_content)]
    if con_scadenze:
        passi.append(("scadenze", mark_expired_campaign_data))

    for nome, funzione in passi:
        try:
            funzione()
            esiti[nome] = "ok"
        except Exception as e:
            # Un passo che salta non deve impedire gli altri: se la quota
            # YouTube e\' finita, le scadenze vanno comunque marcate.
            log.error("passo '%s' non riuscito: %s", nome, e)
            esiti[nome] = f"errore: {e}"
    return esiti


def start_engine():
    """Avvia lo scheduler dentro il processo chiamante.

    IOSA_ENGINE_MODE decide chi fa girare il motore:
      inline (default) - lo scheduler parte qui dentro, com\'e\' sempre stato
      off              - non parte niente: lo fa un worker o un cron esterno

    Il default resta 'inline' apposta: cambiare modalita\' e\' una scelta di
    dispiegamento, non deve succedere da sola al primo deploy.
    """
    modalita = (os.getenv("IOSA_ENGINE_MODE") or "inline").strip().lower()
    if modalita == "off":
        log.info("IOSA_ENGINE_MODE=off: lo scheduler non parte in questo processo.")
        return None

    configura()
    log.info("Avvio IOSA Background Ingestion Engine (ciclo: %d min)...",
             INGEST_INTERVAL_MINUTES)
    scheduler = BackgroundScheduler()

    scheduler.add_job(fetch_and_ingest_real_youtube_content, 'interval', minutes=INGEST_INTERVAL_MINUTES)
    scheduler.add_job(fetch_and_ingest_tiktok_content, 'interval', minutes=INGEST_INTERVAL_MINUTES)
    scheduler.add_job(mark_expired_campaign_data, 'interval', hours=12)

    scheduler.start()
    esegui_un_ciclo()
    return scheduler


