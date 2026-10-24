"""SOC-F (24/10/2026): the breakout card renders in both layouts (face and old) at 1080x1350,
and a face card whose picture is missing fails cleanly. Skipped without Playwright's Chromium."""
import json
import pathlib
import struct
import subprocess
import sys

import pytest

TEMPLATES = pathlib.Path(__file__).resolve().parents[1] / "templates"
CHROMIUM = pathlib.Path("/opt/pw-browsers/chromium")

pytestmark = pytest.mark.skipif(not CHROMIUM.exists(), reason="Playwright Chromium not installed here")


def png_size(path):
    head = pathlib.Path(path).read_bytes()[:24]
    assert head[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", head[16:24])


def render(data_json, out):
    return subprocess.run([sys.executable, "-I", str(TEMPLATES / "render_breakout.py"), str(data_json), str(out)],
                          cwd=TEMPLATES, capture_output=True, text=True, timeout=120)


@pytest.mark.parametrize("name", ["example_breakout_face.json", "example_reysotto.json"])
def test_both_layouts_render_at_1080x1350(name, tmp_path):
    out = tmp_path / "card.png"
    r = render(TEMPLATES / name, out)
    assert r.returncode == 0, r.stderr[-500:]
    assert png_size(out) == (1080, 1350)


def test_a_face_card_without_its_avatar_fails_cleanly(tmp_path):
    data = json.loads((TEMPLATES / "example_breakout_face.json").read_text(encoding="utf-8"))
    data["avatar"] = "no_such_avatar.jpg"
    spec = tmp_path / "face.json"
    spec.write_text(json.dumps(data), encoding="utf-8")
    out = tmp_path / "card.png"
    r = render(spec, out)
    assert r.returncode != 0
    assert "avatar not found: no_such_avatar.jpg" in r.stderr
    assert "Traceback" not in r.stderr and not out.exists()
