"""Archivio permanente delle targhe renderizzate, su Supabase Storage.

Perche': la cache delle anteprime era un file dentro RENDERS_DIR con
scadenza di 24 ore. Su Render il filesystem e' effimero e il servizio si
riavvia di continuo, quindi quella cache era quasi sempre vuota e ogni
creator che apriva la propria pagina aspettava dodici-venti secondi mentre
Playwright apriva Chromium e impaginava la targa da zero.

Su Storage la targa sopravvive ai riavvii, e il browser la prende dal CDN
senza passare dal backend.

Il bucket 'targhe' e' pubblico in lettura: la targa e' gia' pubblica per
definizione (sta nella pagina di misurazione, che e' aperta a chiunque abbia
il link) e servirla dal CDN e' il punto dell'esercizio. La scrittura richiede
la chiave service_role.
"""
import os
from pathlib import Path
from typing import Optional

import requests

from log_iosa import prendi

log = prendi(__name__)

BUCKET = "targhe"
# Gli stessi nomi che usa main.py: su Render l'indirizzo del database e'
# arrivato dal frontend e si chiama NEXT_PUBLIC_SUPABASE_URL. Leggere solo
# SUPABASE_URL lasciava l'archivio spento senza dirlo a nessuno.
SUPABASE_URL = (os.getenv("NEXT_PUBLIC_SUPABASE_URL")
                or os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
SERVICE_KEY = (os.getenv("SUPABASE_SERVICE_KEY")
               or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()

# Il backend non deve restare appeso al CDN: se Storage non risponde in fretta
# si rende la targa come prima, che e' lento ma funziona.
TIMEOUT = 8


def attivo() -> bool:
    return bool(SUPABASE_URL and SERVICE_KEY)


def url_pubblico(nome: str) -> str:
    return f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{nome}"


def esiste(nome: str) -> bool:
    """Vero se la targa e' gia' in archivio. Una HEAD sul CDN, non una lista."""
    if not attivo():
        return False
    try:
        r = requests.head(url_pubblico(nome), timeout=TIMEOUT)
        return r.status_code == 200
    except requests.RequestException as e:
        log.warning("archivio targhe non raggiungibile (%s): si rende al volo", e)
        return False


def carica(nome: str, percorso: Path) -> Optional[str]:
    """Mette la targa in archivio e restituisce l'URL pubblico.

    Un caricamento fallito non e' un errore fatale: la targa e' gia' stata
    resa e puo' essere servita dal file locale. Si ritentera' alla prossima
    richiesta.
    """
    if not attivo():
        return None
    try:
        with open(percorso, "rb") as f:
            r = requests.post(
                f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{nome}?upsert=true",
                headers={"apikey": SERVICE_KEY,
                         "Authorization": f"Bearer {SERVICE_KEY}",
                         "Content-Type": "image/png"},
                data=f.read(), timeout=30,
            )
        if r.status_code in (200, 201):
            log.info("targa %s archiviata", nome)
            return url_pubblico(nome)
        log.warning("archiviazione di %s non riuscita (%s): %s",
                    nome, r.status_code, r.text[:200])
    except (requests.RequestException, OSError) as e:
        log.warning("archiviazione di %s non riuscita: %s", nome, e)
    return None
