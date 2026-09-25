"""The Stripe webhook: the order state lands, and a repeated event places no
second order. Real PostgreSQL (every migration), the Stripe signature check
and the Printify call replaced.

Before the fix the webhook wrote printify_product_id with the anon key;
test_the_anon_key_cannot_write_posts pins why that write was lost.
"""

import pytest
from fastapi.testclient import TestClient

import main
from tests.pg_client import PgClient

SESSION = "cs_test_iosa_1"


def v2_post(db, token):
    with db.cursor() as cur:
        cur.execute("insert into posts (external_post_id, author_handle, baseline_score, vpi_ratio, "
                    "vpi_level, vpi_level_name, vpi_color, method_version, baseline_rule, claim_token) "
                    "values ('vid', '@c', 100, 6, 2, 'L2', '#111', 'v2', 'standard', %s) returning id",
                    (token,))
        return cur.fetchone()[0]


def event(session_id=SESSION, token="tok-v2"):
    return {"type": "checkout.session.completed",
            "data": {"object": {"id": session_id, "metadata": {"claim_token": token},
                                "customer_details": {"name": "A B", "email": "a@example.invalid",
                                                     "address": {"country": "IT"}}}}}


@pytest.fixture
def hook(db, monkeypatch):
    client = PgClient(db)
    orders = []
    monkeypatch.setattr(main, "supabase", client)
    monkeypatch.setattr(main, "supabase_service", client)
    monkeypatch.setattr(main, "STRIPE_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setattr(main.stripe.Webhook, "construct_event", lambda payload, sig, secret: payload_event[0])
    payload_event = [event()]

    def fulfil(**kw):
        orders.append(kw["external_ref"])
        return {"product_id": f"prod-{len(orders)}", "variant_id": 1, "order_id": f"ord-{len(orders)}"}
    monkeypatch.setattr(main, "fulfill_trophy_order", fulfil)
    return TestClient(main.app), db, orders, payload_event


def post(client):
    return client.post("/api/webhooks/stripe", content=b"{}", headers={"stripe-signature": "t"}).json()


def test_the_order_state_lands_and_a_repeat_places_no_second_order(hook):
    client, db, orders, _ = hook
    v2_post(db, "tok-v2")
    assert post(client) == {"status": "success"}
    assert post(client) == {"status": "already_fulfilled"}
    assert orders == [SESSION]
    with db.cursor() as cur:
        cur.execute("select printify_product_id from posts where claim_token = 'tok-v2'")
        assert cur.fetchone() == ("prod-1",)
        cur.execute("select status, customer_email, shipping_address from claims")
        assert cur.fetchall() == [("FULFILLED", None, None)]


def test_a_different_session_is_a_new_order(hook):
    client, db, orders, payload = hook
    v2_post(db, "tok-v2")
    post(client)
    payload[0] = event(session_id="cs_test_iosa_2")
    assert post(client) == {"status": "success"}
    assert orders == [SESSION, "cs_test_iosa_2"]


def test_a_v1_token_orders_without_writing_the_archive(hook):
    client, db, orders, payload = hook
    with db.cursor() as cur:
        cur.execute("select claim_token, md5(to_jsonb(v)::text) from posts_v1 v where external_post_id = 'v1_old_a'")
        token, before = cur.fetchone()
    payload[0] = event(token=token)
    assert post(client) == {"status": "success"}
    assert post(client) == {"status": "already_fulfilled"}
    assert len(orders) == 1
    with db.cursor() as cur:
        cur.execute("select md5(to_jsonb(v)::text) from posts_v1 v where claim_token = %s", (token,))
        assert cur.fetchone() == (before,)
        cur.execute("select status, post_id from claims")
        assert cur.fetchall() == [("FULFILLED", None)]


def test_a_failed_order_is_recorded_and_not_retried(hook, monkeypatch):
    client, db, orders, _ = hook
    v2_post(db, "tok-v2")
    monkeypatch.setattr(main, "fulfill_trophy_order", lambda **kw: (_ for _ in ()).throw(ValueError("no")))
    assert post(client)["status"] == "error_recorded"
    assert post(client) == {"status": "already_fulfilled"}
    with db.cursor() as cur:
        cur.execute("select status from claims")
        assert cur.fetchall() == [("FAILED",)]
        cur.execute("select printify_product_id from posts where claim_token = 'tok-v2'")
        assert cur.fetchone() == ("FAILED_ORDER_ERROR",)


def test_without_the_service_client_nothing_is_ordered(hook, monkeypatch):
    client, db, orders, _ = hook
    monkeypatch.setattr(main, "supabase_service", None)
    assert post(client)["status"] == "error_recorded"
    assert orders == []


def test_the_anon_key_cannot_write_posts(db):
    """Why the old write was lost: posts has no UPDATE policy for the API roles."""
    v2_post(db, "tok-v2")
    with db.cursor() as cur:
        cur.execute("alter table posts enable row level security")   # as in production
        cur.execute("grant select, update on posts to anon")
        cur.execute("savepoint s")
        cur.execute("set local role anon")
        cur.execute("update posts set printify_product_id = 'x' where claim_token = 'tok-v2'")
        n = cur.rowcount
        cur.execute("rollback to savepoint s")
        assert n == 0
