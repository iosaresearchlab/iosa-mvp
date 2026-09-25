"""One scale, the owner's (docs/01 section 4.3): backend and frontend agree,
and a record below 1.5x is a valid standard record with no level."""

import re
from pathlib import Path

import vpi_core as core
import vpi_engine

ROOT = Path(__file__).resolve().parent.parent
OWNER = [(2500.0, 10), (1500.0, 9), (1000.0, 8), (250.0, 7), (100.0, 6),
         (50.0, 5), (25.0, 4), (10.0, 3), (5.0, 2), (1.5, 1)]


def test_backend_scale_is_the_owners_table():
    assert [(t, lvl) for t, lvl, _, _ in core.VPI_SCALE] == OWNER


def test_frontend_scale_is_identical_to_the_backend():
    ts = (ROOT / "frontend" / "src" / "lib" / "vpi-scale.ts").read_text(encoding="utf-8")
    rows = re.findall(r"\[([\d.]+),\s*(\d+),\s*'([^']+)',\s*'(#[0-9A-Fa-f]{6})'\]", ts)
    assert [(float(t), int(l), n, c) for t, l, n, c in rows] == list(core.VPI_SCALE)


def test_the_documented_table_is_the_code():
    doc = (ROOT / "docs" / "01-methodology-protocol.md").read_text(encoding="utf-8")
    table = re.findall(r"^\|\s*≥ ([\d,.]+)x\s*\|\s*(\d+)\s*\|", doc, re.M)
    assert [(float(t.replace(",", "")), int(l)) for t, l in table] == OWNER


def test_engine_writes_no_level_below_the_lowest_threshold():
    assert vpi_engine._vpi_fields(140, 100) == {"vpi_ratio": 1.4, "vpi_level": None,
                                                "vpi_level_name": None, "vpi_color": None}
    assert vpi_engine._vpi_fields(150, 100)["vpi_level"] == 1
