"""
Pulizia periodica del catalogo Printify.

Ogni ordine crea un prodotto personalizzato nello shop. E' il comportamento
voluto - l'oggetto deve restare unico - ma i prodotti restano in catalogo per
sempre. Questo script rimuove quelli vecchi, quando l'ordine e' ormai
consegnato da tempo e il prodotto non serve piu' a nulla.

Di default NON cancella nulla: stampa solo cosa farebbe.

    python cleanup_printify_products.py                 # simulazione
    python cleanup_printify_products.py --giorni 90     # simulazione, soglia diversa
    python cleanup_printify_products.py --applica       # cancella davvero
"""

import argparse
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

from log_iosa import configura, prendi

log = prendi(__name__)

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

PRINTIFY_API_TOKEN = os.getenv("PRINTIFY_API_TOKEN")
PRINTIFY_SHOP_ID = os.getenv("PRINTIFY_SHOP_ID")
BASE_URL = "https://api.printify.com/v1"

GIORNI_DI_GRAZIA_DEFAULT = 60

HEADERS = {
    "Authorization": f"Bearer {PRINTIFY_API_TOKEN}",
    "Content-Type": "application/json",
}


def eta_in_giorni(data_iso: str):
    if not data_iso:
        return None
    for formato in ("%Y-%m-%d %H:%M:%S%z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S"):
        try:
            d = datetime.strptime(data_iso, formato)
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            return (datetime.now(timezone.utc) - d).days
        except ValueError:
            continue
    return None


def elenca_prodotti():
    """Scorre tutte le pagine del catalogo dello shop."""
    prodotti = []
    pagina = 1
    while True:
        url = f"{BASE_URL}/shops/{PRINTIFY_SHOP_ID}/products.json?page={pagina}&limit=50"
        risposta = requests.get(url, headers=HEADERS, timeout=20)
        if not risposta.ok:
            log.error(f"Errore nel leggere la pagina {pagina}: {risposta.status_code} {risposta.text[:200]}")
            break
        dati = risposta.json()
        lotto = dati.get("data", [])
        prodotti.extend(lotto)
        if len(lotto) < 50:
            break
        pagina += 1
        time.sleep(0.3)
    return prodotti


def cancella_prodotto(product_id: str) -> bool:
    url = f"{BASE_URL}/shops/{PRINTIFY_SHOP_ID}/products/{product_id}.json"
    risposta = requests.delete(url, headers=HEADERS, timeout=20)
    if risposta.ok:
        return True
    log.info(f"   non cancellato ({risposta.status_code}): {risposta.text[:160]}")
    return False


def main():
    parser = argparse.ArgumentParser(description="Pulizia del catalogo Printify.")
    parser.add_argument("--giorni", type=int, default=GIORNI_DI_GRAZIA_DEFAULT,
                        help=f"cancella solo i prodotti piu' vecchi di N giorni (default {GIORNI_DI_GRAZIA_DEFAULT})")
    parser.add_argument("--applica", action="store_true",
                        help="cancella davvero; senza questo flag e' una simulazione")
    args = parser.parse_args()

    if not PRINTIFY_API_TOKEN or not PRINTIFY_SHOP_ID:
        log.info("PRINTIFY_API_TOKEN o PRINTIFY_SHOP_ID mancanti nel .env")
        sys.exit(1)

    prodotti = elenca_prodotti()
    log.info(f"Prodotti in catalogo: {len(prodotti)}")

    da_cancellare = []
    senza_data = 0
    for p in prodotti:
        eta = eta_in_giorni(p.get("created_at", ""))
        if eta is None:
            senza_data += 1
            continue
        if eta > args.giorni:
            da_cancellare.append((p["id"], p.get("title", "(senza titolo)"), eta))

    if senza_data:
        log.warning(f"Saltati {senza_data} prodotti senza data leggibile.")

    if not da_cancellare:
        log.info(f"Nessun prodotto piu' vecchio di {args.giorni} giorni. Niente da fare.")
        return

    log.info(f"\nPiu' vecchi di {args.giorni} giorni: {len(da_cancellare)}")
    for pid, titolo, eta in da_cancellare[:20]:
        log.info(f"   {pid}  {eta:>4} giorni  {titolo[:60]}")
    if len(da_cancellare) > 20:
        log.info(f"   ... e altri {len(da_cancellare) - 20}")

    if not args.applica:
        log.info("\nSIMULAZIONE: non e' stato cancellato nulla.")
        log.info("Rilancia con --applica per procedere davvero.")
        return

    log.info("\nCancellazione in corso...")
    cancellati = 0
    for pid, titolo, _ in da_cancellare:
        if cancella_prodotto(pid):
            cancellati += 1
        time.sleep(0.3)
    log.info(f"\nCancellati {cancellati} prodotti su {len(da_cancellare)}.")


if __name__ == "__main__":
    configura()
    main()
