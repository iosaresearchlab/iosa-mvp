"""Rende in anticipo le targhe dei creator che stiamo per contattare.

La prima richiesta di una targa costa dodici-venti secondi: Chromium si apre,
impagina, screenshotta. Se quella prima richiesta capita al creator che ha
appena aperto il nostro messaggio, vede una pagina che carica e se ne va.

Questo script fa in modo che la prima richiesta sia la nostra. Chiama
l'endpoint di anteprima in produzione, che rende e archivia su Storage: da li'
in poi la targa arriva dal CDN, istantanea.

    python scalda_targhe.py                # i contattabili del round 2
    python scalda_targhe.py --round 1
    python scalda_targhe.py --token iosa_xxx iosa_yyy

Non serve Playwright in locale: il rendering avviene sul backend.
"""
import argparse
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
SERVICE_KEY = (os.getenv("SUPABASE_SERVICE_KEY") or "").strip()
BACKEND = (os.getenv("BACKEND_URL")
           or "https://iosa-mvp-backend.onrender.com").strip().rstrip("/")


def token_del_round(numero: int):
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/outreach",
        headers={"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}"},
        params={"select": "author_name,claim_token,contatto_stato",
                "round": f"eq.{numero}", "claim_token": "not.is.null"},
        timeout=30,
    )
    r.raise_for_status()
    # Chi non e' raggiungibile non aprira' mai la pagina: non vale il rendering.
    return [(v["author_name"], v["claim_token"]) for v in r.json()
            if v["contatto_stato"] in ("TROVATO", "DA_CERCARE")]


def scalda(nome: str, token: str) -> bool:
    inizio = time.monotonic()
    try:
        r = requests.get(f"{BACKEND}/api/trophy/preview",
                         params={"claim_token": token}, timeout=180)
        secondi = time.monotonic() - inizio
        if r.status_code == 200:
            print(f"  OK   {nome[:32]:32} {secondi:5.1f}s  {len(r.content)//1024} KB")
            return True
        print(f"  FAIL {nome[:32]:32} {secondi:5.1f}s  HTTP {r.status_code}")
    except requests.RequestException as e:
        print(f"  FAIL {nome[:32]:32} {type(e).__name__}: {e}")
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--round", type=int, default=2)
    ap.add_argument("--token", nargs="*", default=None)
    ap.add_argument("--pausa", type=float, default=2.0,
                    help="secondi tra una targa e l'altra, per non saturare il backend")
    a = ap.parse_args()

    if a.token:
        voci = [(t, t) for t in a.token]
    else:
        if not (SUPABASE_URL and SERVICE_KEY):
            sys.exit("Mancano SUPABASE_URL o SUPABASE_SERVICE_KEY in .env")
        voci = token_del_round(a.round)

    if not voci:
        print("Niente da scaldare.")
        return 0

    print(f"{len(voci)} targhe da scaldare su {BACKEND}")
    print("La prima di ognuna costa una ventina di secondi: e' il punto.\n")
    fatte = 0
    for nome, token in voci:
        fatte += scalda(nome, token)
        time.sleep(a.pausa)

    print(f"\n{fatte} su {len(voci)} pronte in archivio.")
    return 0 if fatte == len(voci) else 1


if __name__ == "__main__":
    sys.exit(main())
