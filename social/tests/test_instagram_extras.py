"""SOC-W5 (24/10/2026): Instagram collaborators and trial reels in the spec. No network."""
import importlib
import json
import os
import subprocess
import sys

import pytest

from social import paths, validate_spec, wrappers


@pytest.fixture
def pa(tmp_path, monkeypatch):
    w = tmp_path / "renders" / "social"
    wrappers.write(w)
    (w / "queue").mkdir()
    for f in ("reel.mp4", "cover.jpg", "card.jpg"):
        (w / f).write_bytes(b"x")
    monkeypatch.setenv("IOSA_SOCIAL_WORK", str(w))
    import social.publish_api as mod
    importlib.reload(mod)
    return mod


def reel(**ig):
    return {"id": "2026-10-24-reel", "video": "reel.mp4", "cover": "cover.jpg", "images": [],
            "instagram": {"caption": "Usually 1 view.", **ig}}


def test_trial_goes_on_the_reel_container_and_collaborators_never(pa, monkeypatch):
    (pa.RENDERS / "instagram_token.json").write_text(json.dumps({"access_token": "IG-TOKEN", "user_id": "1"}))
    sent = []

    class R:
        def __init__(self, b):
            self.b = b

        def json(self):
            return self.b
    monkeypatch.setattr(pa.requests, "post", lambda url, data=None, timeout=None: (sent.append(dict(data)), R({"id": "M1"}))[1])
    monkeypatch.setattr(pa.requests, "get", lambda *a, **k: R({"status_code": "FINISHED", "permalink": "https://ig/p", "caption": "Usually 1 view."}))
    pa.publish_instagram(reel(collaborators=["someone"], trial=True), {"video": "https://s/reel.mp4", "cover": "https://s/c.jpg"})
    assert json.loads(sent[0]["trial_params"]) == {"graduation_strategy": "SS_PERFORMANCE"}
    assert sent[0]["media_type"] == "REELS"
    assert not any("collaborators" in d for d in sent)
    sent.clear()
    pa.publish_instagram(reel(trial="MANUAL"), {"video": "https://s/reel.mp4", "cover": None})
    assert json.loads(sent[0]["trial_params"]) == {"graduation_strategy": "MANUAL"}
    sent.clear()
    pa.publish_instagram(reel(), {"video": "https://s/reel.mp4", "cover": None})       # nothing changes without them
    assert "trial_params" not in sent[0] and "collaborators" not in sent[0]


def test_trial_on_an_image_post_is_ignored_with_a_warning(pa):
    spec = {"images": ["card.jpg"], "instagram": {"caption": "x", "trial": True}}
    trial, warnings = pa.ig_extras(spec)
    assert trial is None and any("needs a video" in w for w in warnings)


def test_the_dry_run_prints_both_fields(pa):
    sp = pa.HERE / "queue" / "2026-10-24-reel.json"
    sp.write_text(json.dumps(reel(collaborators=["someone", "other.one"], trial=True)), encoding="utf-8")
    env = {**os.environ, "IOSA_REPO": str(paths.REPO), "IOSA_SOCIAL_WORK": str(pa.HERE)}   # CI: the repo is elsewhere
    r = subprocess.run([sys.executable, "-I", "publish_api.py", f"queue/{sp.name}", "--dry-run"],
                       cwd=pa.HERE, env=env, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "instagram.collaborators: ['someone', 'other.one'] | instagram.trial: True" in r.stdout
    assert 'trial_params {"graduation_strategy": "SS_PERFORMANCE"}' in r.stdout
    assert "WARNING instagram.collaborators someone, other.one: ignored" in r.stdout
    assert "spec: valid" in r.stdout and "Traceback" not in r.stderr


def test_validate_spec_accepts_them_and_refuses_bad_values():
    ok = reel(collaborators=["a.b_c", "@d"], trial="SS_PERFORMANCE")
    assert not [r for c, r in validate_spec.check(ok, work=None) if c == "instagram"]
    for bad in (reel(collaborators=["a", "b", "c", "d"]), reel(collaborators="a"), reel(collaborators=["no spaces"]),
                reel(trial="SOMETIMES")):
        assert [r for c, r in validate_spec.check(bad, work=None) if c == "instagram"], bad
