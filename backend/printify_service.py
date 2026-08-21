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

# Elenco rigoroso dei codici ISO europei supportati per il routing locale
EU_COUNTRIES = {
    'AT', 'BE', 'BG', 'CY', 'CZ', 'DE', 'DK', 'EE', 'ES', 'FI', 
    'FR', 'GR', 'HR', 'HU', 'IE', 'IT', 'LT', 'LU', 'LV', 'MT', 
    'NL', 'PL', 'PT', 'RO', 'SE', 'SI', 'SK', 'CH', 'NO', 'GB'
}

def upload_image_to_printify(image_path="trophy_design.png"):
    """Carica l'immagine locale nello storage media di Printify via Base64."""
    with open(image_path, "rb") as file:
        encoded_image = base64.b64encode(file.read()).decode('utf-8')

    payload = {
        "file_name": os.path.basename(image_path),
        "contents": encoded_image
    }

    response = requests.post(f"{BASE_URL}/uploads/images.json", json=payload, headers=headers)
    if not response.ok:
        print(f"❌ Errore caricamento immagine Printify ({response.status_code}): {response.text}")
        response.raise_for_status()

    image_data = response.json()
    print(f"✅ Immagine caricata su Printify. ID: {image_data['id']}")
    return image_data["id"]

def get_blueprint_setup(blueprint_id=68, target_country=None):
    """
    Seleziona il Print Provider locale imponendo una validazione rigida della nazione.
    Impedisce fallback accidentali sugli USA se la nazione non è valida.
    """
    if not target_country:
        raise ValueError("❌ ERRORE CRITICO: target_country non può essere vuoto o None! Impossibile determinare il routing di stampa.")

    target_country = target_country.upper().strip()
    
    # Normalizzazione nomi estesi comuni per evitare fallimenti
    country_mapping = {
        "ITALY": "IT", "FRANCE": "FR", "GERMANY": "DE", "SPAIN": "ES", 
        "UNITED STATES": "US", "USA": "US", "UNITED KINGDOM": "GB", "UK": "GB"
    }
    target_country = country_mapping.get(target_country, target_country)

    providers_url = f"{BASE_URL}/catalog/blueprints/{blueprint_id}/print_providers.json"
    p_res = requests.get(providers_url, headers=headers)
    p_res.raise_for_status()
    providers = p_res.json()

    if not providers:
        raise Exception(f"Nessun Print Provider trovato per il blueprint {blueprint_id}")

    selected_provider = None

    # 1. Match esatto per nazione (es. IT -> IT, GB -> GB)
    for p in providers:
        p_country = p.get("location", {}).get("country", "").upper()
        if p_country == target_country:
            selected_provider = p
            print(f"🌍 [ROUTING] Match esatto trovato nel Paese: {p_country}")
            break

    # 2. Match Regionale Europeo (se l'utente è in UE, cerca un provider europeo)
    if not selected_provider and target_country in EU_COUNTRIES:
        for p in providers:
            p_country = p.get("location", {}).get("country", "").upper()
            if p_country in EU_COUNTRIES:
                selected_provider = p
                print(f"🇪🇺 [ROUTING] Match europeo trovato. Stampato in: {p_country} per acquirente in {target_country}")
                break

    # 3. Fallback USA solo se l'utente è effettivamente negli USA o Nord America
    if not selected_provider and target_country == "US":
        for p in providers:
            p_country = p.get("location", {}).get("country", "").upper()
            if p_country == "US":
                selected_provider = p
                print(f"🇺🇸 [ROUTING] Fallback su provider USA.")
                break

    # 4. Se proprio non trova nulla ma la nazione è valida, prende il primo disponibile loggando un warning
    if not selected_provider:
        print(f"⚠️ [ATTENZIONE] Nessun provider locale perfetto per [{target_country}]. Uso il primo disponibile.")
        selected_provider = providers[0]

    provider_id = selected_provider["id"]
    provider_title = selected_provider.get("title", f"Provider #{provider_id}")
    provider_country = selected_provider.get("location", {}).get("country", "Unknown")
    
    print(f"📍 Destinazione Finale: [{target_country}] -> Print Provider: {provider_title} (ID: {provider_id}, stabilimento in: {provider_country})")

    # Recupera le varianti attive per questo specifico provider
    variants_url = f"{BASE_URL}/catalog/blueprints/{blueprint_id}/print_providers/{provider_id}/variants.json"
    v_res = requests.get(variants_url, headers=headers)
    v_res.raise_for_status()
    variants = v_res.json().get("variants", [])

    if not variants:
        raise Exception(f"Nessuna variante trovata per il provider {provider_id}")

    variant_ids = [variants[0]["id"]]
    return provider_id, variant_ids

def create_dynamic_mug_product(image_id, creator_name="Creator", target_country=None, blueprint_id=68):
    """Crea il prodotto tazza richiedendo obbligatoriamente il Paese di destinazione e parametrizzando il blueprint_id."""
    if not target_country:
        raise ValueError("❌ target_country obbligatorio mancante in create_dynamic_mug_product.")

    provider_id, variant_ids = get_blueprint_setup(blueprint_id, target_country=target_country)

    payload = {
        "title": f"IOSA Official Trophy — {creator_name}",
        "description": f"Accredited Viral Performance Award for creator @{creator_name}",
        "blueprint_id": blueprint_id,
        "print_provider_id": provider_id,
        "variants": [
            {
                "id": vid,
                "price": 1900,
                "is_enabled": True
            } for vid in variant_ids
        ],
        "print_areas": [
            {
                "variant_ids": variant_ids,
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
        print(f"\n❌ [ERRORE PRINTIFY API] Codice {response.status_code}: {response.text}")
        response.raise_for_status()

    product_data = response.json()
    product_id = product_data["id"]
    native_variant_id = variant_ids[0]
    
    print(f"✅ Prodotto configurato (Blueprint: {blueprint_id})! Product ID: {product_id}, Variant ID: {native_variant_id}")
    return product_id, native_variant_id

def send_printify_order(product_id, variant_id, shipping_address, line_item_title="IOSA Trophy Mug"):
    """Invia l'ordine di stampa e spedizione."""
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
        print(f"❌ Errore invio ordine Printify: {response.text}")
        response.raise_for_status()

    order_data = response.json()
    print(f"✅ Ordine inviato in produzione! Order ID: {order_data['id']}")
    return order_data["id"]