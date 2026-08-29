import os
import time
import secrets
import random
import requests
import statistics
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client
from apscheduler.schedulers.background import BackgroundScheduler

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

BASE_DOMAIN = os.getenv("NEXT_PUBLIC_SITE_URL", "https://iosaresearch.com")
OPTOUT_EMAIL = "optout@iosaresearch.com"

# Maximum subscriber threshold (increased to 1.5M to include small/medium channels)
MAX_SUBSCRIBERS = 1_500_000 
MIN_SUBSCRIBERS = 1_000
CAMPAIGN_DAYS = 15

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

VPI_TEMPLATES = {
    1: "Hey @{creator}, our algorithms at IOSA Research Lab recorded your latest upload hitting Level 1 - Standard baseline. Make this moment memorable and view your certified VPI report here: {reward_link} (Autonomous metric tracking, not spam. To opt out, email {optout_email}.) 📊",
    2: "Congrats @{creator}! IOSA Research Lab flagged this video reaching Level 2 - Moderate growth. Make this moment memorable by claiming your accredited performance report and award options at {reward_link} (Independent research index. Email {optout_email} to opt out.) 📈",
    3: "Nice work @{creator}! Our automated trackers logged a Level 3 - Rising performance on this upload. Make this moment memorable and check your certified VPI report and award options here: {reward_link} (Data tracking, zero spam. Contact {optout_email} to opt out.) 🚀",
    4: "Hey @{creator}, IOSA Research Lab detected a major spike—your video achieved Level 4 - Trending status! Make this moment memorable and claim your official physical trophy at {reward_link} (Automated research audit. Opt-out anytime via {optout_email}.) 🔥",
    5: "Incredible momentum @{creator}! Our systems flagged this upload hitting Level 5 - Breakout status in performance. Make this moment memorable and claim your physical award at {reward_link} (Independent analytics bot. Email {optout_email} to stop alerts.) ✨",
    6: "Boom! @{creator}, IOSA Research Lab registered an official viral event—Level 6 - Viral unlocked! Make this moment memorable and access your accredited trophy at {reward_link} (Pure data, zero spam. Opt-out via {optout_email}.) 💥",
    7: "Massive performance @{creator}! IOSA Research Lab audited your video and confirmed a Level 7 - Super Viral rank. Make this moment memorable and claim your certified milestone award here: {reward_link} (Autonomous research lab. To opt-out, contact {optout_email}.) ⚡",
    8: "Outstanding result @{creator}! Our indexing nodes marked this upload as a Level 8 - Outlier performance. Make this moment memorable and claim your official physical trophy at {reward_link} (Not spam, just data. Opt-out: {optout_email}.) 🏆",
    9: "Legendary numbers @{creator}! IOSA Research Lab recorded a Level 9 - Mega Outlier event on this video. Make this moment memorable and claim your accredited award at {reward_link} (Autonomous tracking node. Opt-out via {optout_email}.) 👑",
    10: "Historical peak @{creator}! IOSA Research Lab logged a Level 10 - Hyper Outlier anomaly on your channel. Make this moment memorable and access your top-tier accredited trophy at {reward_link} (Independent research lab. To stop receiving alerts, email {optout_email}.) 🌟"
}

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("❌ Missing Supabase credentials in environment variables.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def calculate_vpi_ratio(views: float, baseline: float) -> float:
    """Calculates VPI ratio normalized against channel baseline."""
    if not baseline or baseline <= 0:
        return 1.0
    return round(views / baseline, 1)

def get_vpi_metadata(vpi_ratio: float):
    """Returns (vpi_level, vpi_level_name, vpi_color) based on the 10-Level VPI Scale."""
    if vpi_ratio >= 50.0:
        return 10, "Lvl 10 - Hyper Outlier", "#FF0055"
    elif vpi_ratio >= 25.0:
        return 9, "Lvl 9 - Mega Outlier", "#FF2A00"
    elif vpi_ratio >= 15.0:
        return 8, "Lvl 8 - Outlier", "#FF5500"
    elif vpi_ratio >= 10.0:
        return 7, "Lvl 7 - Super Viral", "#FF8800"
    elif vpi_ratio >= 7.5:
        return 6, "Lvl 6 - Viral", "#FFAA00"
    elif vpi_ratio >= 5.0:
        return 5, "Lvl 5 - Breakout", "#FFCC00"
    elif vpi_ratio >= 3.0:
        return 4, "Lvl 4 - Trending", "#00CC88"
    elif vpi_ratio >= 2.0:
        return 3, "Lvl 3 - Rising", "#0099FF"
    elif vpi_ratio >= 1.5:
        return 2, "Lvl 2 - Moderate", "#7755FF"
    else:
        return 1, "Lvl 1 - Standard", "#888888"

def get_channel_recent_videos_baseline(channel_id: str) -> float | None:
    """Calculates baseline as the MEDIAN view count of the last up to 20 published videos of the channel."""
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

        playlist_url = f"https://www.googleapis.com/youtube/v3/playlistItems?part=contentDetails&playlistId={uploads_playlist_id}&maxResults=20&key={YOUTUBE_API_KEY}"
        pl_res = requests.get(playlist_url, timeout=10)
        if pl_res.status_code != 200:
            return None
        pl_items = pl_res.json().get("items", [])
        if not pl_items:
            return None

        video_ids = [item["contentDetails"]["videoId"] for item in pl_items if "contentDetails" in item and "videoId" in item["contentDetails"]]
        if not video_ids:
            return None

        vid_ids_str = ",".join(video_ids)
        stats_url = f"https://www.googleapis.com/youtube/v3/videos?part=statistics&id={vid_ids_str}&key={YOUTUBE_API_KEY}"
        stats_res = requests.get(stats_url, timeout=10)
        if stats_res.status_code != 200:
            return None
        stat_items = stats_res.json().get("items", [])
        if not stat_items:
            return None

        view_counts = []
        for v_item in stat_items:
            v_stats = v_item.get("statistics", {})
            views_str = v_stats.get("viewCount")
            if views_str is not None:
                view_counts.append(float(views_str))

        if not view_counts:
            return None

        # Calcolo della Mediana Mobile per isolare e rimuovere gli outlier
        median_baseline = float(statistics.median(view_counts))
        return median_baseline if median_baseline > 0 else None
    except Exception:
        return None

def fetch_channels_metadata(channel_ids: list) -> dict:
    """Retrieves real subscriber count and calculates average view baseline per channel."""
    if not channel_ids:
        return {}
    
    ids_str = ",".join(list(set(channel_ids)))
    url = f"https://www.googleapis.com/youtube/v3/channels?part=statistics&id={ids_str}&key={YOUTUBE_API_KEY}"
    
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 404:
            return {}
        if res.status_code != 200:
            return {}
    except Exception:
        return {}

    channels_data = {}
    for item in res.json().get("items", []):
        ch_id = item["id"]
        stats = item.get("statistics", {})
        
        subs = int(stats.get("subscriberCount", 0)) if not stats.get("hiddenSubscriberCount") else 999_999_999
        total_views = int(stats.get("viewCount", 0))
        video_count = int(stats.get("videoCount", 0))
        
        baseline = None
        if total_views > 0 and video_count > 0:
            baseline = float(total_views / video_count)

        channels_data[ch_id] = {
            "subscribers": subs,
            "baseline": baseline
        }

    return channels_data

def fetch_and_ingest_real_youtube_content():
    """Scans YouTube trending videos and ingests outliers into Supabase."""
    if not YOUTUBE_API_KEY:
        print("⚠️ YOUTUBE_API_KEY missing in .env. Skipping live ingestion.")
        return

    # Opzione 3: US + 2 paesi casuali (3 paesi totali)
    other_countries = [c for c in TARGET_COUNTRIES if c != 'US']
    selected_countries = ['US'] + random.sample(other_countries, k=2)

    # Opzione 3: 1 categoria casuale per run (3 coppie Paese-Categoria totali per run)
    selected_category_ids = random.sample(list(CATEGORY_MAP.keys()), k=1)

    print(f"📡 [{datetime.now().strftime('%H:%M:%S')}] Deep scanning YouTube (Countries: {selected_countries}, Categories: {[CATEGORY_MAP[c] for c in selected_category_ids]})...")
    
    scanned_total = 0
    skipped_subs = 0
    skipped_vpi = 0
    skipped_baseline = 0
    already_exists = 0
    total_ingested = 0

    # Cache di sessione in memoria per le mediane calcolate durante questo ciclo
    channel_recent_baseline_cache = {}

    for country in selected_countries:
        for cat_id in selected_category_ids:
            cat_name = CATEGORY_MAP[cat_id]
            items = []

            # Paginazione: Pagina 1 (da 1 a 50)
            url_p1 = (
                f"https://www.googleapis.com/youtube/v3/videos?"
                f"part=snippet,statistics&chart=mostPopular&maxResults=50"
                f"&regionCode={country}&videoCategoryId={cat_id}&key={YOUTUBE_API_KEY}"
            )
            
            try:
                res1 = requests.get(url_p1, timeout=10)
                if res1.status_code == 404:
                    print(f"⚠️ Errore API YouTube (404) per {country}/{cat_name}: Risorsa non trovata o non disponibile per la regione.")
                    continue
                elif res1.status_code != 200:
                    print(f"⚠️ Errore API YouTube ({res1.status_code}) per {country}/{cat_name}: {res1.text}")
                    continue

                data1 = res1.json()
                items.extend(data1.get("items", []))
                next_page_token = data1.get("nextPageToken")

                # Paginazione: Pagina 2 (da 51 a 100) per intercettare gli exploit di canali piccoli/medi
                if next_page_token:
                    url_p2 = f"{url_p1}&pageToken={next_page_token}"
                    res2 = requests.get(url_p2, timeout=10)
                    if res2.status_code == 200:
                        data2 = res2.json()
                        items.extend(data2.get("items", []))
            except Exception as e:
                print(f"⚠️ Eccezione di rete o timeout per {country}/{cat_name}: {e}")
                continue

            if not items:
                continue

            channel_ids = [item["snippet"]["channelId"] for item in items]
            channels_meta = fetch_channels_metadata(channel_ids)

            for vid_data in items:
                scanned_total += 1
                vid_id = vid_data["id"]
                snippet = vid_data["snippet"]
                ch_id = snippet["channelId"]
                title = snippet["title"]
                channel_title = snippet["channelTitle"]
                published_at = snippet["publishedAt"]
                views = float(vid_data["statistics"].get("viewCount", 0))

                ch_info = channels_meta.get(ch_id)
                subscribers = ch_info.get("subscribers", 999_999_999) if ch_info else 999_999_999
                global_baseline = ch_info.get("baseline") if ch_info else None
                
                # --- FILTRO SHORT-CIRCUIT (Costo Quota 0 API) ---
                # Scarta i video non promettenti sulla media globale PRIMA di calcolare la mediana
                if global_baseline and global_baseline > 0:
                    preliminary_ratio = calculate_vpi_ratio(views, global_baseline)
                    if preliminary_ratio < 1.0:
                        skipped_vpi += 1
                        continue

                # 1. Calcola la Mediana Mobile degli ultimi 20 video (con verifica in cache locale)
                if ch_id not in channel_recent_baseline_cache:
                    baseline = get_channel_recent_videos_baseline(ch_id)
                    channel_recent_baseline_cache[ch_id] = baseline
                else:
                    baseline = channel_recent_baseline_cache[ch_id]

                # 2. Se e solo se la mediana degli ultimi 20 video fallisce, usa la media globale del canale come fallback
                if not baseline or baseline <= 0:
                    baseline = global_baseline

                # 3. Se entrambe le metriche non producono un valore valido, scarta il video
                if not baseline or baseline <= 0:
                    skipped_baseline += 1
                    continue

                # --- TEMP DISABLED FOR FULL DATA ACCURACY ---
                # if subscribers > MAX_SUBSCRIBERS:
                #     skipped_subs += 1
                #     continue
                # --------------------------------------------

                vpi_ratio = calculate_vpi_ratio(views, baseline)
                if vpi_ratio <= 1.0:
                    skipped_vpi += 1
                    continue

                vpi_level, level_name, vpi_color = get_vpi_metadata(vpi_ratio)
                claim_token = f"iosa_{secrets.token_urlsafe(12)}"
                now_utc = datetime.now(timezone.utc).isoformat()

                existing = supabase.table("posts").select("id").eq("external_post_id", vid_id).execute()
                if existing.data:
                    already_exists += 1
                    continue

                supabase.table("posts").insert({
                    "platform": "YOUTUBE",
                    "external_post_id": vid_id,
                    "author_handle": f"@{channel_title.replace(' ', '')}",
                    "author_name": channel_title,
                    "subscribers": subscribers,
                    "post_url": f"https://www.youtube.com/watch?v={vid_id}",
                    "content_text": title,
                    "category": cat_name,
                    "country": country,
                    "engagement_score": views,
                    "baseline_score": baseline,
                    "vpi_ratio": vpi_ratio,
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

    print("📊 [LOG INGESTION SUMMARY]")
    print(f"   ├─ Video analizzati in totale: {scanned_total}")
    print(f"   ├─ Scartati per Iscritti > {MAX_SUBSCRIBERS:,}: {skipped_subs} [CHECK DISABLED]")
    print(f"   ├─ Scartati per Baseline assente/non calcolabile: {skipped_baseline}")
    print(f"   ├─ Scartati per VPI <= 1.0: {skipped_vpi}")
    print(f"   ├─ Già presenti nel DB: {already_exists}")
    print(f"   └─ NUOVI INSERITI NEL DB: {total_ingested}\n")

def mark_expired_campaign_data():
    """Soft-delete: marca come EXPIRED i record più vecchi di 15 giorni invece di eliminarli."""
    print("🧹 Verifica ed eventuale scadenza record (> 15 giorni)...")
    cutoff_date = (datetime.now(timezone.utc) - timedelta(days=CAMPAIGN_DAYS)).isoformat()
    try:
        res = supabase.table("posts").update({"status": "EXPIRED"}).lt("created_at", cutoff_date).eq("status", "ACTIVE").execute()
        expired_count = len(res.data) if res.data else 0
        print(f"🟡 {expired_count} record marcati come EXPIRED.")
    except Exception as e:
        print(f"❌ Errore durante la disattivazione dei vecchi record: {e}")

# ==============================================================================
# OUTREACH VIA YOUTUBE COMMENTS - DISABLED / COMMENTED OUT TO PREVENT BAN
# ==============================================================================

# def get_valid_youtube_access_token() -> str:
#     """Rigenera autonomamente l'Access Token temporaneo a partire dal Refresh Token permanente."""
#     if not all([YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN]):
#         print("⚠️ Credenziali OAuth YouTube mancanti nel file .env o nelle variabili d'ambiente.")
#         return ""
#     
#     url = "https://oauth2.googleapis.com/token"
#     payload = {
#         "client_id": YOUTUBE_CLIENT_ID,
#         "client_secret": YOUTUBE_CLIENT_SECRET,
#         "refresh_token": YOUTUBE_REFRESH_TOKEN,
#         "grant_type": "refresh_token"
#     }
#     
#     try:
#         res = requests.post(url, data=payload, timeout=10)
#         if res.status_code == 200:
#             return res.json().get("access_token", "")
#         else:
#             print(f"❌ Errore refresh token OAuth YouTube ({res.status_code}): {res.text}")
#             return ""
#     except Exception as e:
#         print(f"❌ Eccezione durante il refresh token OAuth: {e}")
#         return ""

# def post_youtube_comment(video_id: str, comment_text: str) -> bool:
#     """Invia un commento su YouTube richiedendo dinamicamente un Access Token valido."""
#     access_token = get_valid_youtube_access_token()
#     
#     if not access_token:
#         print(f"⚠️ [MOCK MODE] Impossibile recuperare Access Token OAuth. Commento non inviato per video {video_id}:\n   {comment_text}")
#         return False
#
#     url = "https://www.googleapis.com/youtube/v3/commentThreads?part=snippet"
#     headers = {
#         "Authorization": f"Bearer {access_token}",
#         "Content-Type": "application/json"
#     }
#     body = {
#         "snippet": {
#             "videoId": video_id,
#             "topLevelComment": {
#                 "snippet": {
#                     "textOriginal": comment_text
#                 }
#             }
#         }
#     }
#     
#     try:
#         res = requests.post(url, json=body, headers=headers, timeout=10)
#         if res.status_code in [200, 201]:
#             print(f"🚀 Commento pubblicato con successo su YouTube per il video {video_id}!")
#             return True
#         else:
#             print(f"❌ Errore pubblicazione commento YouTube ({res.status_code}): {res.text}")
#             return False
#     except Exception as e:
#         print(f"❌ Eccezione durante l'invio del commento: {e}")
#         return False

def dispatch_cautious_outreach():
    """OUTREACH DISABLED: YouTube comments deactivated to prevent platform spam flags."""
    print("🛑 Outreach via commenti YouTube disattivato permanentemente.")
    return
    # Code preserved below for future email outreach migration:
    # try:
    #     res = (
    #         supabase.table("posts")
    #         .select("*")
    #         .eq("country", "US")
    #         .eq("status", "ACTIVE")
    #         .eq("comment_sent", False)
    #         .gte("subscribers", MIN_SUBSCRIBERS)
    #         .lte("subscribers", MAX_SUBSCRIBERS)
    #         .order("subscribers", desc=False)
    #         .order("vpi_ratio", desc=True)
    #         .limit(10)
    #         .execute()
    #     )
    #     candidates = res.data or []
    #     if not candidates:
    #         res_fallback = (
    #             supabase.table("posts")
    #             .select("*")
    #             .eq("status", "ACTIVE")
    #             .eq("comment_sent", False)
    #             .gte("subscribers", MIN_SUBSCRIBERS)
    #             .lte("subscribers", MAX_SUBSCRIBERS)
    #             .order("subscribers", desc=False)
    #             .order("vpi_ratio", desc=True)
    #             .limit(10)
    #             .execute()
    #         )
    #         candidates = res_fallback.data or []
    #     if not candidates:
    #         return
    #     for record in candidates:
    #         vpi_level = record.get("vpi_level", 1)
    #         template = VPI_TEMPLATES.get(vpi_level, VPI_TEMPLATES[1])
    #         reward_link = f"{BASE_DOMAIN}/claim/{record['claim_token']}"
    #         formatted_msg = template.format(
    #             creator=record["author_name"],
    #             reward_link=reward_link,
    #             optout_email=OPTOUT_EMAIL
    #         )
    #         success = post_youtube_comment(record["external_post_id"], formatted_msg)
    #         if success:
    #             supabase.table("posts").update({"comment_sent": True}).eq("id", record["id"]).execute()
    #         time.sleep(2)
    # except Exception as e:
    #     print(f"❌ Errore outreach: {e}")

def start_engine():
    """Initializes and starts background tasks (Opzione 3: Esecuzione ogni 20 minuti)."""
    print("⏱️ Avvio IOSA Background Ingestion Engine...")
    scheduler = BackgroundScheduler()
    
    scheduler.add_job(fetch_and_ingest_real_youtube_content, 'interval', minutes=20)
    scheduler.add_job(mark_expired_campaign_data, 'interval', hours=12)
    # scheduler.add_job(dispatch_cautious_outreach, 'interval', hours=1) # DISABLED OUTREACH
    
    scheduler.start()
    
    try:
        fetch_and_ingest_real_youtube_content()
        mark_expired_campaign_data()
        # dispatch_cautious_outreach() # DISABLED OUTREACH
    except Exception as e:
        print(f"❌ Errore durante l'avvio: {e}")

if __name__ == "__main__":
    start_engine()
    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        print("🛑 Engine fermato.")
