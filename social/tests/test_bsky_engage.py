"""SOC-E (23/10/2026): social/bsky_engage.py. No test touches the network."""
import datetime
import importlib

import pytest

ME = "did:plc:me"


@pytest.fixture
def be(tmp_path, monkeypatch):
    w = tmp_path / "renders" / "social"
    w.mkdir(parents=True)
    (w.parent / "bluesky.txt").write_text("BSKY-PASSWORD\n")
    monkeypatch.setenv("IOSA_SOCIAL_WORK", str(w))
    import social.bsky_engage as mod
    importlib.reload(mod)
    return mod


class R:
    def __init__(self, body, status=200):
        self.status_code, self._b = status, body

    def json(self):
        return self._b


def post(rkey, did, handle, liked=False):
    return {"uri": f"at://{did}/app.bsky.feed.post/{rkey}", "cid": "cid" + rkey,
            "author": {"did": did, "handle": handle}, "viewer": {"like": "at://l"} if liked else {}}


@pytest.fixture
def net(monkeypatch, be):
    state = {"posts": [], "profiles": [], "created": [], "seen": []}

    def request(method, url, headers=None, timeout=None, params=None, json=None):
        state["seen"].append((method, url.rsplit("/", 1)[-1], params, json))
        if url.endswith("createSession"):
            return R({"accessJwt": "JWT", "did": ME})
        if url.endswith("resolveHandle"):
            return R({"did": "did:plc:" + params["handle"].split(".")[0]})
        if url.endswith("getPosts"):
            want = [v for k, v in params]
            return R({"posts": [p for p in state["posts"] if p["uri"] in want]})
        if url.endswith("getProfiles"):
            return R({"profiles": state["profiles"]})
        if url.endswith("createRecord"):
            state["created"].append(json)
            return R({"uri": "at://new", "cid": "c"})
        return R({"error": "NotFound"}, 404)
    monkeypatch.setattr(be.requests, "request", request)
    return state


def test_one_like_and_one_follow_are_written_and_logged(be, net, capsys):
    net["posts"] = [post("3abc", "did:plc:ana", "ana.bsky.social")]
    net["profiles"] = [{"did": "did:plc:bob", "handle": "bob.bsky.social", "viewer": {}}]
    assert be.main(["--like", "https://bsky.app/profile/ana.bsky.social/post/3abc", "--follow", "@bob.bsky.social"]) == 0
    kinds = [c["collection"] for c in net["created"]]
    assert kinds == ["app.bsky.feed.like", "app.bsky.graph.follow"]
    assert net["created"][0]["record"]["subject"] == {"uri": "at://did:plc:ana/app.bsky.feed.post/3abc", "cid": "cid3abc"}
    assert net["created"][1]["record"]["subject"] == "did:plc:bob"
    lines = (be.HERE / be.LOG).read_text(encoding="utf-8").splitlines()
    assert [l.split()[1:3] for l in lines] == [["like", "did:plc:ana"], ["follow", "did:plc:bob"]]
    out = capsys.readouterr().out
    assert "BSKY-PASSWORD" not in out and "JWT" not in out and "YouTube units: 0" in out


def test_more_than_four_likes_or_two_follows_does_nothing(be, net):
    with pytest.raises(SystemExit):
        be.run([f"at://did:plc:a/app.bsky.feed.post/{i}" for i in range(5)], [])
    with pytest.raises(SystemExit):
        be.run([], ["a", "b", "c"])
    assert net["seen"] == []                                   # not even the login


def test_the_same_account_is_never_engaged_twice_in_seven_days(be, net):
    old = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=8)).strftime("%Y-%m-%dT%H:%M:%SZ")
    new = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    (be.HERE / be.LOG).write_text(f"{old} like did:plc:old old.bsky.social at://x\n"
                                  f"{new} follow did:plc:ana ana.bsky.social\n", encoding="utf-8")
    net["posts"] = [post("1", "did:plc:ana", "ana.bsky.social"), post("2", "did:plc:old", "old.bsky.social"),
                    post("3", "did:plc:cy", "cy.bsky.social"), post("4", "did:plc:cy", "cy.bsky.social")]
    done, skipped, _ = be.run([p["uri"] for p in net["posts"]], [])
    assert [d.split()[1] for d in done] == ["old.bsky.social", "cy.bsky.social"]     # 8 days ago is fine
    assert any("ana.bsky.social" in s and "7 days" in s for s in skipped)
    assert any("cy.bsky.social" in s and "7 days" in s for s in skipped)             # twice in one run
    assert len(net["created"]) == 2


def test_already_liked_or_followed_and_dry_run_write_nothing(be, net):
    net["posts"] = [post("1", "did:plc:ana", "ana.bsky.social", liked=True), post("2", "did:plc:cy", "cy.bsky.social")]
    net["profiles"] = [{"did": "did:plc:bob", "handle": "bob.bsky.social", "viewer": {"following": "at://f"}}]
    done, skipped, _ = be.run([p["uri"] for p in net["posts"]], ["bob.bsky.social"], dry=True)
    assert done == ["like cy.bsky.social at://did:plc:cy/app.bsky.feed.post/2"]
    assert {s.split(":")[-1].strip() for s in skipped} == {"already liked", "already followed"}
    assert net["created"] == [] and not (be.HERE / be.LOG).exists()


def test_it_only_ever_writes_likes_and_follows(be):
    src = (be.paths.CODE / "bsky_engage.py").read_text(encoding="utf-8")
    assert "app.bsky.feed.post\", {" not in src and "reply" not in src.split('"""', 2)[2]
