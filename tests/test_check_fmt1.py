"""tests/check_fmt1.py: the FMT-1 step-3 criteria on fixtures, with a
negative control for each condition."""

import pytest

from tests.check_fmt1 import evaluate


def rec(fmt="LONG", dur=600, shape="wide", rule="youtube_shape", pub="2026-10-01T10:00:00Z"):
    return {"format": fmt, "duration_s": dur, "shape": shape, "format_rule": rule,
            "created_at": pub, "was_live": False}


GOOD = [rec(), rec(dur=120, shape="wide"), rec(dur=900, shape=None),
        rec(dur=90, shape="vertical", pub="2024-10-14T22:00:00Z")]


def test_a_good_day_passes():
    verdict, failed, counts = evaluate(GOOD)
    assert verdict == "PASS" and failed == [] and counts["long_up_to_180_wide"] == 1


@pytest.mark.parametrize("bad, condition", [
    ([rec(rule="duration_180")], "every record format_rule = youtube_shape"),
    ([rec(dur=None)], "every record has duration_s"),
    ([rec(dur=170, shape=None)], "every record <= 180 s has a shape"),
    ([rec(dur=120, shape="vertical")], "none <= 180 s not wide, except before 15/10/2024 and over 60 s"),
    ([rec(dur=120, shape="square")], "none <= 180 s not wide, except before 15/10/2024 and over 60 s"),
    ([rec(dur=60, shape="vertical", pub="2024-10-14T22:00:00Z")],
     "none <= 180 s not wide, except before 15/10/2024 and over 60 s"),
    ([rec(fmt="SHORT", dur=40, shape="vertical")], "no record other than long-form"),
])
def test_each_condition_fails_on_its_own(bad, condition):
    verdict, failed, _ = evaluate(GOOD + bad)
    assert verdict == "FAIL" and condition in failed


def test_no_wide_short_duration_record_fails():
    verdict, failed, _ = evaluate([rec()])
    assert verdict == "FAIL" and failed == ["at least one long-form <= 180 s and wide"]


def test_no_record_fails():
    assert "records exist" in evaluate([])[1]
