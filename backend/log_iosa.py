"""Logging del backend IOSA.

Il motore gira ogni 20 minuti, tutto il giorno. Finche' scriveva con print()
i suoi messaggi non finivano da nessuna parte: nessun orario, nessuna
gravita', niente da cercare. Se l'ingestione si fermava lunedi' e te ne
accorgevi giovedi', di lunedi' non restava niente.

Qui i messaggi vanno sia a schermo sia in logs/iosa.log, che ruota a 5 MB e
tiene le ultime cinque copie: circa un mese di esecuzione continua.

    from log_iosa import configura, prendi
    configura()                       # una volta sola, all'avvio
    log = prendi(__name__)            # in ogni modulo
    log.info("...")                   # andamento normale
    log.warning("...")                # va avanti ma qualcosa non torna
    log.error("...")                  # un pezzo non e' riuscito
"""
import logging
import logging.handlers
import os
import sys
from pathlib import Path

CARTELLA_LOG = Path(__file__).resolve().parent / "logs"
FILE_LOG = CARTELLA_LOG / "iosa.log"
BYTE_PER_FILE = 5 * 1024 * 1024
COPIE = 5

_configurato = False


def configura(livello: str = None) -> None:
    """Prepara il logger radice. Chiamarla una volta, all'avvio del processo.

    Il livello si puo' alzare o abbassare senza toccare il codice, con
    IOSA_LOG_LEVEL nell'ambiente (DEBUG, INFO, WARNING, ERROR).
    """
    global _configurato
    if _configurato:
        return

    scelto = (livello or os.getenv("IOSA_LOG_LEVEL") or "INFO").upper()
    radice = logging.getLogger()
    radice.setLevel(getattr(logging, scelto, logging.INFO))

    formato = logging.Formatter(
        "%(asctime)s %(levelname)-7s %(name)-18s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    a_schermo = logging.StreamHandler(sys.stdout)
    a_schermo.setFormatter(formato)
    radice.addHandler(a_schermo)

    # Se la cartella non e' scrivibile (contenitore in sola lettura, permessi)
    # il processo deve comunque partire: il log a schermo resta.
    try:
        CARTELLA_LOG.mkdir(exist_ok=True)
        su_file = logging.handlers.RotatingFileHandler(
            FILE_LOG, maxBytes=BYTE_PER_FILE, backupCount=COPIE, encoding="utf-8"
        )
        su_file.setFormatter(formato)
        radice.addHandler(su_file)
    except OSError as e:
        radice.warning("log su file non attivo (%s): resta solo lo schermo", e)

    # APScheduler e urllib3 sono chiacchieroni a INFO e non dicono niente
    # di utile su cosa sta facendo l'indice.
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    _configurato = True


def prendi(nome: str) -> logging.Logger:
    """Logger di un modulo. Accorcia __main__ e i nomi con il punto."""
    if nome in ("__main__", None):
        nome = "iosa"
    return logging.getLogger(nome.rsplit(".", 1)[-1])
