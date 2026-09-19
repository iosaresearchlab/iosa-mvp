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
