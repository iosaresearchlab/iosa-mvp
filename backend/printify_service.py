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
        print(f"Errore caricamento immagine Printify ({response.status_code}): {response.text}")
        response.raise_for_status()

    image_data = response.json()
    print(f"Immagine caricata su Printify con successo. ID: {image_data['id']}")
    return image_data["id"]

def get_blueprint_setup(blueprint_id=68):
    """
    Recupera dinamicamente dal catalogo Printify un Print Provider attivo 
    e le varianti disponibili per il blueprint specificato (es. 68 = Tazza Ceramica).
    """
    # 1. Recupera i provider disponibili per questo modello
    providers_url = f"{BASE_URL}/catalog/blueprints/{blueprint_id}/print_providers.json"
    p_res = requests.get(providers_url, headers=headers)
    p_res.raise_for_status()
    providers = p_res.json()

    if not providers:
        raise Exception(f"Nessun Print Provider trovato per il blueprint {blueprint_id}")

    # Selezioniamo il primo provider disponibile nel catalogo
    provider = providers[0]
    provider_id = provider["id"]
    provider_title = provider.get("title", f"Provider #{provider_id}")
    print(f"Provider selezionato dal catalogo: {provider_title} (ID: {provider_id})")

    # 2. Recupera le varianti attive per questo provider
    variants_url = f"{BASE_URL}/catalog/blueprints/{blueprint_id}/print_providers/{provider_id}/variants.json"
    v_res = requests.get(variants_url, headers=headers)
    v_res.raise_for_status()
    variants = v_res.json().get("variants", [])

    if not variants:
        raise Exception(f"Nessuna variante trovata per il provider {provider_id}")

    # Selezioniamo la prima variante attiva (es. tazza standard 11oz)
    variant_ids = [variants[0]["id"]]
    print(f"Variante selezionata dal catalogo: ID {variant_ids[0]}")

    return provider_id, variant_ids

def create_dynamic_mug_product(image_id, creator_name="Rick Astley"):
    """Crea un prodotto Tazza Ceramica personalizzato su Printify con la targa generata."""
    blueprint_id = 68  # White Ceramic Mug 11oz
    
    # Estrazione dinamica dal catalogo per evitare ID non validi
    provider_id, variant_ids = get_blueprint_setup(blueprint_id)

    payload = {
        "title": f"IOSA Official Trophy — {creator_name}",
        "description": f"Accredited Viral Performance Award for creator @{creator_name}",
        "blueprint_id": blueprint_id,
        "print_provider_id": provider_id,
        "variants": [
            {
                "id": vid,
                "price": 1900,  # Prezzo in centesimi ($19.00)
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
    
    # In caso di errore, visualizza la risposta JSON dettagliata di Printify
    if not response.ok:
        print(f"\n[ERRORE PRINTIFY API] Codice {response.status_code}:")
        try:
            print(response.json())
        except Exception:
            print(response.text)
        response.raise_for_status()

    product_data = response.json()
    print(f"\nProdotto creato su Printify con successo! Product ID: {product_data['id']}")
    return product_data["id"]

if __name__ == "__main__":
    img_id = upload_image_to_printify("trophy_design.png")
    prod_id = create_dynamic_mug_product(img_id, "Rick Astley")

def send_printify_order(product_id, variant_id, shipping_address, line_item_title="IOSA Trophy Mug"):
    """
    Invia l'ordine di stampa e spedizione a Printify dopo che Stripe ha confermato il pagamento.
    """
    payload = {
        "external_id": f"order_{os.urandom(4).hex()}",
        "line_items": [
            {
                "product_id": product_id,
                "variant_id": variant_id,
                "quantity": 1
            }
        ],
        "shipping_method": 1,  # Standard shipping
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
        print(f"Errore creazione ordine Printify: {response.text}")
        response.raise_for_status()

    order_data = response.json()
    print(f"✅ Ordine inviato con successo a Printify! Order ID: {order_data['id']}")
    return order_data["id"]