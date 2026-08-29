import sys
import asyncio
import json
from datetime import datetime, timezone, timedelta
from typing import Optional

# Force ProactorEventLoop policy on Windows to allow Playwright subprocesses
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import os
import re
import stripe
import traceback
from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, field_validator
from dotenv import load_dotenv
from supabase import create_client

from trophy_pipeline import fulfill_trophy_order, generate_and_publish_trophy
from generate_trophy import generate_trophy_png, generate_mug_preview_png
from vpi_engine import start_engine

load_dotenv()

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
SUPABASE_URL = os.getenv("NEXT_PUBLIC_SUPABASE_URL") or os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY") or os.getenv("SUPABASE_KEY")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
print(f"DEBUG: FRONTEND_URL is set to: {FRONTEND_URL}")

if not STRIPE_SECRET_KEY:
    print("⚠️ WARNING: STRIPE_SECRET_KEY not found in .env file!")

stripe.api_key = STRIPE_SECRET_KEY

supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

app = FastAPI(title="IOSA Trophy API")

@app.on_event("startup")
def startup_event():
    start_engine()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
    return {"status": "online", "system": "IOSA Lab Backend"}

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
    try:
        if not supabase:
            return {"by_country": {}, "by_category": {}, "macro_regions": {}}

        res = supabase.table("posts").select("country, category, vpi_ratio").eq("status", "ACTIVE").execute()
        data = res.data or []

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
    try:
        if not supabase:
            return {"keywords": []}

        res = supabase.table("posts").select("content_text, vpi_ratio").gte("vpi_ratio", min_vpi).eq("status", "ACTIVE").execute()
        data = res.data or []

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
async def api_generate_trophy(data: TrophyRequest):
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
                print(f"Error fetching post details for trophy preview: {db_err}")
        
        if not resolved_title:
            resolved_title = "Viral Content Title"

        image_path = await generate_trophy_png(
            record_id=resolved_record_id or "preview",
            vpi_score=vpi,
            user_handle=author,
            content_title=resolved_title,
            e_act=e_act,
            e_base=e_base,
            gamma=gamma,
            recorded_date=req_date or "2026-08-20",
            level_name=resolved_level_name
        )
        return FileResponse(image_path, media_type="image/png")
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
        image_path = await generate_mug_preview_png(
            record_id=record_id,
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

        if not post_data and token != "REC_8F9A2B":
            raise HTTPException(status_code=404, detail="Token not found")

        return {"status": "ready", "token": token}

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e) or repr(e))

@app.post("/api/checkout/create-session")
def create_checkout_session(req: CheckoutSessionRequest):
    try:
        unit_amount = 1900
        
        vpi_ratio = "+8.7x"
        level_name = "LVL 5 — OUTLIER"
        content_title = "Viral Performance Accreditation"
        date_str = "2026-08-20"

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
            except Exception as err:
                print(f"Error fetching metadata for checkout session: {err}")

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
            shipping_options=[
                {
                    'shipping_rate_data': {
                        'type': 'fixed_amount',
                        'fixed_amount': {'amount': 499, 'currency': 'usd'}, 
                        'display_name': 'Standard Tracked Shipping (US / EU / UK)',
                        'delivery_estimate': {
                            'minimum': {'unit': 'business_day', 'value': 3},
                            'maximum': {'unit': 'business_day', 'value': 7},
                        },
                    }
                },
                {
                    'shipping_rate_data': {
                        'type': 'fixed_amount',
                        'fixed_amount': {'amount': 1299, 'currency': 'usd'}, 
                        'display_name': 'Express Shipping',
                        'delivery_estimate': {
                            'minimum': {'unit': 'business_day', 'value': 2},
                            'maximum': {'unit': 'business_day', 'value': 5},
                        },
                    }
                }
            ],
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
                'date_str': date_str
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

    try:
        if STRIPE_WEBHOOK_SECRET:
            stripe.Webhook.construct_event(
                payload, stripe_signature, STRIPE_WEBHOOK_SECRET
            )
        event = json.loads(payload)
        
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"Webhook Error: {str(e)}")
    
    if event.get("type") == "checkout.session.completed":
        session = event.get("data", {}).get("object", {})
        metadata = session.get("metadata", {})
        
        claim_token = metadata.get("claim_token")
        
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
        level_name = metadata.get("level_name", "LVL 5 — OUTLIER")
        content_title = metadata.get("content_title", "Viral Performance Accreditation")
        date_str = metadata.get("date_str", "2026-08-20")

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
            except Exception as err:
                print(f"Error fetching post details for token {claim_token}: {err}")

        print(f"🚀 STARTING ORDER FULFILLMENT for {author} (Destination: {country_code})...")

        try:
            order_result = fulfill_trophy_order(
                author=author,
                vpi_ratio=vpi_ratio,
                level_name=level_name,
                content_title=content_title,
                date_str=date_str,
                shipping_address=shipping_info
            )
            
            product_id = order_result.get("product_id")
            if supabase and claim_token and product_id:
                supabase.table("posts").update({"printify_product_id": product_id}).eq("claim_token", claim_token).execute()
                
            print(f"✅ FULFILLMENT COMPLETE! Printify Order ID: {order_result.get('order_id')}")
            
        except Exception as err:
            print(f"❌ ERROR DURING ORDER FULFILLMENT: {err}")
            traceback.print_exc()
            
            if supabase and claim_token:
                try:
                    supabase.table("posts").update({"printify_product_id": "FAILED_ORDER_ERROR"}).eq("claim_token", claim_token).execute()
                except Exception as db_err:
                    print(f"Failed to update DB error state: {db_err}")
                    
            raise HTTPException(status_code=500, detail=f"Order fulfillment failed: {str(err)}")

    return {"status": "success"}