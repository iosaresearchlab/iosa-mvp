import os
from generate_trophy import create_trophy_image
from printify_service import upload_image_to_printify, create_dynamic_mug_product, send_printify_order

def generate_and_publish_trophy(author, vpi_ratio, level_name, content_title, date_str, target_country="US"):
    """
    Pipeline End-to-End per la creazione del prodotto personalizzato su Printify:
    1. Genera l'immagine della targa personalizzata
    2. Carica l'immagine su Printify
    3. Crea il prodotto Tazza su Printify scegliendo il provider locale (EU o US)
    4. Ritorna tuple (product_id, variant_id)
    """
    temp_img_path = f"trophy_{author.lower().replace(' ', '_')}.png"

    try:
        print(f"\n1. Generazione targa per {author}...")
        create_trophy_image(
            author=author,
            vpi_ratio=vpi_ratio,
            level_name=level_name,
            content_title=content_title,
            date_str=date_str,
            output_path=temp_img_path
        )

        print("2. Caricamento targa su Printify...")
        image_id = upload_image_to_printify(temp_img_path)

        print(f"3. Creazione prodotto Tazza su Printify (Destinazione: {target_country})...")
        product_id, variant_id = create_dynamic_mug_product(
            image_id=image_id, 
            creator_name=author, 
            target_country=target_country
        )

        print(f"✅ Prodotto configurato con successo! Product ID: {product_id}, Variant ID: {variant_id}")
        return product_id, variant_id

    finally:
        if os.path.exists(temp_img_path):
            os.remove(temp_img_path)

def fulfill_trophy_order(author, vpi_ratio, level_name, content_title, date_str, shipping_address):
    """
    Funzione invocate nel Webhook di Stripe al completamento dell'ordine.
    - Rileva il paese dell'acquirente dall'indirizzo
    - Crea il prodotto sul provider locale
    - Invia l'ordine a Printify con il variant_id nativo del provider locale
    """
    country_code = shipping_address.get("country", "US")
    
    print(f"📦 Avvio evasione ordine per {author} — Destinazione: {country_code}")
    
    product_id, variant_id = generate_and_publish_trophy(
        author=author,
        vpi_ratio=vpi_ratio,
        level_name=level_name,
        content_title=content_title,
        date_str=date_str,
        target_country=country_code
    )
    
    order_id = send_printify_order(
        product_id=product_id,
        variant_id=variant_id,
        shipping_address=shipping_address,
        line_item_title=f"IOSA Official Trophy — {author}"
    )
    
    return {
        "product_id": product_id,
        "variant_id": variant_id,
        "order_id": order_id
    }

if __name__ == "__main__":
    # Test esecutivo con indirizzo FR
    test_address = {
        "first_name": "Creator",
        "last_name": "EU",
        "email": "creatorEU@test.com",
        "country": "FR",
        "city": "Paris",
        "line1": "22 Boulevard Saint-Germain",
        "postal_code": "75005"
    }
    fulfill_trophy_order(
        author="ThaisSantana",
        vpi_ratio="8.7",
        level_name="LVL 5 — OUTLIER",
        content_title="Viral Video Title",
        date_str="2026-08-20",
        shipping_address=test_address
    )