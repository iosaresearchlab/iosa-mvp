import os
import time
import requests
import statistics
import re
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client

# Caricamento variabili d'ambiente
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)

SUPABASE_URL = os.getenv("NEXT_PUBLIC_SUPABASE_URL") or os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY") or os.getenv("SUPABASE_KEY")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("❌ Credenziali Supabase mancanti nelle variabili d'ambiente.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def is_real_youtube_short(video_id: str) -> bool:
    """
    Verifica con certezza assoluta se un video è uno Short sfruttando 
    il router HTTP interno di YouTube (Status 200 vs Redirect 302).
    """
    url = f"https://www.youtube.com/shorts/{video_id}"
    try:
        response = requests.head(url, allow_redirects=False, timeout=3)
        return response.status_code == 200
    except requests.RequestException:
        return False

def parse_iso_duration(duration_str: str) -> int:
    """Converte le stringhe di durata ISO 8601 in secondi totali."""
    if not duration_str:
        return 0
    match = re.match(r'P(?:(\d+)D)?T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_str)
    if not match:
        return 0
    days = int(match.group(1) or 0)
    hours = int(match.group(2) or 0)
    minutes = int(match.group(3) or 0)
    seconds = int(match.group(4) or 0)
    return days * 86400 + hours * 3600 + minutes * 60 + seconds

def calculate_vpi_ratio(views: float, baseline: float) -> float:
    """Calcola il VPI ratio rapportato alla baseline del canale."""
    if not baseline or baseline <= 0:
        return 1.0
    return round(views / baseline, 1)

def get_vpi_metadata(vpi_ratio: float):
    """Restituisce il livello VPI, la denominazione e il colore della scala."""
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
    """Calcola la baseline basandosi ESCLUSIVAMENTE sulla mediana dei soli Short del canale."""
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
            return None

        video_ids = [item["contentDetails"]["videoId"] for item in pl_items if "contentDetails" in item and "videoId" in item["contentDetails"]]
        if not video_ids:
            return None

        vid_ids_str = ",".join(video_ids)
        stats_url = f"https://www.googleapis.com/youtube/v3/videos?part=contentDetails,statistics&id={vid_ids_str}&key={YOUTUBE_API_KEY}"
        stats_res = requests.get(stats_url, timeout=10)
        if stats_res.status_code != 200:
            return None
        stat_items = stats_res.json().get("items", [])
        if not stat_items:
            return None

        short_view_counts = []
        for v_item in stat_items:
            c_details = v_item.get("contentDetails", {})
            dur_str = c_details.get("duration", "")
            dur_sec = parse_iso_duration(dur_str)

            # Filtro restrittivo: solo Short reali (<= 180s e verfifica HTTP)
            if 0 < dur_sec <= 180 and is_real_youtube_short(v_item["id"]):
                v_stats = v_item.get("statistics", {})
                views_str = v_stats.get("viewCount")
                if views_str is not None:
                    short_view_counts.append(float(views_str))

        if not short_view_counts:
            return None

        median_baseline = float(statistics.median(short_view_counts))
        return median_baseline if median_baseline > 0 else None
    except Exception:
        return None

def run_backfill():
    """Riscansiona i video nel DB, ricalcola il VPI ed emette lo stato INACTIVE per i non-Short."""
    print("🔄 Recupero dei post YouTube presenti nel database...")
    res = supabase.table("posts").select("*").eq("platform", "YOUTUBE").execute()
    posts = res.data or []
    print(f"📊 Trovati {len(posts)} record YouTube da analizzare.\n")

    channel_baseline_cache = {}
    updated_count = 0
    inactivated_count = 0

    batch_size = 50
    for i in range(0, len(posts), batch_size):
        chunk = posts[i:i + batch_size]
        vid_ids = [p["external_post_id"] for p in chunk if p.get("external_post_id")]
        if not vid_ids:
            continue

        vid_ids_str = ",".join(vid_ids)
        yt_url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet,contentDetails,statistics&id={vid_ids_str}&key={YOUTUBE_API_KEY}"
        
        yt_data_map = {}
        try:
            yt_res = requests.get(yt_url, timeout=10)
            if yt_res.status_code == 200:
                for item in yt_res.json().get("items", []):
                    yt_data_map[item["id"]] = item
        except Exception as e:
            print(f"⚠️ Errore di connessione API YouTube per batch: {e}")

        for post in chunk:
            post_id = post["id"]
            vid_id = post.get("external_post_id")
            
            if not vid_id:
                continue

            yt_item = yt_data_map.get(vid_id)
            if not yt_item:
                # Video eliminato o privato su YouTube -> INACTIVE
                supabase.table("posts").update({"status": "INACTIVE"}).eq("id", post_id).execute()
                inactivated_count += 1
                print(f"🔴 [INACTIVE] Post ID {post_id} - Video {vid_id} non più reperibile su YouTube.")
                continue

            dur_str = yt_item.get("contentDetails", {}).get("duration", "")
            dur_sec = parse_iso_duration(dur_str)
            ch_id = yt_item.get("snippet", {}).get("channelId")
            views = float(yt_item.get("statistics", {}).get("viewCount", post.get("engagement_score") or 0))

            # Verifica se è un reale YouTube Short
            is_short = (0 < dur_sec <= 180) and is_real_youtube_short(vid_id)

            if not is_short:
                # Non è uno Short -> imposta INACTIVE
                supabase.table("posts").update({"status": "INACTIVE"}).eq("id", post_id).execute()
                inactivated_count += 1
                print(f"🟡 [INACTIVE] Post ID {post_id} - Video {vid_id} NON è uno Short reale (Long-form o orizzontale).")
                continue

            # Calcolo/Recupero Baseline solo da Short
            if ch_id not in channel_baseline_cache:
                baseline = get_channel_recent_videos_baseline(ch_id)
                channel_baseline_cache[ch_id] = baseline
            else:
                baseline = channel_baseline_cache[ch_id]

            if not baseline or baseline <= 0:
                supabase.table("posts").update({"status": "INACTIVE"}).eq("id", post_id).execute()
                inactivated_count += 1
                print(f"⚠️ [INACTIVE] Post ID {post_id} - Impossibile calcolare baseline Shorts per il canale {ch_id}.")
                continue

            vpi_ratio = calculate_vpi_ratio(views, baseline)
            vpi_level, level_name, vpi_color = get_vpi_metadata(vpi_ratio)

            supabase.table("posts").update({
                "engagement_score": views,
                "baseline_score": baseline,
                "vpi_ratio": vpi_ratio,
                "vpi_level": vpi_level,
                "vpi_level_name": level_name,
                "vpi_color": vpi_color,
                "status": "ACTIVE"
            }).eq("id", post_id).execute()

            updated_count += 1
            print(f"✅ [UPDATED] Post ID {post_id} | VPI Ratio: {vpi_ratio} | Baseline Shorts: {baseline:.0f} | Views: {views:.0f}")

    print("\n📊 [RIEPILOGO AGGIORNAMENTO DB BACKDROP VPI]")
    print(f"   ├─ Record totali esaminati: {len(posts)}")
    print(f"   ├─ Record aggiornati correttamente (Shorts validi): {updated_count}")
    print(f"   └─ Record marcati come INACTIVE (Non-Short / non validi): {inactivated_count}\n")

if __name__ == "__main__":
    run_backfill()