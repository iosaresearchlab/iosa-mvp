"""SOC-N (23/10/2026): social/notifications.py. No test touches the network."""
import datetime
import importlib
import json

import pytest

UTC = datetime.timezone.utc
SINCE = datetime.datetime(2026, 10, 21, 12, 0, tzinfo=UTC)
ME = "did:plc:me"


@pytest.fixture
def nt(tmp_path, monkeypatch):
    w = tmp_path / "renders" / "social"
    w.mkdir(parents=True)
    r = w.parent
    (r / "bluesky.txt").write_text("BSKY-PASSWORD\n")
    (r / "threads_token.json").write_text(json.dumps({"access_token": "TH-TOKEN"}))
    (r / "instagram_token.json").write_text(json.dumps({"access_token": "IG-TOKEN", "user_id": "1"}))
    monkeypatch.setenv("IOSA_SOCIAL_WORK", str(w))
    import social.notifications as mod
    importlib.reload(mod)
    return mod


class R:
    def __init__(self, status, body):
        self.status_code, self._b = status, body

    def json(self):
        return self._b


def post(uri_rkey, did=ME, reply=False):
    return {"uri": f"at://{did}/app.bsky.feed.post/{uri_rkey}", "record": {"reply": {"parent": {"uri": "at://other"}}} if reply else {}}


def fake(routes):
    """routes: list of (substring of the URL, body or (status, body)); first match wins."""
    seen = []

    def request(method, url, timeout=None, params=None, headers=None, json=None):
        seen.append((method, url, params))
        for key, body in routes:
            if key in url:
                st, b = body if isinstance(body, tuple) else (200, body)
                return R(st, b)
        return R(404, {"error": {"code": 0, "message": "no route " + url}})
    request.seen = seen
    return request


def bsky_routes(notifications, threads=None, posts=None):
    return [("createSession", {"accessJwt": "JWT", "did": ME}),
            ("listNotifications", {"notifications": notifications}),
            ("getPosts", {"posts": posts or []}),
            ("getPostThread", threads or {"thread": {"replies": []}})]


def n(reason, handle, at, **kw):
    return {"reason": reason, "author": {"handle": handle, "did": "did:plc:" + handle, **kw.pop("author", {})},
            "indexedAt": at, "uri": f"at://did:plc:{handle}/app.bsky.feed.post/r{handle}", **kw}


def test_bluesky_reply_to_our_reply_is_listed_with_what_it_answers(nt, monkeypatch):
    our_reply = post("ourreply", reply=True)
    notes = [n("reply", "ana.bsky.social", "2026-10-22T10:00:00.000Z",
               record={"text": "Good point", "reply": {"parent": {"uri": our_reply["uri"]}}}),
             n("follow", "bob.bsky.social", "2026-10-22T09:00:00.000Z", author={"viewer": {"following": "at://x"}}),
             n("like", "cy.bsky.social", "2026-10-22T08:00:00.000Z", reasonSubject=our_reply["uri"]),
             n("repost", "dee.bsky.social", "2026-10-22T07:00:00.000Z"),
             n("like", "old.bsky.social", "2026-10-20T08:00:00.000Z", reasonSubject=our_reply["uri"])]
    monkeypatch.setattr(nt.requests, "request", fake(bsky_routes(notes, posts=[our_reply])))
    api = nt.Api()
    items, extra = nt.bluesky(api, SINCE)
    assert [i["kind"] for i in items] == ["reply", "follow", "like"]           # the old like is outside
    r = items[0]
    assert r["answers"] == "our reply" and r["already_answered"] is False
    assert r["link"] == "https://bsky.app/profile/ana.bsky.social/post/rana.bsky.social"
    assert r["answers_link"] == "https://bsky.app/profile/iosaresearch.bsky.social/post/ourreply"
    assert items[1]["already_answered"] is True                                # we follow back
    assert items[2]["already_answered"] is None and items[2]["answers"] == "our reply"
    assert extra == ["Bluesky: 1 other notifications (reposts and the like) not listed"]
    assert api.count["bluesky"] == 4                                           # login, list, getPosts, thread


def test_bluesky_a_reply_we_answered_is_marked(nt, monkeypatch):
    notes = [n("mention", "ana.bsky.social", "2026-10-22T10:00:00.000Z", record={"text": "@iosa look"})]
    thread = {"thread": {"replies": [{"post": {"author": {"did": ME}}}]}}
    monkeypatch.setattr(nt.requests, "request", fake(bsky_routes(notes, threads=thread)))
    items, _ = nt.bluesky(nt.Api(), SINCE)
    assert items[0]["already_answered"] is True and items[0]["answers"] is None


def test_threads_reply_to_our_reply_is_reported_as_activity_only(nt, monkeypatch):
    routes = [("/me/threads", {"data": [{"id": "P1", "timestamp": "2026-10-22T12:00:00+0000",
                                        "permalink": "https://threads/p1", "has_replies": True},
                                       {"id": "P2", "timestamp": "2026-10-22T12:00:00+0000",
                                        "permalink": "https://threads/p2", "has_replies": False}]}),
              ("/P1/conversation", {"data": [
                  {"id": "C1", "text": "Nice", "username": "eve", "timestamp": "2026-10-22T13:00:00+0000",
                   "permalink": "https://threads/c1"},
                  {"id": "C2", "text": "Thanks", "username": "iosa.research.lab",
                   "timestamp": "2026-10-22T14:00:00+0000", "permalink": "https://threads/c2"}]}),
              ("/C1/replies", {"data": [{"id": "C2", "username": "iosa.research.lab"}]}),
              ("/me/replies", {"data": [{"id": "Q1", "timestamp": "2026-10-21T17:35:24+0000",
                                         "permalink": "https://threads/Dew9Q4cgE1O", "has_replies": True}]}),
              ("/Q1/replies", {"data": []}),
              ("/me/mentions", (403, {"error": {"code": 10, "message": "Application does not have permission"}}))]
    monkeypatch.setattr(nt.requests, "request", fake(routes))
    api = nt.Api()
    items, notes = nt.threads(api, SINCE)
    assert len(items) == 1 and items[0]["author"] == "eve" and items[0]["answers"] == "our post"
    assert items[0]["already_answered"] is True
    assert any(x.startswith("Threads: replies to our replies need threads.com/activity") and "Dew9Q4cgE1O" in x
               for x in notes)
    assert any("mentions not readable" in x and "code 10" in x for x in notes)
    assert api.count["threads"] == 6                                           # P2 has no replies: not read


def test_instagram_comments_replies_tags_and_dm_permission(nt, monkeypatch):
    routes = [("/me/media", {"data": [{"id": "M1", "timestamp": "2026-10-22T12:00:00+0000",
                                       "permalink": "https://ig/p/1", "comments_count": 3},
                                      {"id": "M2", "timestamp": "2026-10-22T12:00:00+0000",
                                       "permalink": "https://ig/p/2", "comments_count": 0}],
                            "paging": {"next": "https://graph.instagram.com/x?access_token=IG-TOKEN"}}),
              ("/M1/comments", {"data": [{"id": "K1", "text": "wow", "username": "fan",
                                          "timestamp": "2026-10-22T13:00:00+0000",
                                          "replies": {"data": [
                                              {"id": "K2", "text": "thanks", "username": "iosa.research.lab",
                                               "timestamp": "2026-10-22T14:00:00+0000"},
                                              {"id": "K3", "text": "you're welcome", "username": "fan",
                                               "timestamp": "2026-10-22T15:00:00+0000"}]}}]}),
              ("/me/tags", {"data": []}),
              ("/me/conversations", (400, {"error": {"code": 3, "message": "Application does not have the capability"}}))]
    monkeypatch.setattr(nt.requests, "request", fake(routes))
    items, notes = nt.instagram(nt.Api(), SINCE)
    assert [(i["author"], i["answers"], i["already_answered"]) for i in items] == [
        ("fan", "our post", True), ("fan", "our reply", False)]
    assert any("DMs not readable" in x for x in notes)


def test_the_output_file_and_the_summary_never_carry_a_secret(nt, monkeypatch, capsys):
    routes = bsky_routes([n("reply", "ana.bsky.social", datetime.datetime.now(UTC).isoformat(),
                            record={"text": "hi", "reply": {"parent": {"uri": post("x")["uri"]}}})],
                         posts=[post("x")])
    routes += [("graph.threads.net", (500, {"error": {"code": 1, "message": "bad access_token=TH-TOKEN"}})),
               ("/me/media", {"data": [], "paging": {"next": "https://g?access_token=IG-TOKEN"}}),
               ("/me/tags", {"data": []}), ("/me/conversations", {"data": []})]
    monkeypatch.setattr(nt.requests, "request", fake(routes))
    assert nt.main(["--hours", "48"]) == 0
    out = capsys.readouterr().out
    files = list((nt.HERE / "queue").glob("*-notifications.json"))
    body = files[0].read_text(encoding="utf-8")
    for secret in ("TH-TOKEN", "IG-TOKEN", "BSKY-PASSWORD", "JWT"):
        assert secret not in out and secret not in body
    j = json.loads(body)
    assert j["youtube_units"] == 0 and set(j["requests"]) == {"bluesky", "threads", "instagram"}
    assert "X: browser" in j["notes"] and "X: browser" in out
    assert "Not answered yet:" in out and "@ana.bsky.social" in out


def test_timestamps_of_the_three_apis_parse_alike(nt):
    a = nt.when("2026-10-22T10:00:00.123Z")
    b = nt.when("2026-10-22T10:00:00+0000")
    c = nt.when("2026-10-22T10:00:00+00:00")
    assert a.replace(microsecond=0) == b == c
