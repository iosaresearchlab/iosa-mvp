"""How a VPI is written for people (UI-11, owner decision 02/10/2026).

Rounded DOWN at the displayed precision, so the number never reaches a level
threshold the record has not reached: 1.48 is "+1.4x", never "+1.5x". The
level is still computed on the full value (vpi_core.py). The same strings as
frontend/src/lib/vpi-format.mjs, which tests/test_vpi_format.py runs in node
and compares. CSV exports and the API's numeric fields keep the full value.

The floor is taken on the shortest decimal that identifies the number
(Python's repr(), the same digits as JavaScript's String()), with string
arithmetic only, never a multiplication in floating point.
"""

import math
import re

DASH = "—"
_DECIMAL = re.compile(r"^(\d+)(?:\.(\d+))?(?:e([+-]?\d+))?$")


def _number(value):
    if value is None:
        return math.nan
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    try:
        return float(str(value).replace(",", "").strip())
    except ValueError:
        return math.nan


def _down(n, scale, digits):
    """floor(n / 10**scale) with `digits` decimals, as a string."""
    m = _DECIMAL.match(repr(n))
    fraction = m.group(2) or ""
    mantissa = (m.group(1) + fraction).lstrip("0") or "0"
    p = int(m.group(3) or 0) - len(fraction) - scale + digits
    out = mantissa + "0" * p if p >= 0 else mantissa[:max(0, len(mantissa) + p)]
    out = (out.lstrip("0") or "0").rjust(digits + 1, "0")
    return f"{out[:-digits]}.{out[-digits:]}" if digits else out


def format_vpi(value):
    """Compact, for the web: "+12.5x", "+347x", "+1.3Kx", "+13Kx", "+1.3Mx"."""
    n = _number(value)
    if not math.isfinite(n) or n <= 0:
        return DASH
    if n >= 1_000_000:
        return f"+{_down(n, 6, 1)}Mx"
    if n >= 10_000:
        return f"+{_down(n, 3, 0)}Kx"
    if n >= 1_000:
        return f"+{_down(n, 3, 1)}Kx"
    if n >= 100:
        return f"+{_down(n, 0, 0)}x"
    return f"+{_down(n, 0, 1)}x"


def format_vpi_full(value):
    """Full, for print (plaque, mug): "+1,293,859x"; below 100, one decimal."""
    n = _number(value)
    if not math.isfinite(n) or n <= 0:
        return DASH
    if n >= 100:
        return f"+{int(_down(n, 0, 0)):,}x"
    return f"+{_down(n, 0, 1)}x"
