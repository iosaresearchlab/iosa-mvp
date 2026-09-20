"""Riaggancia ogni riga di outreach al record attivo piu' recente del canale.

Il problema: un claim token scade 15 giorni dopo il rilevamento, ma i creator
vengono selezionati settimane prima di scrivergli. Con una sola azione
Instagram al giorno, gli ultimi della lista ricevono un link gia' morto. E'
gia' successo: la tornata del 28 settembre puntava a due pagine scadute il 25
e il 27.

La soluzione non e' allungare la finestra - quella e' una scelta di prodotto,
i dati sono freschi per costruzione. E' ricordarsi che **una riga di outreach
riguarda un canale, non un record**: il record giusto e' quello attivo nel
momento in cui si scrive.

Da eseguire prima di ogni tornata di invii:

    python aggiorna_token_outreach.py --round 1            # mostra e basta
    python aggiorna_token_outreach.py --round 1 --scrivi

Chi non ha piu' nessun record attivo non viene toccato: si segnala e si
decide a mano se toglierlo dal round.
"""
import argparse
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
SERVICE_KEY = (os.getenv("SUPABASE_SERVICE_KEY") or "").strip()

# Sotto questa soglia il rapporto ha un denominatore troppo piccolo per
# reggere un messaggio: e' la stessa usata per selezionare il round 2.
BASELINE_MINIMA = 1000


def _testa():
    return {"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}"}


def righe_da_controllare(numero: int, solo_non_inviati: bool):
    par = {"select": "id,channel_id,author_name,claim_token,post_id,vpi_ratio,"
                     "vpi_level,contatto_stato,inviato_il",
           "round": f"eq.{numero}", "order": "author_name"}
    if solo_non_inviati:
        par["inviato_il"] = "is.null"
    r = requests.get(f"{SUPABASE_URL}/rest/v1/outreach", headers=_testa(),
                     params=par, timeout=30)
    r.raise_for_status()
    return r.json()


def migliore_record_attivo(channel_id: str):
    """Il record attivo con il VPI piu' alto per quel canale, se esiste."""
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/posts", headers=_testa(),
        params={"select": "id,claim_token,vpi_ratio,vpi_level,detected_at,baseline_score",
                "channel_id": f"eq.{channel_id}", "status": "eq.ACTIVE",
                "baseline_score": f"gte.{BASELINE_MINIMA}",
                "order": "vpi_ratio.desc", "limit": "1"},
        timeout=30)
    r.raise_for_status()
    dati = r.json()
    return dati[0] if dati else None


def scrivi(riga_id: str, record: dict):
    r = requests.patch(
        f"{SUPABASE_URL}/rest/v1/outreach",
        headers={**_testa(), "Content-Type": "application/json",
                 "Prefer": "return=representation"},
        params={"id": f"eq.{riga_id}"},
        json={"post_id": record["id"], "claim_token": record["claim_token"],
              "vpi_ratio": record["vpi_ratio"], "vpi_level": record["vpi_level"],
              "aggiornato_il": "now()"},
        timeout=30)
    r.raise_for_status()
    if not r.json():
        raise RuntimeError("UPDATE andato a vuoto: la chiave non e' service_role")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--round", type=int, default=1)
    ap.add_argument("--scrivi", action="store_true",
                    help="senza questo non tocca il database")
    ap.add_argument("--tutti", action="store_true",
                    help="include anche le righe gia' inviate")
    a = ap.parse_args()

    if not (SUPABASE_URL and SERVICE_KEY):
        sys.exit("Mancano SUPABASE_URL o SUPABASE_SERVICE_KEY in .env")

    righe = righe_da_controllare(a.round, not a.tutti)
    if not righe:
        print(f"Round {a.round}: niente da controllare.")
        return 0

    cambiati, invariati, senza_record = [], 0, []

    for riga in righe:
        record = migliore_record_attivo(riga["channel_id"])
        if record is None:
            senza_record.append(riga)
            continue
        if record["id"] == riga["post_id"]:
            invariati += 1
            continue
        cambiati.append((riga, record))

    print(f"Round {a.round}: {len(righe)} righe controllate\n")
    for riga, record in cambiati:
        print(f"  CAMBIA  {riga['author_name'][:30]:30} "
              f"{riga['claim_token']} -> {record['claim_token']}  "
              f"(VPI {riga['vpi_ratio']} -> {record['vpi_ratio']}, "
              f"rilevato {record['detected_at'][:10]})")
    for riga in senza_record:
        print(f"  NIENTE  {riga['author_name'][:30]:30} "
              f"nessun record attivo: va tolto dal round o riselezionato")

    print(f"\n{len(cambiati)} da aggiornare, {invariati} gia' al record giusto, "
          f"{len(senza_record)} senza record attivo.")

    if not cambiati:
        return 0

    if cambiati:
        print("\n  ATTENZIONE: cambiare il token cambia anche i numeri del")
        print("  messaggio. Se il testo per questi creator e' gia' scritto, va")
        print("  riscritto: altrimenti il messaggio racconta una misurazione e")
        print("  il link ne apre un'altra. Da usare PRIMA di redigere i testi.")

    if not a.scrivi:
        print("\nSola lettura: rilancia con --scrivi per aggiornare.")
        return 0

    for riga, record in cambiati:
        scrivi(riga["id"], record)
    print(f"Aggiornate {len(cambiati)} righe.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
