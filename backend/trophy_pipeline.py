import os
import re
import uuid
from generate_trophy import create_trophy_image
from printify_service import upload_image_to_printify, create_dynamic_mug_product, send_printify_order

def generate_and_publish_trophy(author: str, vpi_ratio: str, level_name: str, content_title: str, date_str: str, target_country: str = "US"):
    """
    End-to-End pipeline for Printify custom product creation:
    1. Generates the customized trophy award image.
    2. Uploads the image asset to Printify.
    3. Creates the custom Mug product selecting the optimal local provider (EU or US).
    4. Returns a tuple of (product_id, variant_id).
    """
    # Sanitize author handle to create a safe temporary file name
    safe_author = re.sub(r'[^\w\-]', '_', author.lower())
    unique_suffix = uuid.uuid4().hex[:6]
    temp_img_path = f"trophy_{safe_author}_{unique_suffix}.png"

    try:
        print(f"\n1. Generating custom trophy award for {author}...")
        create_trophy_image(
            author=author,
            vpi_ratio=vpi_ratio,
            level_name=level_name,
            content_title=content_title,
            date_str=date_str,
            output_path=temp_img_path
        )

        print("2. Uploading artwork to Printify...")
        image_id = upload_image_to_printify(temp_img_path)

        print(f"3. Creating Mug product on Printify (Target Country: {target_country})...")
        product_id, variant_id = create_dynamic_mug_product(
            image_id=image_id, 
            creator_name=author, 
            target_country=target_country
        )

        print(f"✅ Product successfully configured! Product ID: {product_id}, Variant ID: {variant_id}")
        return product_id, variant_id

    except Exception as e:
        print(f"❌ Pipeline error during trophy generation/publishing: {e}")
        raise e

    finally:
        if os.path.exists(temp_img_path):
            os.remove(temp_img_path)

def fulfill_trophy_order(author: str, vpi_ratio: str, level_name: str, content_title: str, date_str: str, shipping_address: dict):
    """
    Function triggered upon Stripe webhook order completion:
    - Extracts buyer country code from shipping address.
    - Generates and publishes the product on the appropriate local print provider.
    - Submits order to Printify with native variant ID for local fulfillment.
    """
    country_code = shipping_address.get("country", "US")
    
    print(f"📦 Initiating order fulfillment for {author} — Destination: {country_code}")
    
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
    # Test execution with EU shipping address (France)
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