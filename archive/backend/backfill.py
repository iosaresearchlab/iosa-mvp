import os
import requests
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

def backfill_subscribers():
    print("🔄 Recupero post ACTIVE con subscribers NULL...")
    res = supabase.table("posts").select("id, external_post_id").eq("status", "ACTIVE").is_("subscribers", "null").execute()
    posts = res.data or []
    
    if not posts:
        print("✨ Nessun record da aggiornare.")
        return

    print(f"📌 Trovati {len(posts)} record da aggiornare.")
    
    for post in posts:
        vid_id = post["external_post_id"]
        # Recupera channelId del video
        url_vid = f"https://www.googleapis.com/youtube/v3/videos?part=snippet&id={vid_id}&key={YOUTUBE_API_KEY}"
        r_vid = requests.get(url_vid).json()
        
        items = r_vid.get("items", [])
        if not items:
            continue
            
        ch_id = items[0]["snippet"]["channelId"]
        
        # Recupera iscritti del canale
        url_ch = f"https://www.googleapis.com/youtube/v3/channels?part=statistics&id={ch_id}&key={YOUTUBE_API_KEY}"
        r_ch = requests.get(url_ch).json()
        
        ch_items = r_ch.get("items", [])
        if ch_items:
            stats = ch_items[0].get("statistics", {})
            subs = int(stats.get("subscriberCount", 0)) if not stats.get("hiddenSubscriberCount") else 999999999
            
            supabase.table("posts").update({"subscribers": subs}).eq("id", post["id"]).execute()
            print(f"✅ Aggiornato post {vid_id} con {subs} iscritti.")

if __name__ == "__main__":
    backfill_subscribers()