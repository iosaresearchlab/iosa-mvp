import os
import time
import requests
import statistics
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)

SUPABASE_URL = os.getenv("NEXT_PUBLIC_SUPABASE_URL") or os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY") or os.getenv("SUPABASE_KEY")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("❌ Missing Supabase credentials.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def calculate_vpi_ratio(views: float, baseline: float) -> float:
    if not baseline or baseline <= 0:
        return 1.0
    return round(views / baseline, 1)

def get_vpi_metadata(vpi_ratio: float):
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

        view_counts = [float(v.get("statistics", {}).get("viewCount", 0)) for v in stat_items if v.get("statistics", {}).get("viewCount") is not None]
        if not view_counts:
            return None

        median_val = float(statistics.median(view_counts))
        return median_val if median_val > 0 else None
    except Exception:
        return None

def get_channel_id_from_video(video_id: str) -> str | None:
    """Recupera il channelId di un video se non presente nel DB."""
    try:
        url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet&id={video_id}&key={YOUTUBE_API_KEY}"
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            items = res.json().get("items", [])
            if items:
                return items[0]["snippet"]["channelId"]
    except Exception:
        pass
    return None

def run_recalculation():
    print("🔄 Avvio ricalcolo baseline per i record attivi nel DB...")
    
    # 1. Recupera tutti i post con status ACTIVE
    res = supabase.table("posts").select("*").eq("status", "ACTIVE").execute()
    posts = res.data or []
    
    print(f"📦 Trovati {len(posts)} record da elaborare.")
    
    channel_baseline_cache = {}
    updated_count = 0
    expired_count = 0

    for idx, post in enumerate(posts, start=1):
        post_id = post["id"]
        video_id = post["external_post_id"]
        views = post.get("engagement_score", 0)

        # Recupera il channel_id tramite API (o cache)
        channel_id = get_channel_id_from_video(video_id)
        if not channel_id:
            print(f"[{idx}/{len(posts)}] ⚠️ Impossibile recuperare channel_id per video {video_id}. Saltato.")
            continue

        # Calcola o recupera la baseline mediana dalla cache
        if channel_id not in channel_baseline_cache:
            new_baseline = get_channel_recent_videos_baseline(channel_id)
            channel_baseline_cache[channel_id] = new_baseline
            time.sleep(0.2) # Evita il rate limiting
        else:
            new_baseline = channel_baseline_cache[channel_id]

        if not new_baseline:
            print(f"[{idx}/{len(posts)}] ⚠️ Baseline non calcolabile per canale {channel_id}.")
            continue

        # Ricalcola metrica VPI
        new_vpi_ratio = calculate_vpi_ratio(views, new_baseline)

        # Se il nuovo VPI scende sotto o uguale a 1.0 (non è più un outlier), marca il record come EXPIRED
        if new_vpi_ratio <= 1.0:
            supabase.table("posts").update({"status": "EXPIRED"}).eq("id", post_id).execute()
            expired_count += 1
            print(f"[{idx}/{len(posts)}] 🟡 Post {video_id} declassato (VPI {new_vpi_ratio}x) -> Marcato come EXPIRED.")
            continue

        vpi_level, level_name, vpi_color = get_vpi_metadata(new_vpi_ratio)

        # Aggiorna il record nel database
        supabase.table("posts").update({
            "baseline_score": new_baseline,
            "vpi_ratio": new_vpi_ratio,
            "vpi_level": vpi_level,
            "vpi_level_name": level_name,
            "vpi_color": vpi_color
        }).eq("id", post_id).execute()

        updated_count += 1
        print(f"[{idx}/{len(posts)}] ✅ Post {video_id} aggiornato! Nuova Baseline: {new_baseline:.2f} | Nuovo VPI: {new_vpi_ratio}x ({level_name})")

    print("\n🎉 FINE RICALCOLO:")
    print(f"   ├─ Record aggiornati correttamente: {updated_count}")
    print(f"   └─ Record ricalcolati e scartati (VPI <= 1.0): {expired_count}")

if __name__ == "__main__":
    run_recalculation()