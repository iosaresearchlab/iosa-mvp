"""The TikTok branch of the v1 engine, archived at T-11 (25/09/2026).

Moved verbatim from backend/vpi_engine.py. It produced one record in the
project's entire history, and the Research API exposes no Most Popular chart,
so entry into Most Popular is not observable there (docs/02 section 4.2).
Not imported by anything; kept as a record. It relied on the module globals
of the v1 engine (archive/backend/vpi_engine_v1.py): supabase, log,
TARGET_COUNTRIES, the vpi_core helpers, TIKTOK_CLIENT_KEY / _SECRET.
"""

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



