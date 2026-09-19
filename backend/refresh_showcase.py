"""
Riallinea i record gia' in tabella alle regole correnti del VPI.

Il motore di ingestione fa solo insert: non torna mai sulle righe che ha
scritto. Quando cambiano le regole della baseline, i record piu' vecchi
restano com'erano fino a scadenza naturale della finestra di 15 giorni.

Ricalcolare tutto costa troppa quota per un progetto a budget zero, quindi
questo script riallinea solo la vetrina: i record con VPI alto, cioe' quelli
che finiscono in cima alla classifica e che quindi la gente vede davvero.

Per ogni canale coinvolto scarica una sola volta i suoi Short (3 unita' di
quota) e da quella lista ricalcola la baseline di tutti i suoi record,
escludendo di volta in volta il video misurato. Aggiorna anche gli iscritti,
che il motore vecchio riempiva con una sentinella.

E' ripartibile: ogni giro salva su file quello che ha raccolto e riprende da
dove si era fermato, cosi' si puo' spezzare in sessioni brevi senza rifare
(e ripagare) il lavoro gia' fatto.

Nulla viene mai cancellato: un record la cui baseline scende sotto la soglia
minima passa a INACTIVE, come gia' avviene nel ciclo di vita normale. Se una
chiamata all'API fallisce il canale resta fuori dal file di stato e verra'
ritentato al giro dopo: meglio un dato vecchio che un dato inventato.

Uso tipico:
    python refresh_showcase.py                 # raccoglie per ~140 secondi e si ferma
    python refresh_showcase.py                 # ... si rilancia finche' non manca piu' nulla
    python refresh_showcase.py --sql           # dallo stato raccolto scrive l'SQL
"""

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import vpi_engine as motore
from vpi_core import (
    MIN_BASELINE_VIEWS,
    baseline_from_samples,
    calculate_vpi_ratio,
    get_vpi_metadata,
    round_vpi,
)

COSTO_VIDEOS_LIST = 1      # una chiamata ogni 50 video
COSTO_CANALE = 3           # channels + playlistItems + videos
COSTO_SUBSCRIBERS = 1      # una chiamata ogni 50 canali

CUTOVER_DEFAULT = "2026-09-19T06:00:00+00:00"


def apostrofa(valore) -> str:
    """Letterale SQL: stringhe con apice raddoppiato, None come NULL."""
    if valore is None:
        return "NULL"
    if isinstance(valore, (int, float)):
        return repr(valore)
    return "'" + str(valore).replace("'", "''") + "'"


def carica_stato(percorso):
    if os.path.exists(percorso):
        with open(percorso, encoding="utf-8") as f:
            return json.load(f)
    return {"video_canale": {}, "canali": {}, "quota": 0}


def salva_stato(percorso, stato):
    tmp = percorso + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(stato, f)
    os.replace(tmp, percorso)


def leggi_candidati(min_vpi: float, prima_di: str):
    """Record attivi, scritti dal motore vecchio, con VPI sopra la soglia."""
    righe, passo, inizio = [], 1000, 0
    while True:
        res = (
            motore.supabase.table("posts")
            .select("id,external_post_id,engagement_score,baseline_score,vpi_ratio,author_handle,detected_at")
            .eq("status", "ACTIVE")
            .lt("detected_at", prima_di)
            .gte("vpi_ratio", min_vpi)
            .range(inizio, inizio + passo - 1)
            .execute()
        )
        blocco = res.data or []
        righe.extend(blocco)
        if len(blocco) < passo:
            break
        inizio += passo
    return righe


def mappa_video_canale(video_ids, stato):
    """video_id -> channel_id, 1 unita' di quota ogni 50 video. Risultato in cache."""
    mancanti = [v for v in video_ids if v not in stato["video_canale"]]
    for i in range(0, len(mancanti), 50):
        blocco = mancanti[i:i + 50]
        url = (
            "https://www.googleapis.com/youtube/v3/videos"
            f"?part=snippet&id={','.join(blocco)}&key={motore.YOUTUBE_API_KEY}"
        )
        stato["quota"] += COSTO_VIDEOS_LIST
        try:
            res = motore.requests.get(url, timeout=15)
            if res.status_code != 200:
                print(f"  videos.list ha risposto {res.status_code} su un blocco di {len(blocco)}")
                continue
        except Exception as exc:
            print(f"  videos.list non raggiungibile: {exc}")
            continue
        visti = set()
        for item in res.json().get("items", []):
            ch = item.get("snippet", {}).get("channelId")
            if ch:
                stato["video_canale"][item["id"]] = ch
                visti.add(item["id"])
        # I video spariti da YouTube si marcano, per non richiederli ogni giro.
        for v in blocco:
            if v not in visti:
                stato["video_canale"].setdefault(v, None)
    return stato["video_canale"]


def raccogli(args, stato, righe):
    video_ids = sorted({r["external_post_id"] for r in righe if r.get("external_post_id")})
    mappa = mappa_video_canale(video_ids, stato)
    vivi = sum(1 for v in video_ids if mappa.get(v))
    print(f"Video ancora esistenti: {vivi} su {len(video_ids)}")

    canali = sorted({mappa[v] for v in video_ids if mappa.get(v)})
    da_fare = [c for c in canali if c not in stato["canali"]]
    print(f"Canali totali: {len(canali)}   gia' raccolti: {len(canali) - len(da_fare)}   da fare: {len(da_fare)}")
    if not da_fare:
        return 0

    # Gli iscritti costano 1 unita' ogni 50 canali: si prendono in blocco.
    senza_subs = [c for c in da_fare if c not in stato.get("subscribers", {})]
    if senza_subs:
        stato.setdefault("subscribers", {})
        blocco = senza_subs[:600]
        meta = motore.fetch_channels_metadata(blocco)
        stato["quota"] += ((len(blocco) + 49) // 50) * COSTO_SUBSCRIBERS
        for c in blocco:
            stato["subscribers"][c] = meta.get(c, {}).get("subscribers")
        noti = sum(1 for c in blocco if stato["subscribers"].get(c) is not None)
        print(f"Iscritti: recuperati {noti} su {len(blocco)} canali")

    # Ogni canale sono tre chiamate in fila, quindi il collo di bottiglia e'
    # la latenza, non la quota: si lavora a piccoli gruppi in parallelo.
    scadenza = time.time() + args.secondi
    fatti, falliti = 0, 0
    with ThreadPoolExecutor(max_workers=args.parallelo) as pool:
        for i in range(0, len(da_fare), args.parallelo):
            if time.time() > scadenza:
                break
            gruppo = da_fare[i:i + args.parallelo]
            if stato["quota"] + COSTO_CANALE * len(gruppo) > args.budget:
                print(f"Budget quota esaurito a {stato['quota']} unita'.")
                break
            risultati = list(pool.map(motore.get_channel_short_samples, gruppo))
            stato["quota"] += COSTO_CANALE * len(gruppo)
            for ch_id, campioni in zip(gruppo, risultati):
                if campioni is None:
                    falliti += 1      # non si salva: si ritenta al giro dopo
                    continue
                stato["canali"][ch_id] = campioni
                fatti += 1
            if fatti and fatti % 24 < args.parallelo:
                salva_stato(args.stato, stato)

    salva_stato(args.stato, stato)
    restanti = len([c for c in canali if c not in stato["canali"]])
    print(f"Raccolti ora: {fatti}   falliti (ritentabili): {falliti}   ancora da fare: {restanti}")
    print(f"Quota spesa in totale: {stato['quota']} unita'")
    return restanti


def giorni_da_rilevamento(valore, adesso):
    """Quanti giorni sono passati dalla rilevazione del record."""
    if not valore:
        return 0.0
    try:
        istante = datetime.fromisoformat(str(valore).replace("Z", "+00:00"))
    except ValueError:
        return 0.0
    if istante.tzinfo is None:
        istante = istante.replace(tzinfo=timezone.utc)
    return max(0.0, (adesso - istante).total_seconds() / 86400.0)


def costruisci_aggiornamenti(stato, righe):
    mappa = stato["video_canale"]
    subs = stato.get("subscribers", {})
    adesso = datetime.now(timezone.utc)
    aggiornamenti = []
    senza_canale, senza_campioni, senza_baseline = 0, 0, 0

    for r in righe:
        ch_id = mappa.get(r.get("external_post_id"))
        if not ch_id:
            senza_canale += 1
            continue
        campioni = stato["canali"].get(ch_id)
        if campioni is None:
            senza_campioni += 1
            continue

        # La baseline va riportata al momento in cui il record e' stato
        # rilevato: i Short pubblicati dopo non c'erano e non devono entrare.
        indietro = giorni_da_rilevamento(r.get("detected_at"), adesso)
        baseline, n_camp = baseline_from_samples(
            campioni, exclude_video_id=r.get("external_post_id"), giorni_indietro=indietro
        )
        if not baseline or baseline <= 0:
            senza_baseline += 1
            continue

        views = float(r.get("engagement_score") or 0)
        vpi = calculate_vpi_ratio(views, baseline)
        livello, nome_livello, colore = get_vpi_metadata(vpi)

        aggiornamenti.append({
            "id": r["id"],
            "handle": r.get("author_handle"),
            "baseline_vecchia": float(r.get("baseline_score") or 0),
            "baseline_nuova": round(baseline, 1),
            "vpi_vecchio": float(r.get("vpi_ratio") or 0),
            "vpi_nuovo": round_vpi(vpi),
            "vpi_level": livello,
            "vpi_level_name": nome_livello,
            "vpi_color": colore,
            "subscribers": subs.get(ch_id),
            "status": "ACTIVE" if baseline >= MIN_BASELINE_VIEWS else "INACTIVE",
            "campioni": n_camp,
            "giorni_indietro": round(indietro, 1),
        })

    return aggiornamenti, senza_canale, senza_campioni, senza_baseline


def scrivi_sql(percorso, aggiornamenti):
    with open(percorso, "w", encoding="utf-8") as f:
        for i in range(0, len(aggiornamenti), 300):
            blocco = aggiornamenti[i:i + 300]
            valori = ",\n  ".join(
                "({}, {}, {}, {}, {}, {}, {}, {})".format(
                    apostrofa(a["id"]), a["baseline_nuova"], a["vpi_nuovo"], a["vpi_level"],
                    apostrofa(a["vpi_level_name"]), apostrofa(a["vpi_color"]),
                    apostrofa(a["subscribers"]), apostrofa(a["status"]),
                )
                for a in blocco
            )
            f.write(
                "update posts p set\n"
                "  baseline_score = v.baseline,\n"
                "  vpi_ratio      = v.vpi,\n"
                "  vpi_level      = v.livello,\n"
                "  vpi_level_name = v.nome,\n"
                "  vpi_color      = v.colore,\n"
                "  subscribers    = v.iscritti,\n"
                "  status         = v.stato\n"
                "from (values\n  " + valori + "\n"
                ") as v(id, baseline, vpi, livello, nome, colore, iscritti, stato)\n"
                "where p.id = v.id::uuid;\n\n"
            )


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--min-vpi", type=float, default=100.0,
                    help="ricalcola i record con VPI almeno pari a questo (default 100)")
    ap.add_argument("--prima-di", default=CUTOVER_DEFAULT,
                    help="considera solo i record rilevati prima di questo istante ISO")
    ap.add_argument("--budget", type=int, default=5000,
                    help="tetto complessivo di unita' di quota YouTube (default 5000)")
    ap.add_argument("--secondi", type=int, default=140,
                    help="quanto puo' durare un singolo giro di raccolta (default 140)")
    ap.add_argument("--parallelo", type=int, default=6,
                    help="quanti canali interrogare insieme (default 6)")
    ap.add_argument("--stato", default="/tmp/vetrina_stato.json",
                    help="file dove si accumula quello che e' stato raccolto")
    ap.add_argument("--sql", action="store_true",
                    help="non chiama l'API: costruisce l'SQL da quanto gia' raccolto")
    ap.add_argument("--out", default="/tmp/vetrina.sql", help="file SQL di uscita")
    args = ap.parse_args()

    stato = carica_stato(args.stato)
    righe = leggi_candidati(args.min_vpi, args.prima_di)
    print(f"Soglia VPI {args.min_vpi}, rilevati prima di {args.prima_di}: {len(righe)} record candidati",
          flush=True)
    if not righe:
        return 0

    if not args.sql:
        restanti = raccogli(args, stato, righe)
        if restanti:
            print(f"\nNon ho finito: rilancia lo stesso comando ({restanti} canali mancanti).", flush=True)
            return 0
        print("\nRaccolta completa. Rilancia con --sql per generare l'aggiornamento.", flush=True)
        return 0

    aggiornamenti, senza_canale, senza_campioni, senza_baseline = costruisci_aggiornamenti(stato, righe)
    disattivati = sum(1 for a in aggiornamenti if a["status"] == "INACTIVE")

    print()
    print(f"Record ricalcolati:                  {len(aggiornamenti)}")
    print(f"Saltati (video non piu' su YouTube): {senza_canale}")
    print(f"Saltati (canale non raccolto):       {senza_campioni}")
    print(f"Saltati (campioni insufficienti):    {senza_baseline}")
    print(f"Che passano a INACTIVE:              {disattivati}")
    print(f"Quota spesa in totale:               {stato['quota']} unita'")

    if aggiornamenti:
        scarti = sorted(aggiornamenti, key=lambda a: abs(a["vpi_nuovo"] - a["vpi_vecchio"]), reverse=True)
        print("\nScostamenti maggiori:")
        for a in scarti[:15]:
            print(f"  {str(a['handle'])[:26]:<26} baseline {a['baseline_vecchia']:>10.1f} -> {a['baseline_nuova']:>10.1f}"
                  f"   VPI {a['vpi_vecchio']:>9.1f} -> {a['vpi_nuovo']:>8.1f}  [{a['status']}]")

        with open(args.out + ".json", "w", encoding="utf-8") as f:
            json.dump(aggiornamenti, f, indent=1, ensure_ascii=False)
        scrivi_sql(args.out, aggiornamenti)
        print(f"\nSQL in {args.out}, dettaglio in {args.out}.json")

    return 0


if __name__ == "__main__":
    sys.exit(main())
