import os
import time
import secrets
import random
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client
from apscheduler.schedulers.blocking import BlockingScheduler

# Load environment variables
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)

SUPABASE_URL = os.getenv("NEXT_PUBLIC_SUPABASE_URL") or os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY") or os.getenv("SUPABASE_KEY")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

# Maximum subscriber threshold (excludes overly large channels)
MAX_SUBSCRIBERS = 500_000 
CAMPAIGN_DAYS = 15

# Rotazione globale per democraticità di nicchie e paesi
TARGET_COUNTRIES = ['US', 'IT', 'GB', 'DE', 'FR', 'ES', 'BR', 'JP', 'IN', 'CA', 'AU']
CATEGORY_MAP = {
    '10': 'Music',
    '20': 'Gaming',
    '28': 'Tech',
    '17': 'Sports',
    '24': 'Entertainment',
    '22': 'People'
}

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("❌ Missing Supabase credentials in environment variables.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def calculate_vpi_ratio(views: float, baseline: float) -> float:
    """Calculates VPI ratio normalized against channel baseline (rounded to 1 decimal place)[cite: 4]."""
    if not baseline or baseline <= 0:
        return 1.0
    return round(views / baseline, 1)

def get_vpi_metadata(vpi_ratio: float):
    """Returns (vpi_level, vpi_level_name, vpi_color) based on the 10-Level VPI Scale[cite: 4]."""
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

def fetch_channels_metadata(channel_ids: list) -> dict:
    """Retrieves real subscriber count and calculates average view baseline per channel[cite: 4]."""
    if not channel_ids:
        return {}
    
    ids_str = ",".join(list(set(channel_ids)))
    url = f"https://www.googleapis.com/youtube/v3/channels?part=statistics&id={ids_str}&key={YOUTUBE_API_KEY}"
    res = requests.get(url, timeout=10)
    
    if res.status_code != 200:
        return {}

    channels_data = {}
    for item in res.json().get("items", []):
        ch_id = item["id"]
        stats = item.get("statistics", {})
        
        subs = int(stats.get("subscriberCount", 0)) if not stats.get("hiddenSubscriberCount") else 999_999_999
        total_views = int(stats.get("viewCount", 0))
        video_count = max(int(stats.get("videoCount", 1)), 1)
        
        # Real calculated baseline: average views per video on the channel[cite: 4]
        avg_views = max(int(total_views / video_count), 5_000)

        channels_data[ch_id] = {
            "subscribers": subs,
            "baseline": float(avg_views)
        }

    return channels_data

def fetch_and_ingest_real_youtube_content():
    """
    Scans YouTube trending videos rotating countries and categories to cover democratic global niches.
    Filters out creators exceeding subscriber limit or VPI <= 1.0.
    """
    if not YOUTUBE_API_KEY:
        print("⚠️ YOUTUBE_API_KEY missing in .env. Skipping live ingestion.")
        return

    # Seleziona 3 Paesi e 2 Categorie ad ogni scan per variazione continua[cite: 4]
    selected_countries = random.sample(TARGET_COUNTRIES, k=3)
    selected_category_ids = random.sample(list(CATEGORY_MAP.keys()), k=2)

    print(f"📡 [{datetime.now().strftime('%H:%M:%S')}] Deep scanning YouTube (Countries: {selected_countries}, Categories: {[CATEGORY_MAP[c] for c in selected_category_ids]})...")
    
    total_ingested = 0

    for country in selected_countries:
        for cat_id in selected_category_ids:
            cat_name = CATEGORY_MAP[cat_id]
            url = (
                f"https://www.googleapis.com/youtube/v3/videos?"
                f"part=snippet,statistics&chart=mostPopular&maxResults=50"
                f"&regionCode={country}&videoCategoryId={cat_id}&key={YOUTUBE_API_KEY}"
            )

            res = requests.get(url, timeout=10)
            if res.status_code != 200:
                continue

            data = res.json()
            items = data.get("items", [])
            if not items:
                continue

            channel_ids = [item["snippet"]["channelId"] for item in items]
            channels_meta = fetch_channels_metadata(channel_ids)

            for vid_data in items:
                vid_id = vid_data["id"]
                snippet = vid_data["snippet"]
                ch_id = snippet["channelId"]
                title = snippet["title"]
                channel_title = snippet["channelTitle"]
                published_at = snippet["publishedAt"]
                views = float(vid_data["statistics"].get("viewCount", 0))

                ch_info = channels_meta.get(ch_id, {"subscribers": 999_999_999, "baseline": 50_000.0})
                subscribers = ch_info["subscribers"]
                baseline = ch_info["baseline"]

                # Filtro limite iscritti[cite: 4]
                if subscribers > MAX_SUBSCRIBERS:
                    continue

                # Calcolo VPI[cite: 4]
                vpi_ratio = calculate_vpi_ratio(views, baseline)

                # SOGLIA DI INGRESSO: VPI deve essere rigorosamente > 1.0[cite: 4]
                if vpi_ratio <= 1.0:
                    continue

                vpi_level, level_name, vpi_color = get_vpi_metadata(vpi_ratio)
                claim_token = f"iosa_{secrets.token_urlsafe(12)}"

                # Deduplica tramite external_post_id[cite: 4]
                existing = supabase.table("posts").select("id").eq("external_post_id", vid_id).execute()
                if not existing.data:
                    supabase.table("posts").insert({
                        "platform": "YOUTUBE",
                        "external_post_id": vid_id,
                        "author_handle": f"@{channel_title.replace(' ', '')}",
                        "author_name": channel_title,
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
                        "created_at": published_at
                    }).execute()
                    total_ingested += 1
                    print(f"   📥 Ingested [{country}/{cat_name}]: [{channel_title}] ({subscribers:,} subs) | Views: {int(views):,} vs Avg: {int(baseline):,} | VPI: +{vpi_ratio}x")

    print(f"✅ Scan completato: {total_ingested} nuovi outlier accreditati scritti su Supabase.\n")

def purge_expired_campaign_data():
    """
    Routine di pulizia automatica che elimina tutti i post più vecchi di 15 giorni[cite: 4].
    """
    print("🧹 Esecuzione pulizia dati campagna (rimozione record > 15 giorni)...")
    cutoff_date = (datetime.now(timezone.utc) - timedelta(days=CAMPAIGN_DAYS)).isoformat()
    try:
        supabase.table("posts").delete().lt("created_at", cutoff_date).execute()
        print("🗑️ Pulizia completata con successo.")
    except Exception as e:
        print(f"❌ Errore durante la pulizia del database: {e}")

if __name__ == "__main__":
    # Esecuzione immediata all'avvio[cite: 4]
    fetch_and_ingest_real_youtube_content()

    # Inizializzazione scheduler[cite: 4]
    scheduler = BlockingScheduler()
    # Ingestion ogni 15 minuti[cite: 4]
    scheduler.add_job(fetch_and_ingest_real_youtube_content, 'interval', minutes=15)
    # Controllo e pulizia automatica ogni 24 ore[cite: 4]
    scheduler.add_job(purge_expired_campaign_data, 'interval', hours=24)

    print("⏱️ IOSA Ingestion Engine attivo. Ingestion ogni 15 min, Pulizia ogni 24h. Premere Ctrl+C per fermare.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("🛑 Ingestion Engine fermato.")