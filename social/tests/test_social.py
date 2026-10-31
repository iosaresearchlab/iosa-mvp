"""FIX-1e (20/10/2026): the social tooling is versioned, imports, and keeps
the scheduled tasks' commands through the wrappers of renders/social/.
No test touches the network: the dry run is checked with requests disabled."""
import json
import os
import pathlib
import py_compile
import re
import subprocess
import sys

import pytest

from social import paths, wrappers

SOCIAL = paths.CODE


def test_every_python_file_compiles():
    for f in SOCIAL.rglob("*.py"):
        py_compile.compile(str(f), doraise=True)


def test_every_wrapped_entry_point_exists_and_its_wrapper_compiles(tmp_path):
    for rel in wrappers.ENTRY_POINTS:
        assert (SOCIAL / rel).is_file(), rel
    for p in wrappers.write(tmp_path / "renders" / "social"):
        py_compile.compile(str(p), doraise=True)


def test_templates_found_by_name_or_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert paths.template("card_breakout.html") == SOCIAL / "templates" / "card_breakout.html"
    (tmp_path / "card_breakout.html").write_text("local")
    assert paths.template("card_breakout.html") == tmp_path / "card_breakout.html"
    with pytest.raises(FileNotFoundError):
        paths.template("card_that_does_not_exist.html")


def test_local_scripts_of_every_template_are_here():
    for html in (SOCIAL / "templates").glob("*.html"):
        for src in re.findall(r'<script src="([^":]+)"', html.read_text(encoding="utf-8")):
            assert (html.parent / src).is_file(), (html.name, src)


def test_the_renderers_read_templates_through_paths():
    for name in ("render_breakout.py", "render_card.py", "render_motion.py", "render_reel.py", "render_reel_video.py"):
        src = (SOCIAL / "templates" / name).read_text(encoding="utf-8")
        assert "from social.paths import template" in src and "template(" in src, name
        assert ".resolve().as_uri()" not in src, name


@pytest.fixture
def work(tmp_path):
    """A working folder like renders/social: wrappers, queue, one image."""
    w = tmp_path / "renders" / "social"
    wrappers.write(w)
    (w / "queue").mkdir()
    (w / "2026-10-19-breakout-x.jpg").write_bytes(b"\xff\xd8\xff")
    return w


def _spec(w, name, **extra):
    spec = {"id": name, "images": ["2026-10-19-breakout-x.jpg"],
            "bluesky": {"text": "Usually 1 view. This one: 2 (as of 19 Oct)", "alt": "card"},
            "instagram": {"caption": "c"}, "threads": {"text": "t"}, **extra}
    p = w / "queue" / f"{name}.json"
    p.write_text(json.dumps(spec), encoding="utf-8")
    return p


def test_dry_run_through_the_wrapper_says_what_would_go_out_and_writes_nothing(work):
    sp = _spec(work, "2026-10-19-s2-x")
    for i in (1, 3):                      # two posts already on Instagram that day: no cap since SOC-CAP
        _spec(work, f"2026-10-19-s{i}-y", result={"instagram": {"url": f"https://ig/{i}"}})
    before = sp.read_bytes()
    env = {**os.environ, "IOSA_REPO": str(paths.REPO), "IOSA_SOCIAL_WORK": ""}
    env.pop("IOSA_SOCIAL_WORK")
    # requests is disabled: a dry run that touched the network would fail here
    blocker = work / "sitecustomize.py"
    blocker.write_text("import requests\n"
                       "def _no(*a, **k): raise SystemExit('network used in a dry run')\n"
                       "requests.get = requests.post = _no\n")
    env["PYTHONPATH"] = str(work)
    r = subprocess.run([sys.executable, "publish_api.py", f"queue/{sp.name}", "--dry-run"],
                       cwd=work, env=env, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "bluesky: publish" in r.stdout
    assert "instagram: publish" in r.stdout   # SOC-CAP (30/10/2026): no daily volume cap
    assert "threads: publish" in r.stdout
    assert "media: all present" in r.stdout
    assert sp.read_bytes() == before


def test_wrapper_finds_the_repo_in_a_staged_layout_without_help(tmp_path):
    """The cloud workspace stages renders/ and social/ side by side
    (/mnt/user-data/uploads/iosa-lab/...): no IOSA_REPO needed, and a wrapper
    never runs itself."""
    import shutil
    root = tmp_path / "iosa-lab"
    shutil.copytree(SOCIAL, root / "social", ignore=shutil.ignore_patterns("__pycache__"))
    w = root / "renders" / "social"
    wrappers.write(w)
    (w / "queue").mkdir()
    (w / "2026-10-19-breakout-x.jpg").write_bytes(b"\xff\xd8\xff")
    sp = _spec(w, "2026-10-19-s1-q")
    env = {k: v for k, v in os.environ.items() if k not in ("IOSA_REPO", "IOSA_SOCIAL_WORK")}
    r = subprocess.run([sys.executable, "-I", "publish_api.py", f"queue/{sp.name}", "--dry-run"],
                       cwd=w, env=env, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "bluesky: publish" in r.stdout


def test_dry_run_flags_missing_media(work):
    sp = _spec(work, "2026-10-19-s4-z", images=["nope.jpg"])
    env = {**os.environ, "IOSA_REPO": str(paths.REPO)}
    r = subprocess.run([sys.executable, "publish_api.py", f"queue/{sp.name}", "--dry-run"],
                       cwd=work, env=env, capture_output=True, text=True, timeout=60)
    assert r.returncode == 1 and "MISSING nope.jpg" in r.stdout


def test_published_channels_are_never_planned_again(work, monkeypatch):
    monkeypatch.setenv("IOSA_SOCIAL_WORK", str(work))
    import importlib
    import social.publish_api as pa
    importlib.reload(pa)
    sp = _spec(work, "2026-10-20-s1-a", result={"bluesky": {"url": "https://bsky.app/x"}})
    spec = json.loads(sp.read_text())
    assert pa.plan(spec, sp) == [("bluesky", "done https://bsky.app/x"), ("instagram", "publish"), ("threads", "publish")]
    assert pa.plan(spec, sp, only={"threads"}) == [("threads", "publish")]
    assert pa.HERE == work and pa.RENDERS == work.parent


def test_bluesky_facets_cover_bare_domain_links_and_hashtags():
    import social.publish_api as pa
    text = "Usually 2 views → iosaresearch.org/creators/x #YouTube"
    f = pa.bsky_facets(text)
    b = text.encode()
    link = next(x for x in f if x["features"][0]["$type"].endswith("#link"))
    assert b[link["index"]["byteStart"]:link["index"]["byteEnd"]] == b"iosaresearch.org/creators/x"
    assert link["features"][0]["uri"] == "https://iosaresearch.org/creators/x"
    tag = next(x for x in f if x["features"][0]["$type"].endswith("#tag"))
    assert tag["features"][0]["tag"] == "YouTube"


def test_check_insights_reports_without_printing_the_token(work, monkeypatch, capsys):
    """FIX-1g: one GET on /me/threads_insights; exit 0 only with data; the token never printed."""
    monkeypatch.setenv("IOSA_SOCIAL_WORK", str(work))
    import importlib
    import social.publish_api as pa
    importlib.reload(pa)
    (work.parent / "threads_token.json").write_text(json.dumps({"access_token": "SECRET-TOKEN", "user_id": "1"}))

    class R:
        def __init__(self, code, body):
            self.status_code, self._b = code, body
        def json(self):
            return self._b
    seen = {}
    def get(url, params=None, timeout=None):
        seen["url"], seen["metric"] = url, params["metric"]
        return R(403, {"error": {"code": 10, "message": "Application does not have permission for this action"}})
    monkeypatch.setattr(pa.requests, "get", get)
    assert pa.check_insights() == 1
    out = capsys.readouterr().out
    assert "NO 403 10" in out and "SECRET-TOKEN" not in out
    assert seen == {"url": "https://graph.threads.net/v1.0/me/threads_insights", "metric": "views,followers_count"}
    monkeypatch.setattr(pa.requests, "get", lambda *a, **k: R(200, {"data": [{"name": "views"}, {"name": "followers_count"}]}))
    assert pa.check_insights() == 0
    assert "OK views, followers_count" in capsys.readouterr().out


def test_no_credential_ever_printed(work, monkeypatch, capsys):
    """A network error carries the URL with access_token=...: it is redacted, in check_insights
    and in any traceback of the script."""
    monkeypatch.setenv("IOSA_SOCIAL_WORK", str(work))
    import importlib
    import social.publish_api as pa
    importlib.reload(pa)
    (work.parent / "threads_token.json").write_text(json.dumps({"access_token": "SECRET-TOKEN", "user_id": "1"}))
    def boom(*a, **k):
        raise pa.requests.ConnectionError("Max retries exceeded with url: /me?access_token=SECRET-TOKEN (x)")
    monkeypatch.setattr(pa.requests, "get", boom)
    assert pa.check_insights() == 2
    assert "SECRET-TOKEN" not in capsys.readouterr().out
    try:
        boom()
    except Exception:
        pa._excepthook(*sys.exc_info())
    err = capsys.readouterr().err
    assert "SECRET-TOKEN" not in err and "access_token=***" in err
    assert pa._redact('{"accessJwt": "abc.def", "x": 1}') == '{"accessJwt": "***", "x": 1}'
    assert pa._redact("Authorization: Bearer abc123") == "Authorization: Bearer ***"


@pytest.mark.parametrize("card, example, keys", [
    ("card_breakout_chart.html", "example_breakout_chart.json", ("title", "usual", "baseline", "this")),
    ("card_breakout_why.html", "example_breakout_why.json", ("why", "title")),
])
def test_carousel_slides_have_an_example(card, example, keys):
    """Carousel slides 2 and 3 (20/10/2026): each template ships with an example that
    render_card.py can render; the chart example carries the videos.list read."""
    assert (SOCIAL / "templates" / card).is_file()
    d = json.loads((SOCIAL / "templates" / example).read_text(encoding="utf-8"))
    for k in keys:
        assert d.get(k), (example, k)
    if "baseline" in d:
        assert all(b["v"] >= 0 and b["d"] < d["this"]["d"] for b in d["baseline"])
        vs = sorted(b["v"] for b in d["baseline"])
        assert d["usual"] > 0 and vs[0] <= d["usual"] <= vs[-1]


def test_plan_never_caps_a_channel(work):
    """SOC-CAP (owner, 30/10/2026 21:01): no daily publishing cap on any channel (CAP = {}).
    However many posts a channel already has that editorial day, plan() never says "capped"."""
    from social import publish_api
    assert publish_api.CAP == {}
    sp = _spec(work, "2026-10-19-s9-x", x={"text": "x"})
    for i in range(1, 9):                 # eight posts already out on every channel that day
        _spec(work, f"2026-10-19-s{i}-y",
              result={c: {"url": f"https://{c}/{i}"} for c in publish_api.CHANNELS})
    spec = json.loads(sp.read_text(encoding="utf-8"))
    for only in (None, set(publish_api.CHANNELS)):
        for force in (False, True):
            actions = publish_api.plan(spec, sp, only, force)
            assert actions and all(a == "publish" for _, a in actions), actions
