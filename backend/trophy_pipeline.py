import re
import uuid

from generate_trophy import create_trophy_image
from printify_service import (
    upload_image_to_printify,
    create_dynamic_mug_product,
    send_printify_order,
)

# Aree di spedizione servite dai print provider configurati.
SUPPORTED_REGIONS = {
    'US', 'GB', 'UK', 'AT', 'BE', 'BG', 'CY', 'CZ', 'DE', 'DK', 'EE',
    'ES', 'FI', 'FR', 'GR', 'HR', 'HU', 'IE', 'IT', 'LT', 'LU', 'LV',
    'MT', 'NL', 'PL', 'PT', 'RO', 'SE', 'SI', 'SK'
}


def _safe_id(value) -> str:
    """Identificativo sicuro come nome file. I claim_token restano invariati."""
    return re.sub(r'[^A-Za-z0-9_-]', '_', str(value or ''))[:120]


def generate_and_publish_trophy(
    author: str,
    vpi_ratio: str,
    level_name: str,
    content_title: str,
    date_str: str,
    target_country: str = "US",
    e_act: str = "N/A",
    e_base: str = "N/A",
    record_id: str = None,
    claim_base_url: str = None,
):
    """
    Pipeline end-to-end: rendering della targa, upload su Printify e
    configurazione del prodotto sul provider piu' vicino al destinatario.

    record_id deve essere il claim_token reale: finisce nel QR stampato.
    """
    safe_id = _safe_id(record_id) or f"order_{uuid.uuid4().hex[:6]}"

    try:
        print(f"\n[PIPELINE] 1. Rendering artwork for {author}...")
        rendered_path = create_trophy_image(
            author=author,
            vpi_ratio=vpi_ratio,
            level_name=level_name,
            content_title=content_title,
            date_str=date_str,
            output_path=f"renders/trophy_{safe_id}.png",
            e_act=e_act,
            e_base=e_base,
            record_id=safe_id,
            claim_base_url=claim_base_url,
        )

        print("[PIPELINE] 2. Uploading asset to Printify...")
        image_id = upload_image_to_printify(rendered_path)

        print(f"[PIPELINE] 3. Configuring product for target country: {target_country}...")
        product_id, variant_id = create_dynamic_mug_product(
            image_id=image_id,
            creator_name=author,
            target_country=target_country,
        )

        return product_id, variant_id

    except Exception as e:
        print(f"[PIPELINE] Errore durante l'esecuzione: {e}")
        raise


def fulfill_trophy_order(
    author: str,
    vpi_ratio: str,
    level_name: str,
    content_title: str,
    date_str: str,
    shipping_address: dict,
    e_act: str = "N/A",
    e_base: str = "N/A",
    claim_token: str = None,
    external_ref: str = None,
    shipping_method: int = 1,
):
    """
    Innescata dal webhook Stripe. external_ref e' l'ID sessione Stripe e rende
    l'ordine idempotente: un retry non genera un secondo ordine a pagamento.
    """
    country_code = shipping_address.get("country", "US").upper()

    if country_code not in SUPPORTED_REGIONS:
        err_msg = f"Order blocked: Shipping to {country_code} is currently not supported (Allowed: US/UK/EU)."
        print(f"[FULFILLMENT] {err_msg}")
        raise ValueError(err_msg)

    print(f"\n[FULFILLMENT] Avvio ordine - Destinazione: {country_code}")

    product_id, variant_id = generate_and_publish_trophy(
        author=author,
        vpi_ratio=vpi_ratio,
        level_name=level_name,
        content_title=content_title,
        date_str=date_str,
        target_country=country_code,
        e_act=e_act,
        e_base=e_base,
        record_id=claim_token,
    )

    print("[PIPELINE] 4. Transmitting final order...")
    order_id = send_printify_order(
        product_id=product_id,
        variant_id=variant_id,
        shipping_address=shipping_address,
        line_item_title=f"IOSA Official Trophy - {author}",
        external_ref=external_ref,
        shipping_method=shipping_method,
    )

    return {
        "product_id": product_id,
        "variant_id": variant_id,
        "order_id": order_id,
    }
