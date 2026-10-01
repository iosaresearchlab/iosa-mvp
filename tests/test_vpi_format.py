"""UI-11 (owner decision 02/10/2026): a VPI shown to people never reaches a
level threshold the record has not reached.

The frontend (frontend/src/lib/vpi-format.mjs, run here in node) and the
backend (backend/vpi_format.py) round down at the displayed precision and
give the same string for the same value, including values just below every
threshold of VPI_SCALE.
"""

import json
import math
import os
import random
import re
import shutil
import subprocess
from pathlib import Path

import pytest

import vpi_core
from vpi_format import format_vpi, format_vpi_full

ROOT = Path(__file__).resolve().parent.parent
MJS = ROOT / "frontend" / "src" / "lib" / "vpi-format.mjs"
THRESHOLDS = [t for t, *_ in vpi_core.VPI_SCALE]


def values():
    out = [1.48, 4.96, 2496, 2.3, 0.051311357478536226, 1e-7, 1293859, 12345.6, 999.99, 99.99]
    for t in THRESHOLDS:
        out += [t, math.nextafter(t, 0), t - 1e-9, t - 0.001, t - 0.01, t - 0.04, t - 0.1, t + 0.01]
    rnd = random.Random(20261002)
    out += [10 ** rnd.uniform(-2, 7) for _ in range(2000)]
    return out


def level(v):
    return next((n for t, n, *_ in vpi_core.VPI_SCALE if v >= t), None)


def shown(s):
    """The number a reader sees in the string."""
    m = re.fullmatch(r"\+([\d,]+(?:\.\d+)?)(K|M)?x", s)
    return float(m.group(1).replace(",", "")) * {None: 1, "K": 1e3, "M": 1e6}[m.group(2)]


def by_node(vals):
    node = shutil.which("node")
    if not node:
        if os.environ.get("CI"):
            pytest.fail("node is needed to check the frontend formatter")
        pytest.skip("node not installed")
    script = ("import { formatVPI, formatVPIFull } from %s;\n"
              "let s = ''; process.stdin.on('data', (d) => s += d).on('end', () => {\n"
              "  const v = JSON.parse(s);\n"
              "  process.stdout.write(JSON.stringify(v.map((x) => [formatVPI(x), formatVPIFull(x)])));\n"
              "});") % json.dumps(MJS.as_uri())
    out = subprocess.run([node, "--input-type=module", "-e", script], input=json.dumps(vals),
                         capture_output=True, text=True, check=True, timeout=60)
    return json.loads(out.stdout)


def test_frontend_and_backend_give_the_same_string():
    vals = values()
    js = by_node(vals)
    for v, (compact, full) in zip(vals, js):
        assert (format_vpi(v), format_vpi_full(v)) == (compact, full), v


def test_the_number_shown_never_reaches_a_level_not_reached():
    for v in values():
        for s in (format_vpi(v), format_vpi_full(v)):
            if v >= 0.1:
                assert shown(s) <= v and level(shown(s)) == level(v), (v, s)


@pytest.mark.parametrize("value, compact, full", [
    (1.48, "+1.4x", "+1.4x"), (1.5, "+1.5x", "+1.5x"), (4.96, "+4.9x", "+4.9x"),
    (5, "+5.0x", "+5.0x"), (2.3, "+2.3x", "+2.3x"), (249.9, "+249x", "+249x"),
    (2496, "+2.4Kx", "+2,496x"), (2500, "+2.5Kx", "+2,500x"), (12345.6, "+12Kx", "+12,345x"),
    (1293859, "+1.2Mx", "+1,293,859x"), ("1.48", "+1.4x", "+1.4x"),
    (None, "—", "—"), (0, "—", "—"),
])
def test_examples(value, compact, full):
    assert (format_vpi(value), format_vpi_full(value)) == (compact, full)


def test_every_formatter_for_people_uses_it():
    main = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")
    assert ':.1f}x"' not in main and main.count("format_vpi_full(") >= 4
    fmt = (ROOT / "frontend" / "src" / "lib" / "format.ts").read_text(encoding="utf-8")
    assert "export { formatVPI, formatVPIFull } from './vpi-format.mjs';" in fmt
    assert "toFixed(1)}x" not in fmt and "toFixed(1)}Kx" not in fmt
    digest = (ROOT / "tools" / "weekly_digest.py").read_text(encoding="utf-8")
    assert 'format_vpi_full(float(v)).lstrip("+")' in digest
