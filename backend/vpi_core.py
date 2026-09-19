"""
Nucleo condiviso del calcolo VPI.

Unica fonte di verita' per formula, soglie, colori, durata degli Short e
ciclo di vita dei record. Importato da vpi_engine.py e da qualunque script
di manutenzione, cosi' che due percorsi non possano piu' calcolare due VPI
diversi per lo stesso video.
"""

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------- costanti

SHORT_MAX_SECONDS = 180          # durata massima di uno Short
CAMPAIGN_DAYS = 15               # finestra di visibilita' di un record
BASELINE_MAX_AGE_DAYS = 90       # quanto indietro guardare per la baseline
BASELINE_MIN_AGE_DAYS = 14       # eta' minima perche' un video sia "maturo"
MIN_BASELINE_SAMPLES = 5         # sotto questa soglia la mediana non e' affidabile

# Soglia minima di visualizzazioni della baseline.
#
# Il VPI e' un rapporto: quando il denominatore e' piccolo il risultato non
# misura piu' nulla. La mediana di un gruppo di Short e' un intero (o un .5),
# quindi la sua granularita' relativa e' 0.5/baseline: a 500 vale lo 0.1%,
# sotto le 100 visualizzazioni supera lo 0.5% e una singola view in piu' o in
# meno sposta il VPI di percentuali intere, mentre il prodotto lo dichiara con
# una cifra decimale.
#
# Il dato lo conferma: sui record storici il VPI mediano per fascia di
# baseline va da 6.103x (baseline < 100) a 3.7x (baseline > 100K), cioe'
# scala come 1/baseline invece di restare costante come dovrebbe fare una
# normalizzazione. Sotto le 300 visualizzazioni di baseline il 100% dei
# record finisce al livello 10, quindi la scala non distingue piu' niente.
#
# 500 non taglia i piccoli creator: i record sotto quella soglia sono tutti
# canali di news ad altissima frequenza di pubblicazione (@GMANews,
# @Tribunnews, @KOMPASTV, @NewYorkPost...) la cui mediana e' depressa dal
# volume, non canali con pochi iscritti.
MIN_BASELINE_VIEWS = 500
MIN_VPI_FOR_INGESTION = 1.0      # sotto o uguale non e' un outlier

# Scala a 10 livelli: (soglia minima, livello, nome, colore)
VPI_SCALE = (
    (50.0, 10, "Lvl 10 - Hyper Outlier", "#FF0055"),
    (25.0, 9, "Lvl 9 - Mega Outlier", "#FF2A00"),
    (15.0, 8, "Lvl 8 - Outlier", "#FF5500"),
    (10.0, 7, "Lvl 7 - Super Viral", "#FF8800"),
    (7.5, 6, "Lvl 6 - Viral", "#FFAA00"),
    (5.0, 5, "Lvl 5 - Breakout", "#FFCC00"),
    (3.0, 4, "Lvl 4 - Trending", "#00CC88"),
    (2.0, 3, "Lvl 3 - Rising", "#0099FF"),
    (1.5, 2, "Lvl 2 - Moderate", "#7755FF"),
    (0.0, 1, "Lvl 1 - Standard", "#888888"),
)

_ISO_DURATION = re.compile(r'P(?:(\d+)D)?T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?')


# ---------------------------------------------------------------- funzioni

def parse_iso_duration(duration_str: str) -> int:
    """Converte una durata ISO 8601 (PT1M15S) in secondi totali."""
    if not duration_str:
        return 0
    match = _ISO_DURATION.match(duration_str)
    if not match:
        return 0
    days, hours, minutes, seconds = (int(g or 0) for g in match.groups())
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def is_short_duration(duration_seconds: int) -> bool:
    """Vero se la durata rientra nel formato short."""
    return 0 < duration_seconds <= SHORT_MAX_SECONDS


def calculate_vpi_ratio(views, baseline) -> float:
    """
    VPI = views del video / mediana della baseline del canale.

    Nessun arrotondamento qui: il livello va assegnato sul valore pieno,
    altrimenti un 1.449 arrotondato a 1.4 cambia livello.
    """
    try:
        views = float(views or 0)
        baseline = float(baseline or 0)
    except (TypeError, ValueError):
        return 1.0
    if baseline <= 0:
        return 1.0
    return views / baseline


def get_vpi_metadata(vpi_ratio: float):
    """Restituisce (livello, nome, colore) per un VPI ratio."""
    try:
        value = float(vpi_ratio)
    except (TypeError, ValueError):
        value = 0.0
    for threshold, level, name, color in VPI_SCALE:
        if value >= threshold:
            return level, name, color
    return 1, "Lvl 1 - Standard", "#888888"


def age_in_days(published_at, now=None):
    """Eta' in giorni di una data ISO 8601. None se assente o illeggibile."""
    if not published_at:
        return None
    try:
        published = datetime.fromisoformat(str(published_at).replace("Z", "+00:00"))
    except ValueError:
        return None
    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)
    now = now or datetime.now(timezone.utc)
    return (now - published).total_seconds() / 86400.0


def round_vpi(vpi_ratio: float) -> float:
    """Valore da mostrare e da salvare, arrotondato dopo l'assegnazione del livello."""
    try:
        return round(float(vpi_ratio), 1)
    except (TypeError, ValueError):
        return 1.0


# ------------------------------------------------------------- cache su file
# Evita di ricomputare baseline e verifiche Short a ogni ciclo: a budget zero
# la quota API e' la risorsa piu' scarsa del progetto.

_CACHE_DIR = Path(__file__).resolve().parent / ".cache"


class TTLCache:
    """Cache chiave/valore persistente su file JSON, con scadenza per voce."""

    def __init__(self, name: str, ttl_seconds: int):
        self.path = _CACHE_DIR / f"{name}.json"
        self.ttl = ttl_seconds
        self._data = {}
        self._load()

    def _load(self):
        try:
            if self.path.exists():
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            self._data = {}

    def save(self):
        try:
            _CACHE_DIR.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self._data), encoding="utf-8")
        except Exception:
            pass

    def get(self, key, default=None):
        entry = self._data.get(str(key))
        if not entry:
            return default
        value, stored_at = entry
        if (time.time() - stored_at) > self.ttl:
            self._data.pop(str(key), None)
            return default
        return value

    def set(self, key, value):
        self._data[str(key)] = [value, time.time()]

    def purge_expired(self):
        now = time.time()
        self._data = {
            k: v for k, v in self._data.items()
            if (now - v[1]) <= self.ttl
        }
