"""
Nucleo condiviso del calcolo VPI.

Unica fonte di verita' per formula, soglie, colori, durata degli Short e
ciclo di vita dei record. Importato da vpi_engine.py e da qualunque script
di manutenzione, cosi' che due percorsi non possano piu' calcolare due VPI
diversi per lo stesso video.
"""

import json
import statistics
import re
import time
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------- costanti

SHORT_MAX_SECONDS = 180          # durata massima di uno Short
CAMPAIGN_DAYS = 15               # finestra di visibilita' di un record
BASELINE_MAX_AGE_DAYS = 90       # quanto indietro guardare per la baseline
MIN_BASELINE_SAMPLES = 5         # sotto questa soglia la mediana non e' affidabile

# v2 baseline rule (docs/01-methodology-protocol.md section 2): samples of the
# same channel and format published between BASELINE_MIN_AGE_DAYS and
# BASELINE_MAX_AGE_DAYS before the MEASURED VIDEO was published; at least
# MIN_BASELINE_SAMPLES, at most BASELINE_SAMPLES_MAX spread evenly across the
# window; uploads read up to BASELINE_PAGES_MAX pages. One rule, no fallback.
BASELINE_MIN_AGE_DAYS = 7
BASELINE_SAMPLES_MAX = 20
BASELINE_PAGES_MAX = 3
RULE_STANDARD = "standard"
RULE_NOT_COMPUTABLE = "not_computable"

# v1 only: the floor under which baseline_from_samples() computed the 28,917
# archived records. Kept so that recomputing a v1 record keeps the v1 rule.
V1_BASELINE_MIN_AGE_DAYS = 14

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


#: I due formati che misuriamo. Il VPI confronta un video con la mediana del
#: suo stesso canale, e quel confronto ha senso solo dentro lo stesso formato:
#: su quasi tutti i canali gli Short e i video lunghi hanno distribuzioni di
#: views diverse, quindi una baseline mista misurerebbe il mix di
#: pubblicazione del canale invece della prestazione del video.
FORMATO_SHORT = "SHORT"
FORMATO_LONG = "LONG"


def formato_da_durata(duration_seconds: int) -> str | None:
    """SHORT, LONG, oppure None se la durata non e' utilizzabile (0 o assente)."""
    if not duration_seconds or duration_seconds <= 0:
        return None
    return FORMATO_SHORT if duration_seconds <= SHORT_MAX_SECONDS else FORMATO_LONG


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


def baseline_from_samples(campioni, exclude_video_id: str = None, giorni_indietro: float = 0):
    """v1 ONLY. Mediana delle views dei video recenti e maturi del canale.

    The rule of the 28,917 archived v1 records, kept unchanged for them. v2
    records use baseline_v2(): window anchored to the measured video, no
    fallback, at most 20 samples (docs/01-methodology-protocol.md section 2).

    I campioni che riceve sono gia' filtrati per formato da chi la chiama: qui
    non si distingue fra Short e video lunghi, si applica la stessa regola alla
    lista che arriva.

    Tre regole, invariate rispetto a prima:
      - solo Short pubblicati negli ultimi BASELINE_MAX_AGE_DAYS giorni, cosi'
        un video di due anni fa non gonfia il denominatore con views accumulate
        in un arco temporale incomparabile;
      - si preferiscono i video con almeno BASELINE_MIN_AGE_DAYS di eta', gia'
        arrivati a regime; se sono troppo pochi si allarga a tutti i recenti;
      - il video che stiamo misurando e' escluso dalla propria baseline.

    giorni_indietro sposta la finestra all'indietro nel tempo ed e' quello che
    serve per ricalcolare un record vecchio: l'eta' dei campioni e' misurata da
    adesso, ma un record rilevato dieci giorni fa va confrontato con la baseline
    che il canale aveva allora, non con quella di oggi. Senza questo, per un
    canale che pubblica molto il denominatore di oggi e' piu' basso e il VPI
    risulterebbe gonfiato dal solo passare del tempo. I video pubblicati dopo la
    rilevazione vengono quindi esclusi, e maturita' e scadenza sono valutate
    rispetto a quel momento.

    Restituisce (baseline, numero_di_campioni); baseline e' None se i campioni
    non bastano a rendere la mediana significativa.
    """
    if not campioni:
        return None, 0

    recent, mature = [], []
    for c in campioni:
        if c["video_id"] == exclude_video_id:
            continue
        eta = c["age_days"] - giorni_indietro
        if eta < 0:
            continue          # non esisteva ancora quando abbiamo misurato
        if eta > BASELINE_MAX_AGE_DAYS:
            continue
        recent.append(c["views"])
        if eta >= V1_BASELINE_MIN_AGE_DAYS:
            mature.append(c["views"])

    sample = mature if len(mature) >= MIN_BASELINE_SAMPLES else recent
    if len(sample) < MIN_BASELINE_SAMPLES:
        return None, len(sample)

    median_baseline = float(statistics.median(sample))
    return (median_baseline if median_baseline > 0 else None), len(sample)


def _as_datetime(value):
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def even_pick(items, k):
    """k items spread evenly across an ordered list, first and last included."""
    n = len(items)
    if n <= k:
        return list(items)
    if k == 1:
        return [items[0]]
    return [items[round(i * (n - 1) / (k - 1))] for i in range(k)]


def baseline_v2(samples, measured_video_id, measured_published_at):
    """The v2 baseline of ONE measured video (docs/01 section 2).

    samples: [{video_id, published_at, views}] of the same channel AND the
    same format as the measured video; views None = not readable, excluded.
    The window is [published - 90 days, published - 7 days], both ends
    included, measured from the measured video's own publication, never from
    now: that is what makes the denominator pre-event.

    Returns {baseline, samples, rule, span_days, video_ids}. With fewer than
    5 usable samples, or a median of 0 (the ratio would be undefined):
    rule 'not_computable', baseline None. The record still exists.
    """
    ref = _as_datetime(measured_published_at)
    window = []
    for c in samples:
        if c["video_id"] == measured_video_id or c.get("views") is None:
            continue
        pub = _as_datetime(c["published_at"])
        age = (ref - pub).total_seconds() / 86400.0
        if BASELINE_MIN_AGE_DAYS <= age <= BASELINE_MAX_AGE_DAYS:
            window.append((pub, c["video_id"], float(c["views"])))
    window.sort()
    chosen = even_pick(window, BASELINE_SAMPLES_MAX)
    ids = [vid for _, vid, _ in chosen]
    span = ((chosen[-1][0] - chosen[0][0]).total_seconds() / 86400.0) if chosen else None
    out = {"samples": len(chosen), "video_ids": ids, "span_days": span}
    if len(chosen) < MIN_BASELINE_SAMPLES:
        return {**out, "baseline": None, "rule": RULE_NOT_COMPUTABLE}
    median = float(statistics.median(v for _, _, v in chosen))
    if median <= 0:
        return {**out, "baseline": None, "rule": RULE_NOT_COMPUTABLE}
    return {**out, "baseline": median, "rule": RULE_STANDARD}


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
