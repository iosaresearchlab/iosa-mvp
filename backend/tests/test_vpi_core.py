"""
Test del nucleo di calcolo VPI.

Eseguibili senza dipendenze esterne:
    python tests/test_vpi_core.py
oppure con pytest:
    pytest tests/
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import vpi_core as core


def test_parse_iso_duration():
    assert core.parse_iso_duration("PT1M15S") == 75
    assert core.parse_iso_duration("PT59S") == 59
    assert core.parse_iso_duration("PT3M") == 180
    assert core.parse_iso_duration("PT1H2M3S") == 3723
    assert core.parse_iso_duration("") == 0
    assert core.parse_iso_duration(None) == 0


def test_is_short_duration():
    assert core.is_short_duration(1)
    assert core.is_short_duration(180)
    assert not core.is_short_duration(181)
    assert not core.is_short_duration(0)
    assert not core.is_short_duration(-5)


def test_calculate_vpi_ratio():
    assert core.calculate_vpi_ratio(100, 10) == 10.0
    assert core.calculate_vpi_ratio(0, 10) == 0.0
    # baseline assente o nulla: nessun outlier, non una divisione per zero
    assert core.calculate_vpi_ratio(100, 0) == 1.0
    assert core.calculate_vpi_ratio(100, None) == 1.0
    assert core.calculate_vpi_ratio("abc", 10) == 1.0


def test_level_thresholds():
    attesi = [
        (120.0, 10), (50.0, 10), (49.9, 9), (25.0, 9), (24.9, 8),
        (15.0, 8), (14.9, 7), (10.0, 7), (9.9, 6), (7.5, 6),
        (7.4, 5), (5.0, 5), (4.9, 4), (3.0, 4), (2.9, 3),
        (2.0, 3), (1.9, 2), (1.5, 2), (1.49, 1), (0.5, 1),
    ]
    for ratio, livello in attesi:
        assert core.get_vpi_metadata(ratio)[0] == livello, f"VPI {ratio}"


def test_no_rounding_before_level():
    """1.45 sta sotto 1.5: col vecchio arrotondamento saliva di livello."""
    assert core.get_vpi_metadata(1.45)[0] == 1
    assert core.round_vpi(1.45) == 1.4 or core.round_vpi(1.45) == 1.5


def test_every_level_has_a_colour():
    livelli = {lvl for _, lvl, _, _ in core.VPI_SCALE}
    assert livelli == set(range(1, 11))
    for _, _, nome, colore in core.VPI_SCALE:
        assert nome.startswith("Lvl ")
        assert colore.startswith("#") and len(colore) == 7


def test_age_in_days():
    now = datetime(2026, 9, 19, tzinfo=timezone.utc)
    assert abs(core.age_in_days("2026-09-09T00:00:00Z", now) - 10) < 0.01
    assert abs(core.age_in_days("2026-06-21T00:00:00+00:00", now) - 90) < 0.01
    assert core.age_in_days("") is None
    assert core.age_in_days("non-una-data") is None
    assert core.age_in_days(None) is None


def test_ttl_cache():
    cache = core.TTLCache("selftest", ttl_seconds=60)
    cache.set("k", [123, 4])
    assert cache.get("k") == [123, 4]
    assert cache.get("mancante") is None
    scaduta = core.TTLCache("selftest_scaduta", ttl_seconds=0)
    scaduta.set("k", 1)
    assert scaduta.get("k") is None


def _campione(video_id, views, age_days):
    return {"video_id": video_id, "views": float(views), "age_days": age_days}


def test_baseline_e_la_mediana_dei_maturi():
    campioni = [_campione(f"v{i}", views, 30) for i, views in enumerate([100, 200, 300, 400, 500])]
    assert core.baseline_from_samples(campioni) == (300.0, 5)


def test_baseline_esclude_il_video_misurato():
    campioni = [_campione("v0", 10000, 30)] + [_campione(f"v{i}", 100, 30) for i in range(1, 6)]
    assert core.baseline_from_samples(campioni, exclude_video_id="v0") == (100.0, 5)


def test_baseline_scarta_i_video_troppo_vecchi():
    vecchi = [_campione(f"o{i}", 999999, core.BASELINE_MAX_AGE_DAYS + 10) for i in range(5)]
    recenti = [_campione(f"n{i}", 100, 30) for i in range(5)]
    assert core.baseline_from_samples(vecchi + recenti) == (100.0, 5)


def test_baseline_preferisce_i_maturi_ma_ripiega_sui_recenti():
    maturi = [_campione(f"m{i}", 1000, core.BASELINE_MIN_AGE_DAYS + 1) for i in range(2)]
    freschi = [_campione(f"f{i}", 10, 1) for i in range(4)]
    # 6 campioni: [10, 10, 10, 10, 1000, 1000] -> mediana 10.0
    assert core.baseline_from_samples(maturi + freschi) == (10.0, 6)


def test_baseline_riportata_indietro_esclude_i_video_successivi():
    # Record rilevato 40 giorni fa. I 5 Short pubblicati 20 giorni fa sono
    # successivi alla rilevazione e non devono entrare nel denominatore, anche
    # se visti da oggi sembrano campioni maturi a tutti gli effetti.
    dopo = [_campione(f"d{i}", 5, 20) for i in range(5)]
    prima = [_campione(f"p{i}", 1000, 60) for i in range(5)]
    assert core.baseline_from_samples(dopo + prima, giorni_indietro=40) == (1000.0, 5)
    # Senza lo spostamento la mediana crolla e il VPI si gonfierebbe.
    assert core.baseline_from_samples(dopo + prima) == (502.5, 10)


def test_baseline_none_se_i_campioni_non_bastano():
    campioni = [_campione(f"v{i}", 100, 30) for i in range(core.MIN_BASELINE_SAMPLES - 1)]
    assert core.baseline_from_samples(campioni) == (None, core.MIN_BASELINE_SAMPLES - 1)


def test_baseline_none_se_lista_vuota():
    assert core.baseline_from_samples([]) == (None, 0)
    assert core.baseline_from_samples(None) == (None, 0)


def test_soglia_minima_di_baseline_e_coerente():
    # La mediana ha granularita' 0.5 view: sotto questa soglia il VPI a una
    # decimale dichiarerebbe una precisione che la misura non possiede.
    assert core.MIN_BASELINE_VIEWS >= 500
    assert 0.5 / core.MIN_BASELINE_VIEWS <= 0.001


if __name__ == "__main__":
    fallimenti = 0
    for nome, funzione in sorted(globals().items()):
        if nome.startswith("test_") and callable(funzione):
            try:
                funzione()
                print(f"  ok    {nome}")
            except AssertionError as e:
                fallimenti += 1
                print(f"  FAIL  {nome}: {e}")
    print(f"\n{'TUTTI I TEST PASSATI' if not fallimenti else str(fallimenti) + ' TEST FALLITI'}")
    sys.exit(1 if fallimenti else 0)


# --------------------------------------------------------------- formati

def test_formato_da_durata_separa_short_e_lunghi():
    from vpi_core import formato_da_durata, FORMATO_SHORT, FORMATO_LONG, SHORT_MAX_SECONDS
    assert formato_da_durata(1) == FORMATO_SHORT
    assert formato_da_durata(SHORT_MAX_SECONDS) == FORMATO_SHORT
    assert formato_da_durata(SHORT_MAX_SECONDS + 1) == FORMATO_LONG
    assert formato_da_durata(3600) == FORMATO_LONG


def test_formato_da_durata_rifiuta_durate_non_utilizzabili():
    """Durata assente o nulla: dirette, premiere, video rimossi. Non si indovina."""
    from vpi_core import formato_da_durata
    assert formato_da_durata(0) is None
    assert formato_da_durata(None) is None
    assert formato_da_durata(-5) is None


def test_baseline_di_un_formato_non_e_contaminata_dall_altro():
    """
    Il punto dell'estensione ai video lunghi: se le due liste si mescolassero,
    la mediana direbbe piu' sul mix di pubblicazione del canale che sul video.
    """
    from vpi_core import baseline_from_samples

    short = [{"video_id": f"s{i}", "views": 1000.0, "age_days": 5} for i in range(6)]
    lunghi = [{"video_id": f"l{i}", "views": 100000.0, "age_days": 5} for i in range(6)]

    base_short, n_short = baseline_from_samples(short)
    base_long, n_long = baseline_from_samples(lunghi)
    base_mista, _ = baseline_from_samples(short + lunghi)

    assert base_short == 1000.0 and n_short == 6
    assert base_long == 100000.0 and n_long == 6
    # la mediana mista non corrisponde a nessuno dei due gruppi
    assert base_short < base_mista < base_long


def test_un_canale_a_prevalenza_long_non_falsa_i_suoi_short():
    """
    Il rischio concreto non e' il singolo video anomalo: la mediana lo assorbe
    da sola. E' il canale che pubblica soprattutto video lunghi e ogni tanto
    uno Short. Li' una baseline mista viene dominata dal formato piu'
    frequente, e gli Short di quel canale risultano tutti sottoperformanti
    per un motivo che non li riguarda.
    """
    from vpi_core import baseline_from_samples, calculate_vpi_ratio

    short = [{"video_id": f"s{i}", "views": 2000.0, "age_days": 30} for i in range(5)]
    lunghi = [{"video_id": f"l{i}", "views": 300000.0, "age_days": 30} for i in range(9)]

    base_corretta, _ = baseline_from_samples(short)
    base_mista, _ = baseline_from_samples(short + lunghi)

    assert base_corretta == 2000.0
    assert base_mista == 300000.0      # la mediana finisce fra i video lunghi

    uno_short_virale = 60000.0
    assert calculate_vpi_ratio(uno_short_virale, base_corretta) == 30.0   # Lvl 9
    assert calculate_vpi_ratio(uno_short_virale, base_mista) < 1.0        # invisibile
