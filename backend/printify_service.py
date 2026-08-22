import os
import base64
import requests
from dotenv import load_dotenv

load_dotenv()

PRINTIFY_API_TOKEN = os.getenv("PRINTIFY_API_TOKEN")
PRINTIFY_SHOP_ID = os.getenv("PRINTIFY_SHOP_ID")
BASE_URL = "https://api.printify.com/v1"

headers = {
    "Authorization": f"Bearer {PRINTIFY_API_TOKEN}",
    "Content-Type": "application/json"
}

# Strict EU Customs Union definition for regional fallbacks
EU_COUNTRIES = {
    'AT', 'BE', 'BG', 'CY', 'CZ', 'DE', 'DK', 'EE', 'ES', 'FI', 
    'FR', 'GR', 'HR', 'HU', 'IE', 'IT', 'LT', 'LU', 'LV', 'MT', 
    'NL', 'PL', 'PT', 'RO', 'SE', 'SI', 'SK'
}

UK_COUNTRIES = {'GB', 'UK'}

def normalize_country(country_input):
    """Converts string inputs to standard 2-letter ISO codes."""
    if not country_input:
        return "US"
    
    clean_input = str(country_input).upper().strip()
    
    mapping = {
        'ITALY': 'IT', 'FRANCE': 'FR', 'GERMANY': 'DE', 'SPAIN': 'ES', 
        'UNITED STATES': 'US', 'USA': 'US', 'UNITED KINGDOM': 'GB',
        'NETHERLANDS': 'NL', 'POLAND': 'PL', 'AUSTRIA': 'AT', 
        'BELGIUM': 'BE', 'SWEDEN': 'SE', 'DENMARK': 'DK', 'FINLAND': 'FI', 
        'PORTUGAL': 'PT', 'IRELAND': 'IE', 'GREECE': 'GR', 'CANADA': 'CA', 
        'AUSTRALIA': 'AU'
    }
    return mapping.get(clean_input, clean_input)

def get_optimal_routing(target_country):
    """
    Hybrid Routing System:
    1. Determines the correct base Blueprint (1016 for EU, 68 for UK/Global).
    2. Searches dynamically for an exact local provider match (e.g. Harrier in UK) to ensure domestic shipping rates.
    3. Fails back securely to a valid active catalog provider if local is unavailable.
    """
    target_iso = normalize_country(target_country)
    
    # Security block for unsupported regions
    if target_iso not in EU_COUNTRIES and target_iso not in UK_COUNTRIES and target_iso != 'US':
        raise ValueError(f"Shipping to {target_iso} is currently not supported. We only ship to US, UK, and EU.")
    
    # Step 1: Define Base Strategy
    if target_iso in EU_COUNTRIES:
        blueprint_id = 1016
        fallback_provider = 26  # Textildruck Europa (Germany)
        region = "EU"
    elif target_iso in UK_COUNTRIES:
        # Blueprint 68 is used for UK mugs, dynamically routed to local UK provider (e.g. Harrier) for low domestic shipping
        blueprint_id = 68
        fallback_provider = None  
        region = "UK"
    else:
        blueprint_id = 68
        fallback_provider = 1   # SPOKE Custom Products (US)
        region = "US/GLOBAL"
        
    print(f"🌍 [ROUTING STRATEGY] Target: {target_iso} ({region}) -> Blueprint: {blueprint_id}")

    # Step 2: Dynamic Search for Nearest Local Provider (Checking Printify Catalog API)
    try:
        providers_url = f"{BASE_URL}/catalog/blueprints/{blueprint_id}/print_providers.json"
        response = requests.get(providers_url, headers=headers)
        
        if response.ok:
            providers = response.json()
            
            # 1. Search for a provider physically located in the target country (e.g., GB for UK)
            for p in providers:
                p_country = normalize_country(p.get("location", {}).get("country", ""))
                if p_country == target_iso:
                    provider_title = p.get('title', f"ID {p['id']}")
                    print(f"🎯 [LOCAL MATCH FOUND] Perfect local routing to {target_iso}: {provider_title}")
                    return blueprint_id, p["id"]
            
            # 2. If target is UK, explicitly scan for UK-based facilities (like Harrier) in the provider list
            if target_iso in UK_COUNTRIES:
                for p in providers:
                    p_country = normalize_country(p.get("location", {}).get("country", ""))
                    p_title = p.get("title", "").lower()
                    if p_country in UK_COUNTRIES or "harrier" in p_title:
                        provider_title = p.get('title', f"ID {p['id']}")
                        print(f"🎯 [UK REGIONAL MATCH FOUND] Routing to UK provider: {provider_title}")
                        return blueprint_id, p["id"]

            # 3. Catalog fallback: pick the first available active provider for this blueprint to prevent 404 errors
            if providers:
                valid_fallback_id = providers[0]["id"]
                print(f"🛡️ [CATALOG FALLBACK] No direct local provider found in {target_iso}. Falling back to active catalog provider ID {valid_fallback_id}.")
                return blueprint_id, valid_fallback_id
        else:
            print(f"⚠️ [API WARNING] Provider list fetch failed ({response.status_code})")
            
    except Exception as e:
        print(f"⚠️ [API WARNING] Dynamic search error: {e}")
        
    # Step 3: Hardcoded Fallback safety net
    if fallback_provider:
        print(f"🛡️ [REGIONAL FALLBACK] Using default fallback provider {fallback_provider}.")
        return blueprint_id, fallback_provider
    else:
        raise Exception(f"No valid print providers found for blueprint {blueprint_id} and target {target_iso}")

def get_variant_for_provider(blueprint_id, provider_id):
    """
    Fetches the correct variant ID dynamically, as variant IDs differ across providers.
    """
    variants_url = f"{BASE_URL}/catalog/blueprints/{blueprint_id}/print_providers/{provider_id}/variants.json"
    response = requests.get(variants_url, headers=headers)
    response.raise_for_status()
    
    variants = response.json().get("variants", [])
    
    if not variants:
        raise Exception(f"No variants found for blueprint {blueprint_id} and provider {provider_id}")
        
    # Attempt to explicitly find an 11oz white mug, otherwise default to the first
    chosen_variant = variants[0]["id"]
    for v in variants:
        title = v.get("title", "").lower()
        if "white" in title or "11oz" in title:
            chosen_variant = v["id"]
            break
            
    return chosen_variant

def upload_image_to_printify(image_path="trophy_design.png"):
    """Uploads local image to Printify via Base64."""
    with open(image_path, "rb") as file:
        encoded_image = base64.b64encode(file.read()).decode('utf-8')

    payload = {
        "file_name": os.path.basename(image_path),
        "contents": encoded_image
    }

    response = requests.post(f"{BASE_URL}/uploads/images.json", json=payload, headers=headers)
    
    if not response.ok:
        print(f"❌ Printify upload error ({response.status_code}): {response.text}")
        response.raise_for_status()

    image_data = response.json()
    print(f"✅ Image successfully uploaded. ID: {image_data['id']}")
    return image_data["id"]

def create_dynamic_mug_product(image_id, creator_name="Creator", target_country=None):
    """Creates the Mug product mapping to the optimized local/regional provider."""
    if not target_country:
        raise ValueError("❌ target_country is required for geographic routing.")
        
    blueprint_id, provider_id = get_optimal_routing(target_country)
    variant_id = get_variant_for_provider(blueprint_id, provider_id)

    payload = {
        "title": f"IOSA Official Trophy — {creator_name}",
        "description": f"Accredited Viral Performance Award for creator @{creator_name}",
        "blueprint_id": blueprint_id,
        "print_provider_id": provider_id,
        "variants": [
            {
                "id": variant_id,
                "price": 1900,
                "is_enabled": True
            } 
        ],
        "print_areas": [
            {
                "variant_ids": [variant_id],
                "placeholders": [
                    {
                        "position": "front",
                        "images": [
                            {
                                "id": image_id,
                                "x": 0.5,
                                "y": 0.5,
                                "scale": 1,
                                "angle": 0
                            }
                        ]
                    }
                ]
            }
        ]
    }

    url = f"{BASE_URL}/shops/{PRINTIFY_SHOP_ID}/products.json"
    response = requests.post(url, json=payload, headers=headers)
    
    if not response.ok:
        print(f"\n❌ [PRINTIFY API ERROR] Code {response.status_code}: {response.text}")
        response.raise_for_status()

    product_data = response.json()
    print(f"✅ Product configured for {target_country}! Product ID: {product_data['id']}")
    
    return product_data["id"], variant_id

def send_printify_order(product_id, variant_id, shipping_address, line_item_title="IOSA Trophy Mug"):
    """Dispatches the order to production."""
    payload = {
        "external_id": f"order_{os.urandom(4).hex()}",
        "line_items": [
            {
                "product_id": product_id,
                "variant_id": variant_id,
                "quantity": 1
            }
        ],
        "shipping_method": 1,
        "send_shipping_notification": True,
        "address_to": {
            "first_name": shipping_address.get("first_name", "Valued"),
            "last_name": shipping_address.get("last_name", "Creator"),
            "email": shipping_address.get("email", ""),
            "phone": shipping_address.get("phone", ""),
            "country": shipping_address.get("country", "IT"),
            "region": shipping_address.get("state", ""),
            "city": shipping_address.get("city", ""),
            "address1": shipping_address.get("line1", ""),
            "address2": shipping_address.get("line2", ""),
            "zip": shipping_address.get("postal_code", "")
        }
    }

    url = f"{BASE_URL}/shops/{PRINTIFY_SHOP_ID}/orders.json"
    response = requests.post(url, json=payload, headers=headers)
    
    if not response.ok:
        print(f"❌ Error submitting Printify order: {response.text}")
        response.raise_for_status()

    order_data = response.json()
    print(f"✅ Order dispatched to production! Order ID: {order_data['id']}")
    return order_data["id"]