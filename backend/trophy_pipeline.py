import os
import re
import uuid
from generate_trophy import create_trophy_image #[cite: 11]
from printify_service import upload_image_to_printify, create_dynamic_mug_product, send_printify_order #[cite: 11]

def generate_and_publish_trophy(author: str, vpi_ratio: str, level_name: str, content_title: str, date_str: str, target_country: str = "US"):
    """
    End-to-End pipeline for custom Printify product generation.
    Handles rendering, upload, and dynamic region-based routing.
    """
    # Create safe filename #[cite: 11]
    safe_author = re.sub(r'[^\w\-]', '_', author.lower()) #[cite: 11]
    unique_suffix = uuid.uuid4().hex[:6] #[cite: 11]
    temp_img_path = f"trophy_{safe_author}_{unique_suffix}.png" #[cite: 11]

    try:
        print(f"\n[PIPELINE] 1. Rendering artwork for {author}...")
        create_trophy_image(
            author=author,
            vpi_ratio=vpi_ratio,
            level_name=level_name,
            content_title=content_title,
            date_str=date_str,
            output_path=temp_img_path
        ) #[cite: 11]

        print("[PIPELINE] 2. Uploading asset to Printify...")
        image_id = upload_image_to_printify(temp_img_path) #[cite: 11]

        print(f"[PIPELINE] 3. Configuring product for target country: {target_country}...")
        product_id, variant_id = create_dynamic_mug_product(
            image_id=image_id, 
            creator_name=author, 
            target_country=target_country
        ) #[cite: 11]

        return product_id, variant_id

    except Exception as e:
        print(f"❌ Critical error during pipeline execution: {e}")
        raise e #[cite: 11]

    finally:
        # File cleanup to prevent clutter #[cite: 11]
        if os.path.exists(temp_img_path): #[cite: 11]
            os.remove(temp_img_path) #[cite: 11]

def fulfill_trophy_order(author: str, vpi_ratio: str, level_name: str, content_title: str, date_str: str, shipping_address: dict):
    """
    Triggered by Stripe Webhook. Extracts the country code for optimal routing calculation.
    """
    country_code = shipping_address.get("country", "US") #[cite: 11]
    
    print(f"\n📦 STARTING ORDER FULFILLMENT — Destination: {country_code}")
    
    product_id, variant_id = generate_and_publish_trophy(
        author=author,
        vpi_ratio=vpi_ratio,
        level_name=level_name,
        content_title=content_title,
        date_str=date_str,
        target_country=country_code
    ) #[cite: 11]
    
    print("[PIPELINE] 4. Transmitting final order...")
    order_id = send_printify_order(
        product_id=product_id,
        variant_id=variant_id,
        shipping_address=shipping_address,
        line_item_title=f"IOSA Official Trophy — {author}"
    ) #[cite: 11]
    
    return {
        "product_id": product_id,
        "variant_id": variant_id,
        "order_id": order_id
    } #[cite: 11]

if __name__ == "__main__":
    # Local testing setup #[cite: 11]
    test_address = {
        "first_name": "Marco",
        "last_name": "Rossi",
        "email": "marco.rossi@test.com",
        "country": "FR", # Set to "US", "GB" or "IT" to test geographic logic
        "city": "Paris",
        "line1": "22 Boulevard Saint-Germain",
        "postal_code": "75005"
    } #[cite: 11]
    
    fulfill_trophy_order(
        author="ThaisSantana",
        vpi_ratio="8.7",
        level_name="LVL 5 — OUTLIER",
        content_title="Viral Video Title",
        date_str="2026-08-21",
        shipping_address=test_address
    ) #[cite: 11]