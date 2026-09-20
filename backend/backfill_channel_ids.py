"""
Backfill di channel_id e channel_handle sui record gia' in tabella.

Perche' serve
-------------
Fino alla correzione di vpi_engine.py l'handle veniva costruito cosi':

    "author_handle": f"@{snippet['channelTitle'].replace(' ', '')}"

cioe' inventato dal nome del canale. Per molti canali non corrisponde
all'handle reale: "@TheFamTime" su YouTube porta a un canale con 2 iscritti,
non a quello da 252K che abbiamo misurato; "@MCTALKETCOMEDY" non esiste,
l'handle vero e' "@mctalketcomedy2463". In tabella non c'era nessun
identificatore stabile del canale.

Cosa fa
-------
1. videos.list sui video dei record senza channel_id  -> channelId (1 unita'/50)
2. channels.list sui canali cosi' trovati             -> customUrl (1 unita'/50)
3. update di channel_id, channel_handle e - se richiesto - author_handle

Costo tipico sull'attuale tabella: ~260 + ~180 = ~440 unita' di quota,
su un budget giornaliero di 10.000.

Uso
---
    python backfill_channel_ids.py --stato
    python backfill_channel_ids.py --dry-run
    python backfill_channel_ids.py --budget 2000
    python backfill_channel_ids.py --non-riscrivere-handle

Principio fail-safe: un errore di rete o una risposta non 200 fanno saltare
il blocco, mai azzerare un valore gia' presente.
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

from log_iosa import configura, prendi

log = prendi(__name__)

load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
# La chiave anon ha solo la policy di lettura su posts: un UPDATE con quella
# chiave non fallisce, semplicemente non tocca nessuna riga (PostgREST risponde
# 200 con zero righe). Serve la service_role, altrimenti lo script direbbe di
# aver scritto senza aver scritto niente.
SUPABASE_KEY = (
    os.getenv("SUPABASE_SERVICE_KEY")
    or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or os.getenv("SUPABASE_KEY")
)

BLOCCO = 50
PAGINA = 1000


def _ruolo(chiave: str) -> str:
    """Supabase ha due formati: il vecchio JWT e le nuove chiavi sb_publishable_/sb_secret_."""
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
    ruolo = _ruolo(SUPABASE_KEY)
    if serve_scrittura and ruolo != "service_role":
        sys.exit(
            f"La chiave configurata ha ruolo '{ruolo}'. Su posts esiste solo la policy\n"
            "di lettura pubblica: un UPDATE con questa chiave non scrive nulla e non\n"
            "segnala errore. Aggiungi SUPABASE_SERVICE_KEY=<service_role> a backend/.env\n"
            "e rilancia: quanto gia' risolto e' salvato, non serve altra quota YouTube."
        )
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def leggi_da_sistemare(sb, solo_attivi: bool):
    """Tutti i record senza channel_id, impaginati: select() si ferma a 1000."""
    righe, da = [], 0
    while True:
        q = (
            sb.table("posts")
            .select("id, external_post_id, author_handle, status")
            .is_("channel_id", "null")
            .eq("platform", "YOUTUBE")
        )
        if solo_attivi:
            q = q.eq("status", "ACTIVE")
        blocco = q.range(da, da + PAGINA - 1).execute().data or []
        righe.extend(blocco)
        if len(blocco) < PAGINA:
            return righe
        da += PAGINA


def canali_dei_video(video_ids: list, contatore: dict) -> dict:
    """{video_id: channel_id} — 1 unita' di quota ogni 50 video."""
    out = {}
    for i in range(0, len(video_ids), BLOCCO):
        blocco = video_ids[i:i + BLOCCO]
        url = (
            "https://www.googleapis.com/youtube/v3/videos"
            f"?part=snippet&id={','.join(blocco)}&key={YOUTUBE_API_KEY}"
        )
        try:
            r = requests.get(url, timeout=15)
        except Exception as exc:
            log.warning(f"  [videos] rete: {exc} — blocco saltato")
            continue
        contatore["quota"] += 1
        if r.status_code != 200:
            log.warning(f"  [videos] HTTP {r.status_code} — blocco saltato")
            continue
        for item in r.json().get("items", []):
            ch = item.get("snippet", {}).get("channelId")
            if ch:
                out[item["id"]] = ch
        time.sleep(0.05)
    return out


def handle_dei_canali(channel_ids: list, contatore: dict) -> dict:
    """{channel_id: handle} — handle assente se il canale non ne espone uno."""
    out = {}
    unici = sorted(set(channel_ids))
    for i in range(0, len(unici), BLOCCO):
        blocco = unici[i:i + BLOCCO]
        url = (
            "https://www.googleapis.com/youtube/v3/channels"
            f"?part=snippet&id={','.join(blocco)}&key={YOUTUBE_API_KEY}"
        )
        try:
            r = requests.get(url, timeout=15)
        except Exception as exc:
            log.warning(f"  [channels] rete: {exc} — blocco saltato")
            continue
        contatore["quota"] += 1
        if r.status_code != 200:
            log.warning(f"  [channels] HTTP {r.status_code} — blocco saltato")
            continue
        for item in r.json().get("items", []):
            h = (item.get("snippet", {}).get("customUrl") or "").strip()
            out[item["id"]] = h if h.startswith("@") else None
        time.sleep(0.05)
    return out


STATO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backfill_channel_ids.json")


def carica_stato() -> dict:
    if os.path.exists(STATO):
        with io.open(STATO, encoding="utf-8") as f:
            return json.load(f)
    return {"risolti": {}, "quota": 0}


def salva_stato(st: dict) -> None:
    with io.open(STATO, "w", encoding="utf-8") as f:
        json.dump(st, f)


def sql_update(risolti: dict, riscrivi_handle: bool) -> str:
    """Un solo UPDATE ... FROM (VALUES ...): 12.000 update singoli sarebbero minuti."""
    def q(v):
        return "null" if v is None else "'" + str(v).replace("'", "''") + "'"

    valori = ",\n".join(
        f"({q(vid)},{q(dati[0])},{q(dati[1])})" for vid, dati in risolti.items()
    )
    set_handle = (
        "\n      author_handle = coalesce(v.handle, posts.author_handle),"
        if riscrivi_handle else ""
    )
    return (
        "update posts set\n"
        "      channel_id = v.ch,\n"
        "      channel_handle = v.handle" + ("," if set_handle else "") + set_handle.rstrip(",") + "\n"
        "from (values\n" + valori + "\n) as v(vid, ch, handle)\n"
        "where posts.external_post_id = v.vid and posts.platform = 'YOUTUBE';"
    )


def applica(sb, st: dict, riscrivi_handle: bool, secondi: int, parallelo: int) -> None:
    """Scrive gli identificatori risolti. Ripartibile: lo stato ricorda cosa e' gia' andato."""
    fatti = set(st.setdefault("applicati", []))
    da_scrivere = [(v, d) for v, d in st["risolti"].items() if v not in fatti]
    log.info(f"Da scrivere: {len(da_scrivere)} (gia' scritti: {len(fatti)})")
    if not da_scrivere:
        return

    scadenza = time.time() + secondi
    esito = {"ok": 0, "handle": 0, "ko": 0}

    def scrivi(coppia):
        vid, (ch, handle) = coppia
        if time.time() > scadenza:
            return None
        campi = {"channel_id": ch, "channel_handle": handle}
        if handle and riscrivi_handle:
            campi["author_handle"] = handle
        try:
            sb.table("posts").update(campi).eq("external_post_id", vid).eq("platform", "YOUTUBE").execute()
        except Exception as exc:
            esito["ko"] += 1
            if esito["ko"] < 4:
                log.error(f"  update fallito su {vid}: {exc}")
            return None
        esito["ok"] += 1
        if handle and riscrivi_handle:
            esito["handle"] += 1
        return vid

    with ThreadPoolExecutor(max_workers=parallelo) as pool:
        for vid in pool.map(scrivi, da_scrivere):
            if vid:
                fatti.add(vid)

    st["applicati"] = sorted(fatti)
    salva_stato(st)
    log.info(f"Scritti: {esito['ok']} — handle corretti: {esito['handle']} — errori: {esito['ko']}")
    rimasti = len(st["risolti"]) - len(fatti)
    if rimasti:
        log.info(f"Ne restano {rimasti}: rilancia --applica.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stato", action="store_true", help="Quanti record mancano e quanti ne ho gia' risolti.")
    ap.add_argument("--budget", type=int, default=120, help="Tetto di unita' di quota per questa esecuzione.")
    ap.add_argument("--secondi", type=int, default=95, help="Tempo massimo, per stare sotto il limite della shell.")
    ap.add_argument("--tutti-gli-stati", action="store_true", help="Anche i record EXPIRED/INACTIVE.")
    ap.add_argument("--non-riscrivere-handle", action="store_true",
                    help="Salva channel_id/channel_handle ma lascia author_handle com'e'.")
    ap.add_argument("--sql", metavar="FILE", help="Scrive l'UPDATE con quanto risolto finora e termina.")
    ap.add_argument("--azzera", action="store_true", help="Cancella lo stato accumulato e riparte da zero.")
    ap.add_argument("--applica", action="store_true",
                    help="Scrive sul database quanto risolto. Ripartibile: salta cio' che ha gia' scritto.")
    ap.add_argument("--parallelo", type=int, default=16, help="Update in parallelo (default 16).")
    args = ap.parse_args()

    if args.azzera and os.path.exists(STATO):
        os.remove(STATO)
        log.info("Stato azzerato.")

    st = carica_stato()

    if args.sql:
        if not st["risolti"]:
            sys.exit("Niente da scrivere: lo stato e' vuoto.")
        with io.open(args.sql, "w", encoding="utf-8") as f:
            f.write(sql_update(st["risolti"], not args.non_riscrivere_handle))
        log.info(f"{len(st['risolti'])} record -> {args.sql}")
        return

    sb = _client(serve_scrittura=args.applica)

    if args.applica:
        applica(sb, st, riscrivi_handle=not args.non_riscrivere_handle,
                secondi=args.secondi, parallelo=args.parallelo)
        return

    righe = leggi_da_sistemare(sb, solo_attivi=not args.tutti_gli_stati)
    da_fare = [r for r in righe
               if r.get("external_post_id") and r["external_post_id"] not in st["risolti"]]

    log.info(f"Senza channel_id: {len(righe)} — gia' risolti in locale: {len(st['risolti'])} "
          f"— ancora da risolvere: {len(da_fare)}")
    if args.stato or not da_fare:
        return

    scadenza = time.time() + args.secondi
    contatore = {"quota": 0}
    video_ids = [r["external_post_id"] for r in da_fare]

    for i in range(0, len(video_ids), BLOCCO):
        if time.time() > scadenza or contatore["quota"] + 2 > args.budget:
            break
        blocco = video_ids[i:i + BLOCCO]
        v2c = canali_dei_video(blocco, contatore)
        if not v2c:
            continue
        c2h = handle_dei_canali(list(v2c.values()), contatore)
        for vid, ch in v2c.items():
            st["risolti"][vid] = [ch, c2h.get(ch)]
        salva_stato(st)

    st["quota"] += contatore["quota"]
    salva_stato(st)
    log.warning(f"Quota di questa esecuzione: {contatore['quota']} — totale: {st['quota']}")
    log.info(f"Risolti finora: {len(st['risolti'])} / {len(righe)}")
    if len(st["risolti"]) < len(righe):
        log.info("Rilancia lo stesso comando per continuare, poi --sql per generare l'UPDATE.")


if __name__ == "__main__":
    configura()
    main()
