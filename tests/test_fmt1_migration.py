"""FMT-1: the data part of migration v2_fmt1_youtube_shape, on PostgreSQL.

02 section 4.9; 08 FMT-1, closing check step 2. The schema part is applied by
the db fixture with every other migration; here its two UPDATE statements run
again on rows written as production holds them before FMT-1, and the result
is what step 2 checks in production.
"""

import json
import re
from pathlib import Path

import pytest

psycopg = pytest.importorskip("psycopg")

MIGRATION = next((Path(__file__).resolve().parent.parent / "supabase" / "migrations")
                 .glob("*_v2_fmt1_youtube_shape.sql"))


def _updates():
    sql = re.sub(r"--[^\n]*", "", MIGRATION.read_text(encoding="utf-8"))
    return [s.strip() for s in sql.split(";") if s.strip().lower().startswith("update")]


def _post(cur, vid, version, rule=None):
    cur.execute("""insert into posts (external_post_id, author_handle, method_version, format,
                     baseline_rule, format_rule)
                   values (%s, 'h', %s, 'LONG', %s, %s)""",
                (vid, version, "not_computable" if version == "v2" else None, rule))


def test_the_migration_has_exactly_the_two_data_updates_of_the_spec():
    ups = _updates()
    assert len(ups) == 2
    assert ups[0].startswith("update public.posts set format_rule = 'duration_180'")
    assert ups[1].startswith("update public.channel_inventory")


def test_step_2_every_v2_record_duration_180_and_no_inventory_short_left(db):
    items_a = {"s1": [1759300000, "SHORT"], "l1": [1759200000, "LONG"],
               "n1": [1759100000, "NONE"], "x1": [1759000000, None]}
    items_b = {"l2": [1759300000, "LONG"]}
    with db.cursor() as cur:
        _post(cur, "v2a", "v2")
        _post(cur, "v2b", "v2")
        _post(cur, "v2new", "v2", "youtube_shape")
        _post(cur, "v1a", "v1")
        cur.execute("insert into channel_inventory (channel_id, items) values ('UCa', %s), ('UCb', %s)",
                    (json.dumps(items_a), json.dumps(items_b)))
        for u in _updates():
            cur.execute(u)
        cur.execute("select external_post_id, format_rule from posts order by 1")
        assert cur.fetchall() == [("v1a", None), ("v2a", "duration_180"), ("v2b", "duration_180"),
                                  ("v2new", "youtube_shape")]
        # the closing check's query, verbatim
        cur.execute("select count(*) from channel_inventory, jsonb_each(items) e(k,v) where v->>1 = 'SHORT'")
        assert cur.fetchone() == (0,)
        cur.execute("select channel_id, items from channel_inventory order by 1")
        got = dict(cur.fetchall())
    assert got["UCa"] == {"s1": [1759300000, None], "l1": [1759200000, "LONG"],
                          "n1": [1759100000, "NONE"], "x1": [1759000000, None]}
    assert got["UCb"] == items_b
