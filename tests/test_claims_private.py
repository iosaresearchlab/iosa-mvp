"""claims holds customers' names, emails and shipping addresses: never public.

Migration v2_claims_private (25/09/2026). RLS stays on, no policy lets the
API roles read, and anon/authenticated hold no privilege on the table.
"""


def test_no_policy_on_claims(db):
    with db.cursor() as cur:
        cur.execute("select policyname from pg_policies where schemaname = 'public' and tablename = 'claims'")
        assert cur.fetchall() == []
        cur.execute("select relrowsecurity from pg_class where oid = 'public.claims'::regclass")
        assert cur.fetchone() == (True,)


def test_api_roles_hold_no_privilege_on_claims(db):
    with db.cursor() as cur:
        for role in ("anon", "authenticated"):
            for priv in ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE"):
                cur.execute("select has_table_privilege(%s, 'public.claims', %s)", (role, priv))
                assert cur.fetchone() == (False,), (role, priv)


def test_anon_reads_nothing_from_claims(db):
    with db.cursor() as cur:
        cur.execute("insert into claims (customer_email, shipping_name) values ('a@example.invalid', 'A')")
        cur.execute("savepoint s")
        cur.execute("set local role anon")
        try:
            cur.execute("select customer_email from claims")
            leaked = cur.fetchall()
        except Exception as e:                 # permission denied is the expected answer
            leaked = type(e).__name__
        cur.execute("rollback to savepoint s")
        assert leaked in ([], "InsufficientPrivilege")
