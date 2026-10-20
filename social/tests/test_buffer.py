"""SOC-X (20/10/2026): X goes out through Buffer's GraphQL API. No test touches the network."""
import datetime
import importlib
import json

import pytest

from social import wrappers


@pytest.fixture
def pa(tmp_path, monkeypatch):
    w = tmp_path / "renders" / "social"
    wrappers.write(w)
    (w / "queue").mkdir()
    (w / "card.png").write_bytes(b"\x89PNG")
    (w / "card.jpg").write_bytes(b"\xff\xd8\xff")
    (w.parent / "buffer_key.txt").write_text("SECRET-BUFFER-KEY\n")
    monkeypatch.setenv("IOSA_SOCIAL_WORK", str(w))
    import social.publish_api as mod
    importlib.reload(mod)
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)
    return mod


def _spec(pa, name="2026-10-20-s3-a", **extra):
    spec = {"id": name, "images": ["card.jpg"],
            "bluesky": {"text": "Usually 1 view. This one: 2 (as of 19 Oct)", "alt": "card"},
            "x": {"text": "Usually 1 view. This one: 2 (as of 19 Oct)", "reply": "https://youtu.be/abc the video",
                  "card": "card.png"}, **extra}
    sp = pa.HERE / "queue" / f"{name}.json"
    sp.write_text(json.dumps(spec), encoding="utf-8")
    return sp, spec


class FakeBuffer:
    """Answers createPost, then the post 'sending' once and 'sent' with its X link."""
    def __init__(self, statuses=("sending", "sent")):
        self.calls, self.statuses = [], list(statuses)

    def __call__(self, query, variables, label):
        self.calls.append((label, variables))
        if query.lstrip().startswith("mutation"):
            return {"createPost": {"post": {"id": "BUF1", "status": "sending"}}}
        st = self.statuses.pop(0) if self.statuses else "sent"
        return {"post": {"id": "BUF1", "status": st, "sentAt": None, "error": None,
                         "externalLink": "https://x.com/IOSAResearch/status/1" if st == "sent" else None}}


def test_the_input_is_the_card_post_and_the_reply_as_buffers_thread(pa):
    _, spec = _spec(pa)
    i = pa.x_input(spec, "https://storage/card.png")
    assert i["channelId"] == "6ad7c83b778b240e2f6ee253" and i["mode"] == "shareNow"
    assert i["schedulingType"] == "automatic"
    assert i["text"] == spec["x"]["text"] and i["assets"] == [{"image": {"url": "https://storage/card.png"}}]
    thread = i["metadata"]["twitter"]["thread"]
    assert thread[0] == {"text": spec["x"]["text"], "assets": i["assets"]}     # repeats the post
    assert thread[1] == {"text": spec["x"]["reply"], "assets": []}             # text only
    assert "isAiGenerated" not in json.dumps(i)


def test_x_is_published_only_when_asked_and_never_twice(pa):
    sp, spec = _spec(pa)
    assert [c for c, _ in pa.plan(spec, sp)] == ["bluesky"]
    assert pa.plan(spec, sp, only={"x"}) == [("x", "publish")]
    spec["result"] = {"x": {"post": "https://x.com/IOSAResearch/status/9", "reply": "https://x.com/r"}}
    assert pa.plan(spec, sp, only={"x"}) == [("x", "done https://x.com/IOSAResearch/status/9")]


def test_publish_x_writes_the_buffer_id_first_then_the_link(pa, monkeypatch):
    sp, spec = _spec(pa)
    spec["result"] = {}
    fake = FakeBuffer()
    monkeypatch.setattr(pa, "buffer", fake)
    monkeypatch.setattr(pa, "upload_public", lambda p: "https://storage/" + str(p))
    saved = []
    out = pa.publish_x(spec, {"images": ["https://storage/card.jpg"]},
                       lambda: saved.append(json.loads(json.dumps(spec["result"]))))
    assert out == {"post": "https://x.com/IOSAResearch/status/1", "buffer": "BUF1", "via": "buffer"}
    assert any(s.get("x_buffer") == "BUF1" for s in saved)                       # saved before polling
    create = fake.calls[0][1]["input"]
    assert create["assets"] == [{"image": {"url": "https://storage/card.png"}}]  # the X card, not the JPEG
    assert len(fake.calls) == 3                                                  # create + 2 reads


def test_a_run_that_stopped_reads_the_same_post_instead_of_creating_another(pa, monkeypatch):
    _, spec = _spec(pa)
    spec["result"] = {"x_buffer": "BUF1"}
    fake = FakeBuffer(statuses=("sent",))
    monkeypatch.setattr(pa, "buffer", fake)
    out = pa.publish_x(spec, {"images": []}, lambda: None)
    assert out["post"].endswith("/status/1")
    assert [label for label, _ in fake.calls] == ["read BUF1"]


def test_requests_are_counted_and_the_budget_stops_a_new_post(pa, monkeypatch):
    log = pa.HERE / pa.BUFFER_LOG
    now = datetime.datetime.utcnow()
    old = (now - datetime.timedelta(days=31)).isoformat(timespec="seconds")
    recent = now.isoformat(timespec="seconds")
    log.write_text(f"{old}Z read X 200\n" + f"{recent}Z read X 200\n" * 3, encoding="utf-8")
    assert pa.buffer_used() == 3
    log.write_text(f"{recent}Z read X 200\n" * (pa.BUFFER_BUDGET - 5), encoding="utf-8")
    _, spec = _spec(pa)
    spec["result"] = {}
    monkeypatch.setattr(pa, "buffer", lambda *a: pytest.fail("no request past the budget"))
    with pytest.raises(SystemExit):
        pa.publish_x(spec, {"images": []}, lambda: None)


def test_buffer_logs_every_request_and_never_prints_the_key(pa, monkeypatch, capsys):
    class R:
        status_code = 200
        def json(self):
            return {"errors": [{"message": "Unauthorized"}]}
    seen = {}
    def post(url, json=None, headers=None, timeout=None):
        seen["url"], seen["auth"] = url, headers["Authorization"]
        return R()
    monkeypatch.setattr(pa.requests, "post", post)
    with pytest.raises(SystemExit):
        pa.buffer("query { x }", {}, "probe")
    assert seen == {"url": "https://api.buffer.com", "auth": "Bearer SECRET-BUFFER-KEY"}
    assert "SECRET-BUFFER-KEY" not in capsys.readouterr().out
    assert (pa.HERE / pa.BUFFER_LOG).read_text(encoding="utf-8").strip().endswith("probe 200")
