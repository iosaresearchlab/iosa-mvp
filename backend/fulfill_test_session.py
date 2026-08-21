import os
import stripe
from dotenv import load_dotenv
from printify_service import send_printify_order

load_dotenv()
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

def fulfill_latest_session():
    sessions = stripe.checkout.Session.list(limit=1)
    if not sessions.data:
        print("❌ Nessuna sessione di checkout trovata su Stripe.")
        return

    # Converti l'oggetto SDK Stripe in un dizionario Python
    session = sessions.data[0].to_dict()
    print(f"Recuperata ultima sessione Stripe: {session.get('id')} (Stato: {session.get('payment_status')})")

    metadata = session.get("metadata") or {}
    product_id = metadata.get("printify_product_id")
    
    shipping = session.get("shipping_details") or {}
    address = shipping.get("address") or {}
    customer = session.get("customer_details") or {}

    shipping_info = {
        "first_name": (shipping.get("name") or "Creator").split(" ")[0],
        "last_name": " ".join((shipping.get("name") or "IOSA").split(" ")[1:]) or "IOSA",
        "email": customer.get("email", ""),
        "phone": customer.get("phone", ""),
        "country": address.get("country", "IT"),
        "state": address.get("state", ""),
        "city": address.get("city", ""),
        "line1": address.get("line1", ""),
        "line2": address.get("line2", ""),
        "postal_code": address.get("postal_code", "")
    }

    if not product_id:
        print("❌ Nessun printify_product_id trovato nei metadata della sessione.")
        return

    print(f"Invio ordine a Printify per Prodotto: {product_id}...")
    send_printify_order(
        product_id=product_id,
        variant_id=33719,
        shipping_address=shipping_info
    )

if __name__ == "__main__":
    fulfill_latest_session()