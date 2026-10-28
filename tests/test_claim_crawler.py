"""OPS-3 (26/10/2026): the burst rule on claim_visite (migration 20261028161007).

A desktop visit without a referrer is marked automatico when the 24 hours
before it already hold at least 20 such visits on other claim tokens. The
inserts run as the public role, as the claim page's do. Nothing else changes:
phone visits, visits with a referrer, a quiet day, a true the page set.
"""

CRAWL_TOKENS = 20


def _visit(db, token, schermo="desktop", provenienza=None, automatico=False, ago=None):
    """Insert one visit as anon (ago: hours before now, written by the owner role)."""
    with db.cursor() as cur:
        if ago is not None:
            cur.execute("insert into claim_visite (claim_token, schermo, provenienza, automatico, vista_il) "
                        "values (%s, %s, %s, %s, now() - make_interval(hours => %s)) returning automatico",
                        (token, schermo, provenienza, automatico, ago))
            return cur.fetchone()[0]
        cur.execute("grant insert on public.claim_visite to anon")
        cur.execute("set local role anon")
        cur.execute("insert into claim_visite (claim_token, schermo, provenienza, automatico) "
                    "values (%s, %s, %s, %s)", (token, schermo, provenienza, automatico))
        cur.execute("reset role")
        cur.execute("select automatico from claim_visite where claim_token = %s "
                    "order by vista_il desc, id limit 1", (token,))
        return cur.fetchone()[0]


def _burst(db, n, ago=1):
    for i in range(n):
        _visit(db, f"crawl_{i}", ago=ago)


def test_a_burst_marks_the_next_desktop_visit_without_referrer(db):
    _burst(db, CRAWL_TOKENS)
    assert _visit(db, "next_one") is True


def test_below_the_threshold_nothing_changes(db):
    _burst(db, CRAWL_TOKENS - 1)
    assert _visit(db, "next_one") is False


def test_a_phone_visit_is_never_touched(db):
    _burst(db, 200)
    assert _visit(db, "phone", schermo="mobile") is False


def test_a_visit_with_a_referrer_is_never_touched(db):
    _burst(db, 200)
    assert _visit(db, "from_x", provenienza="t.co") is False


def test_visits_older_than_24_hours_do_not_count(db):
    _burst(db, 200, ago=25)
    assert _visit(db, "next_day") is False


def test_the_same_token_does_not_count_for_itself(db):
    for _ in range(CRAWL_TOKENS + 5):
        _visit(db, "same", ago=1)
    assert _visit(db, "same") is False


def test_a_true_set_by_the_page_stays_true(db):
    assert _visit(db, "bot", schermo="mobile", automatico=True) is True


def test_the_trigger_function_is_not_callable_by_the_public_roles(db):
    with db.cursor() as cur:
        cur.execute("select has_function_privilege('anon', 'public.claim_visite_burst()', 'execute'), "
                    "has_function_privilege('authenticated', 'public.claim_visite_burst()', 'execute')")
        assert cur.fetchone() == (False, False)


def test_the_tools_query_is_read_only():
    from pathlib import Path
    sql = (Path(__file__).resolve().parent.parent / "tools" / "claim" / "ops3_crawler_2026_10_25.sql").read_text()
    body = "\n".join(l for l in sql.splitlines() if not l.lstrip().startswith("--")).lower()
    for word in ("insert", "update", "delete", "drop", "alter", "truncate", "create"):
        assert f"{word} " not in body
