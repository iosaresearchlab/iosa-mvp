"""Il motore di ingestione come processo a se' stante.

Perche' esiste: il motore girava dentro il servizio web FastAPI, e il piano
gratuito di Render spegne il servizio dopo un quarto d'ora senza richieste
HTTP. Con il servizio moriva lo scheduler, e l'indice restava fermo per ore
ogni notte. Un lavoro periodico non puo' dipendere da qualcuno che visita il
sito.

Due modi d'uso:

    python run_engine.py              # resta acceso e cicla, per un worker
    python run_engine.py --un-ciclo   # un giro solo ed esce, per un cron

Il primo vuole un processo sempre attivo (Render Background Worker, una VM,
il tuo computer). Il secondo non vuole niente di acceso: lo chiama un cron
esterno, e va bene anche GitHub Actions.
"""
import argparse
import signal
import sys
import time

from log_iosa import configura, prendi
from vpi_engine import INGEST_INTERVAL_MINUTES, esegui_un_ciclo

log = prendi(__name__)

_fermati = False


def _chiudi(signum, _frame):
    """Alla prossima pausa esce pulito invece di morire a meta' ciclo."""
    global _fermati
    _fermati = True
    log.info("ricevuto segnale %s: chiudo dopo il ciclo in corso.", signum)


def ciclo_continuo(minuti: int) -> int:
    signal.signal(signal.SIGTERM, _chiudi)
    signal.signal(signal.SIGINT, _chiudi)
    log.info("motore avviato come processo dedicato, un giro ogni %d minuti.", minuti)

    while not _fermati:
        inizio = time.monotonic()
        esiti = esegui_un_ciclo()
        log.info("ciclo concluso: %s", esiti)

        # Il tempo del ciclo si scala dall'attesa, cosi' il passo resta
        # regolare anche quando un giro e' lento.
        resto = max(0.0, minuti * 60 - (time.monotonic() - inizio))
        while resto > 0 and not _fermati:
            pausa = min(5.0, resto)
            time.sleep(pausa)
            resto -= pausa

    log.info("motore fermato.")
    return 0


def un_ciclo() -> int:
    esiti = esegui_un_ciclo()
    log.info("ciclo singolo concluso: %s", esiti)
    # Esce diverso da zero se ogni passo e' fallito: cosi' il cron esterno
    # se ne accorge invece di segnare verde su un giro andato a vuoto.
    return 0 if any(v == "ok" for v in esiti.values()) else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--un-ciclo", action="store_true",
                    help="esegue un solo giro ed esce (per un cron esterno)")
    ap.add_argument("--minuti", type=int, default=INGEST_INTERVAL_MINUTES,
                    help="minuti tra un giro e l'altro nel ciclo continuo")
    a = ap.parse_args()

    configura()
    return un_ciclo() if a.un_ciclo else ciclo_continuo(a.minuti)


if __name__ == "__main__":
    sys.exit(main())
