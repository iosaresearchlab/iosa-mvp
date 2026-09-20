"""Cerca un contatto pubblico per i canali selezionati per l'outreach.

Primo passaggio, quello a costo quasi zero: la descrizione del canale.
Moltissimi creator ci mettono l'email di lavoro. channels.list accetta 50 id
per chiamata e costa 1 unita' di quota a chiamata, quindi 72 canali costano
2 unita' su 10.000.

Chi non ha un'email nella descrizione resta DA_CERCARE: quello va guardato
a mano (pannello Informazioni, sito collegato, Linktree) e costa tempo, non
quota. Separare i due passaggi evita di spendere ore di browser su canali
che avevano l'indirizzo scritto in chiaro.

    python outreach_contatti.py            # round 2, solo lettura
    python outreach_contatti.py --scrivi   # aggiorna la tabella outreach
"""
import argparse
import os
import re
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
SERVICE_KEY = (os.getenv("SUPABASE_SERVICE_KEY") or "").strip()
YOUTUBE_KEY = (os.getenv("YOUTUBE_API_KEY") or "").strip()

# Un'email nella descrizione del canale. Volutamente prudente: niente indirizzi
# con caratteri strani, niente domini a una lettera.
EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

# Indirizzi che non sono il contatto del creator.
DA_IGNORARE = re.compile(
    r"(no-?reply|example\.com|youtube\.com|sentry\.io|@2x|\.png|\.jpg)", re.I
)


def _intestazioni():
    return {"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}"}


def canali_da_cercare(round_num: int):
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/outreach",
        headers=_intestazioni(),
        params={
            "select": "id,channel_id,channel_handle,author_name,country,"
                      "fascia_iscritti,banda_livello",
            "round": f"eq.{round_num}",
            "contatto_stato": "eq.DA_CERCARE",
            "order": "fascia_iscritti,banda_livello",
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def descrizioni(ids):
    """{channel_id: descrizione} per blocchi di 50. 1 unita' di quota a blocco."""
    fuori = {}
    for i in range(0, len(ids), 50):
        blocco = ids[i:i + 50]
        r = requests.get(
            "https://www.googleapis.com/youtube/v3/channels",
            params={"part": "snippet", "id": ",".join(blocco), "key": YOUTUBE_KEY},
            timeout=30,
        )
        if r.status_code != 200:
            # Restituire un risultato parziale qui sarebbe peggio di fallire:
            # ogni canale non letto sembrerebbe "senza email", cioe' un dato
            # dove invece c'e' solo una chiamata non riuscita.
            raise RuntimeError(
                f"YouTube ha risposto {r.status_code}: {r.text[:200]}"
            )
        for voce in r.json().get("items", []):
            fuori[voce["id"]] = voce["snippet"].get("description", "") or ""
        time.sleep(0.3)
    return fuori


def email_dalla_descrizione(testo: str):
    for trovata in EMAIL.findall(testo):
        if not DA_IGNORARE.search(trovata):
            return trovata
    return None


def aggiorna(riga_id: str, canale: str, valore: str, nota: str):
    r = requests.patch(
        f"{SUPABASE_URL}/rest/v1/outreach",
        headers={**_intestazioni(), "Content-Type": "application/json",
                 "Prefer": "return=representation"},
        params={"id": f"eq.{riga_id}"},
        json={"contatto_stato": "TROVATO", "contatto_canale": canale,
              "contatto_valore": valore, "contatto_nota": nota},
        timeout=30,
    )
    r.raise_for_status()
    # La RLS fa passare l'UPDATE senza errore ma senza scrivere nulla se la
    # chiave non e' service_role: senza questo controllo il non-scritto
    # sembrerebbe un successo.
    if not r.json():
        raise RuntimeError("UPDATE andato a vuoto: la chiave non e' service_role")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--round", type=int, default=2)
    ap.add_argument("--scrivi", action="store_true",
                    help="senza questo non tocca il database")
    args = ap.parse_args()

    if not (SUPABASE_URL and SERVICE_KEY and YOUTUBE_KEY):
        sys.exit("Mancano SUPABASE_URL, SUPABASE_SERVICE_KEY o YOUTUBE_API_KEY in .env")

    righe = canali_da_cercare(args.round)
    if not righe:
        print(f"Round {args.round}: nessun canale da cercare.")
        return
    print(f"Round {args.round}: {len(righe)} canali da cercare "
          f"({(len(righe) + 49) // 50} unita' di quota).\n")

    testi = descrizioni([r["channel_id"] for r in righe])
    trovati, senza = [], []

    for riga in righe:
        indirizzo = email_dalla_descrizione(testi.get(riga["channel_id"], ""))
        cella = f"{riga['fascia_iscritti']}/{riga['banda_livello']}"
        if indirizzo:
            trovati.append((riga, indirizzo))
            print(f"  OK   {cella:8} {riga['author_name'][:28]:28} {indirizzo}")
        else:
            senza.append(riga)

    print()
    for riga in senza:
        cella = f"{riga['fascia_iscritti']}/{riga['banda_livello']}"
        print(f"  --   {cella:8} {riga['author_name'][:28]:28} "
              f"youtube.com/{riga['channel_handle']}")

    print(f"\n{len(trovati)} con email nella descrizione, "
          f"{len(senza)} da guardare a mano.")

    if not args.scrivi:
        print("Sola lettura: rilancia con --scrivi per aggiornare la tabella.")
        return

    for riga, indirizzo in trovati:
        aggiorna(riga["id"], "email", indirizzo, "email nella descrizione del canale")
    print(f"Scritti {len(trovati)} contatti.")


if __name__ == "__main__":
    main()
