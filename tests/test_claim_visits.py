"""APP-12 (01/10/2026): a visit to a v1 claim page is recorded again.

The claim page inserts into claim_visite (and claim_eventi) with the public
key, with the post_id of the record it resolved. Since the v1 records moved
to posts_v1 (25/09), that id is not in posts and the foreign key to posts
refused every insert: claim_visite has no row after 24/09/2026 although
Vercel counts claim page views. The insert error was swallowed by the page.
"""

import uuid


def _insert_as_anon(db, table, post_id):
    with db.cursor() as cur:
        cur.execute(f"grant insert on public.{table} to anon")
        cur.execute("savepoint s")
        cur.execute("set local role anon")
        cur.execute(f"insert into {table} (claim_token, post_id) values ('tok_v1', %s)", (post_id,))
        cur.execute("reset role")
        cur.execute(f"select count(*) from {table} where claim_token = 'tok_v1'")
        return cur.fetchone()[0]


def test_a_visit_with_a_v1_record_id_is_accepted(db):
    with db.cursor() as cur:
        cur.execute("select id from posts_v1 limit 1")
        v1_id = cur.fetchone()[0]
        cur.execute("select count(*) from posts where id = %s", (v1_id,))
        assert cur.fetchone() == (0,)          # the id the page sends is not in posts
    assert _insert_as_anon(db, "claim_visite", v1_id) == 1
    assert _insert_as_anon(db, "claim_eventi", uuid.uuid4()) == 1


def test_the_nulled_visits_get_their_record_back(db):
    with db.cursor() as cur:
        cur.execute("select count(*) from claim_visite where post_id is null")
        assert cur.fetchone() == (0,)
        cur.execute("select count(*) from claim_visite v join posts_v1 a on a.id = v.post_id "
                    "and a.claim_token = v.claim_token")
        assert cur.fetchone()[0] >= 1
