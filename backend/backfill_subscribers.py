"""
Ripopola subscribers sui record che ce l'hanno a NULL o con la vecchia sentinella.

Perche' serve
-------------
Prima della correzione del 19/09, fetch_channels_metadata mandava a
channels.list piu' di 50 id per chiamata. YouTube rispondeva 400 e la
funzione restituiva {} in silenzio, quindi ogni record di quel giro finiva
con 999_999_999 (e, dopo la prima correzione, con NULL). Il risultato e'
che ~89% dei record attivi non aveva il numero di iscritti, pur trattandosi
di canali che lo espongono pubblicamente.

Ora che ogni record ha channel_id il recupero e' diretto e costa poco:
una chiamata ogni 50 canali distinti, cioe' ~195 unita' di quota in tutto.

Uso
---
    python backfill_subscribers.py --stato
    python backfill_subscribers.py --secondi 95

Fail-safe: se channels.list non risponde 200 il blocco viene saltato e
nessun valore esistente viene toccato. Un canale che nasconde davvero gli
iscritti resta a NULL, che e' l'unica rappresentazione onesta.
"""

import argparse
import base64
import io
import json
import os
import sys
import time

import requests
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
from supabase import create_client

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = (
    os.getenv("SUPABASE_SERVICE_KEY")
    or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or os.getenv("SUPABASE_KEY")
)

SENTINELLA = 999_999_999
BLOCCO = 50
PAGINA = 1000


def _ruolo(chiave: str) -> str:
    if chiave.startswith("sb_secret_"):
        return "service_role"
    if chiave.startswith("sb_publishable_"):
        return "anon"
    try:
        corpo = chiave.split(".")[1]
        corpo += "=" * (-len(corpo) % 4)
        return json.loads(base64.urlsafe_b64decode(corpo)).get("role", "?")
    except Exception:
        return "?"


def _client(serve_scrittura: bool = False):
    if not (SUPABASE_URL and SUPABASE_KEY):
        sys.exit("Mancano SUPABASE_URL / SUPABASE_SERVICE_KEY nell'ambiente.")
    if serve_scrittura and _ruolo(SUPABASE_KEY) != "service_role":
        sys.exit(
            "Serve una chiave service_role: con la chiave pubblica l'UPDATE non\n"
            "scrive nulla e PostgREST risponde comunque 200."
        )
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def da_sistemare(sb) -> list:
    """Record attivi con channel_id noto e iscritti mancanti o sentinella."""
    righe, da = [], 0
    while True:
        blocco = (
            sb.table("posts")
            .select("id, channel_id, subscribers")
            .eq("platform", "YOUTUBE")
            .eq("status", "ACTIVE")
            .not_.is_("channel_id", "null")
            .or_(f"subscribers.is.null,subscribers.eq.{SENTINELLA}")
            .range(da, da + PAGINA - 1)
            .execute()
            .data
            or []
        )
        righe.extend(blocco)
        if len(blocco) < PAGINA:
            return righe
        da += PAGINA


def iscritti(channel_ids: list, contatore: dict, scadenza: float) -> dict:
    """{channel_id: iscritti|None}. Un canale assente dalla risposta non entra."""
    out = {}
    unici = sorted(set(channel_ids))
    for i in range(0, len(unici), BLOCCO):
        if time.time() > scadenza:
            break
        b = unici[i:i + BLOCCO]
        try:
            r = requests.get(
                "https://www.googleapis.com/youtube/v3/channels"
                f"?part=statistics&id={','.join(b)}&key={YOUTUBE_API_KEY}",
                timeout=15,
            )
        except Exception as exc:
            print(f"  rete: {exc} — blocco saltato")
            continue
        contatore["quota"] += 1
        if r.status_code != 200:
            print(f"  HTTP {r.status_code} — blocco saltato")
            continue
        for item in r.json().get("items", []):
            s = item.get("statistics", {})
            if s.get("hiddenSubscriberCount") or "subscriberCount" not in s:
                out[item["id"]] = None
            else:
                out[item["id"]] = int(s["subscriberCount"])
        time.sleep(0.05)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stato", action="store_true")
    ap.add_argument("--secondi", type=int, default=95)
    ap.add_argument("--parallelo", type=int, default=12)
    args = ap.parse_args()

    sb = _client(serve_scrittura=not args.stato)
    righe = da_sistemare(sb)
    canali = sorted({r["channel_id"] for r in righe})
    print(f"Record da sistemare: {len(righe)} su {len(canali)} canali distinti "
          f"(~{-(-len(canali) // BLOCCO)} unita' di quota)")
    if args.stato or not righe:
        return

    scadenza = time.time() + args.secondi
    contatore = {"quota": 0}

    # La mappa canale -> iscritti si rilegge da disco: rilanciare lo script per
    # finire le scritture non deve ricomprare la stessa quota una seconda volta.
    cache_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "backfill_subscribers.json")
    mappa = {}
    if os.path.exists(cache_path):
        mappa = json.load(io.open(cache_path, encoding="utf-8"))
        print(f"Mappa gia' in cache: {len(mappa)} canali (0 unita' di quota)")
    mancanti = [c for c in canali if c not in mappa]
    if mancanti:
        mappa.update(iscritti(mancanti, contatore, scadenza - 20))
        json.dump(mappa, io.open(cache_path, "w", encoding="utf-8"))
    noti = {k: v for k, v in mappa.items() if v is not None}
    print(f"Canali risolti: {len(mappa)} — con iscritti pubblici: {len(noti)}")

    aggiornabili = [r for r in righe if r["channel_id"] in noti]
    print(f"Record aggiornabili adesso: {len(aggiornabili)}")

    esito = {"ok": 0, "ko": 0}

    def scrivi(riga):
        if time.time() > scadenza:
            return
        try:
            sb.table("posts").update(
                {"subscribers": noti[riga["channel_id"]]}
            ).eq("id", riga["id"]).execute()
            esito["ok"] += 1
        except Exception as exc:
            esito["ko"] += 1
            if esito["ko"] < 4:
                print(f"  update fallito: {exc}")

    with ThreadPoolExecutor(max_workers=args.parallelo) as pool:
        list(pool.map(scrivi, aggiornabili))

    print(f"Quota usata: {contatore['quota']} — scritti: {esito['ok']} — errori: {esito['ko']}")
    if esito["ok"] < len(aggiornabili) or len(mappa) < len(canali):
        print("Rilancia lo stesso comando per completare.")


if __name__ == "__main__":
    main()
