"""GATE-0 decisions on posts: legacy writers and the two record states.

Runs every migration verbatim (the ``db`` fixture in conftest.py).
Source: docs/02-technical-specification.md section 3.2.
"""

import pytest

psycopg = pytest.importorskip("psycopg")


def insert(conn, **cols):
    cols.setdefault("external_post_id", "vid")
    names = ", ".join(cols)
    marks = ", ".join(["%s"] * len(cols))
    with conn.cursor() as cur:
        cur.execute(
            f"insert into posts ({names}) values ({marks}) returning method_version",
            list(cols.values()),
        )
        return cur.fetchone()[0]


def rejected(conn, **cols):
    """True if the row is refused by posts_baseline_state."""
    try:
        with conn.transaction():  # savepoint: the test's transaction survives
            insert(conn, **cols)
    except psycopg.errors.CheckViolation as e:
        assert "posts_baseline_state" in str(e)
        return True
    return False


def test_a_legacy_writer_gets_v1_by_default(db):
    assert insert(db, baseline_score=900, vpi_ratio=2.0, vpi_level=3) == "v1"


LEVEL = dict(vpi_level=3, vpi_level_name="Lvl 3 - Rising", vpi_color="#0099FF")
NO_LEVEL = dict(vpi_level=None, vpi_level_name=None, vpi_color=None)


def test_v2_standard_record_is_accepted(db):
    assert not rejected(db, method_version="v2", baseline_rule="standard",
                        baseline_score=900, vpi_ratio=2.0, **LEVEL)


def test_v2_not_computable_record_without_baseline_or_vpi_is_accepted(db):
    assert not rejected(db, method_version="v2", baseline_rule="not_computable",
                        baseline_score=None, vpi_ratio=None, **NO_LEVEL)


@pytest.mark.parametrize("missing", ["vpi_level", "vpi_level_name", "vpi_color"])
def test_v2_standard_without_its_level_fields_is_rejected(db, missing):
    assert rejected(db, method_version="v2", baseline_rule="standard",
                    baseline_score=900, vpi_ratio=2.0, **{**LEVEL, missing: None})


@pytest.mark.parametrize("present", ["vpi_level", "vpi_level_name", "vpi_color"])
def test_v2_not_computable_with_any_level_field_is_rejected(db, present):
    assert rejected(db, method_version="v2", baseline_rule="not_computable",
                    baseline_score=None, vpi_ratio=None, **{**NO_LEVEL, present: LEVEL[present]})


def test_a_channel_without_a_handle_can_be_recorded(db):
    assert not rejected(db, method_version="v2", baseline_rule="not_computable",
                        baseline_score=None, vpi_ratio=None, author_handle=None, **NO_LEVEL)


def test_v2_record_with_no_rule_is_rejected(db):
    # The case the bare constraint lets through: it evaluates to NULL.
    assert rejected(db, method_version="v2", baseline_rule=None,
                    baseline_score=900, vpi_ratio=2.0)


def test_v2_standard_without_vpi_is_rejected(db):
    assert rejected(db, method_version="v2", baseline_rule="standard",
                    baseline_score=900, vpi_ratio=None)


def test_v2_standard_without_baseline_is_rejected(db):
    assert rejected(db, method_version="v2", baseline_rule="standard",
                    baseline_score=None, vpi_ratio=2.0)


def test_v2_not_computable_with_a_baseline_is_rejected(db):
    assert rejected(db, method_version="v2", baseline_rule="not_computable",
                    baseline_score=900, vpi_ratio=None)


def test_v2_not_computable_with_a_vpi_is_rejected(db):
    assert rejected(db, method_version="v2", baseline_rule="not_computable",
                    baseline_score=None, vpi_ratio=2.0)


def test_unknown_rule_is_rejected(db):
    assert rejected(db, method_version="v2", baseline_rule="fallback",
                    baseline_score=900, vpi_ratio=2.0)


def test_null_method_version_is_not_an_exemption(db):
    assert rejected(db, method_version=None, baseline_rule=None,
                    baseline_score=900, vpi_ratio=2.0)


def test_v1_archive_rows_are_exempt(db):
    assert not rejected(db, method_version="v1", baseline_rule=None,
                        baseline_score=None, vpi_ratio=None)


def test_the_v1_cron_trigger_is_switched_off(db):
    with db.cursor() as cur:
        cur.execute("select active from cron.job where jobname = 'ingestione-iosa'")
        assert cur.fetchone() == (False,)


def test_a_quota_stop_record_without_baseline_or_vpi_is_accepted(db):
    assert not rejected(db, method_version="v2", baseline_rule="quota_stop",
                        baseline_score=None, vpi_ratio=None, **NO_LEVEL)


def test_a_quota_stop_record_with_a_vpi_is_rejected(db):
    assert rejected(db, method_version="v2", baseline_rule="quota_stop",
                    baseline_score=900, vpi_ratio=2.0, **LEVEL)
