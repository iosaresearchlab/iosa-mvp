"""DIG-1 (01/10/2026): the weekly digest draft keeps the wording rules and
never computes a figure across baseline bands.

tools/weekly_digest.py is read-only and writes a draft for the owner; these
tests run its pure part (build) on fixtures shaped like a real week.
"""

import importlib.util
import re
from pathlib import Path

import pytest

import main as backend_main

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("weekly_digest", ROOT / "tools" / "weekly_digest.py")
wd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wd)

DAYS = [f"2026-09-{d:02d}" for d in range(24, 31)]          # 7 readings, week ends Wed 30/09


def rec(i, baseline, vpi, day="2026-09-28", status="CLOSED", days=2, title="a long video",
        rule="standard", certain=True, handle=None):
    return {"author_handle": handle or f"@ch{i}", "author_name": f"Channel {i}", "content_text": title,
            "post_url": f"https://www.youtube.com/watch?v=v{i:010d}", "baseline_score": baseline,
            "baseline_rule": rule, "status": status, "days_charting": days if status == "CLOSED" else None,
            "day_n": days, "vpi_max": (vpi * 1.5 if vpi is not None else None) if status == "CLOSED" else None,
            "views_max": 123_456, "entered_on": day, "left_on": "2026-09-30" if status == "CLOSED" else None,
            "entry_certain": certain, "day1_vpi": vpi, "day1_views": 100_000}


def week():
    rs = []
    # week 40 -> rotation index 40 % 5 = 0 -> band "<100" has fewer than 3, moves to "100-1k"
    rs += [rec(1, 50, 900.0)]
    rs += [rec(10 + i, 500, v) for i, v in enumerate([120.0, 80.0, 60.0, 30.0])]
    rs += [rec(20 + i, 5_000, v) for i, v in enumerate([40.0, 12.0, 9.0])]
    rs += [rec(30 + i, 500_000, v, days=1) for i, v in enumerate([0.8, 0.5, 0.6, 0.4, 0.7])]
    rs += [rec(40, None, None, rule="not_computable", days=1)]
    rs += [rec(41, 500, 99.0, title="🔴LIVE | the full match", status="ACTIVE")]
    rs += [rec(50, 500, 999.0, certain=False)]                      # gap: out of the ranking
    rs += [rec(60, 500, 5000.0, day="2026-09-20")]                  # last week: out
    return rs


def test_bands_are_the_backend_bands():
    assert wd.BANDS == backend_main.BASELINE_BANDS


def test_the_ranking_is_one_band_stated_with_n_and_rotates():
    d = wd.build(DAYS, week())
    assert d["band_rotation"] == "<100" and d["band_moved"] and d["band"] == "100-1k"
    assert d["n_band"] == 5                                             # 4 + the flagged live one, certain only
    assert [t["band"] for t in d["top"]] == ["100-1k"] * 3
    assert [t["day1_vpi"] for t in d["top"]] == [120.0, 99.0, 80.0]
    # every ranked record is from the featured band: no cross-band ranking
    for t in d["top"]:
        assert wd.band_of(next(r for r in week() if r["author_handle"] == t["handle"])["baseline_score"]) == d["band"]
    assert "100 to 1,000 views" in d["script"][1][2] and "5 videos" in d["script"][1][2]


def test_rotation_changes_with_the_week():
    other = [f"2026-10-{d:02d}" for d in range(1, 8)]                # week 41 -> "100-1k"
    rs = [dict(r, entered_on="2026-10-03") for r in week()]
    assert wd.build(other, rs)["band_rotation"] == "100-1k"


def test_position_one_carries_the_three_figures_together_when_closed():
    d = wd.build(DAYS, week())
    one = d["script"][3][2]
    assert "highest VPI observed of 180x, 123,456 views and 2 days in Most Popular" in one
    card = d["cards"][2]
    assert [k for k, _ in card["rows"]][-3:] == ["highest VPI observed", "views", "days in Most Popular"]


def test_position_one_still_charting_gets_no_award():
    rs = [r for r in week() if r["author_handle"] != "@ch10"] + [rec(10, 500, 120.0, status="ACTIVE", days=3)]
    d = wd.build(DAYS, rs)
    assert "still in Most Popular, day 3" in d["script"][3][2] and "highest VPI observed" not in d["script"][3][2]


def test_limit_line_is_per_band_never_pooled():
    d = wd.build(DAYS, week())
    assert d["limit_figure"]["kind"] == "band medians"
    assert set(d["limit_figure"]) == {"kind", "100-1k", ">=100k"}
    assert d["limit_figure"][">=100k"] == 0.6                          # the median of that band alone
    pooled = __import__("statistics").median([r["day1_vpi"] for r in week() if r["day1_vpi"] is not None
                                               and r["entry_certain"] and r["entered_on"] in DAYS])
    assert wd.fmt_vpi(pooled) not in d["limit"]


def test_limit_line_without_baseline_when_the_band_is_large():
    rs = [r for r in week() if r["baseline_score"] != 50 and r["baseline_score"] != 500
          and r["baseline_score"] != 5_000]
    d = wd.build(DAYS, rs)
    assert d["band"] == ">=100k" and d["limit_figure"]["kind"] == "share without a computable baseline"
    assert "1 of the week's 6 long-form videos (17%) have no VPI" in d["limit"]


def test_hook_counts_first_observed_and_single_reading():
    d = wd.build(DAYS, week())
    assert d["records"] == 16 and d["single_reading"] == 6
    assert d["script"][0][2].startswith("This week we first observed 16 long-form videos")


def test_flags_never_drop():
    d = wd.build(DAYS, week())
    flagged = {f["handle"]: f["flags"] for f in d["flagged"]}
    assert "likely live stream or replay (title)" in flagged["@ch41"]
    assert any(t["handle"] == "@ch41" for t in d["top"])                # flagged, still ranked
    assert any("baseline under 1,000" in f for f in flagged["@ch10"])


@pytest.mark.parametrize("bad", [
    "These 3 channels broke the algorithm", "a mind-blowing 900x", "the video entered Most Popular",
    "Subscribe for next week", "Drop your handle in the comments", "YouTube Shorts are back",
    "the biggest anomaly", "an age-adjusted score", "trending now",
])
def test_the_wording_check_catches_what_it_is_for(bad):
    assert wd.check_wording(bad)


def test_the_draft_keeps_every_rule():
    d = wd.build(DAYS, week())
    for text in wd.all_texts(d):
        assert wd.check_wording(text) is None, text
    assert "not age-adjusted" in " ".join(wd.all_texts(d))
    assert d["script"][-1][2].endswith("iosaresearch.org.")              # the close, no call to action


def test_a_draft_that_breaks_a_rule_is_not_written(monkeypatch):
    monkeypatch.setattr(wd, "SITE", "iosaresearch.org — subscribe")
    with pytest.raises(wd.WordingError):
        wd.build(DAYS, week())


def test_x_post_within_280_with_the_link_as_23():
    d = wd.build(DAYS, week())
    assert d["x_length"] <= 280 and "https://iosaresearch.org" in d["x_post"]
    assert wd.x_length("a https://iosaresearch.org/some/very/long/path") == 2 + 23
    long = [dict(r, author_handle="@" + "x" * 200) if r["author_handle"] == "@ch10" else r for r in week()]
    assert wd.build(DAYS, long)["x_length"] <= 280


def test_voiceover_is_about_55_seconds():
    d = wd.build(DAYS, week())
    assert d["script"][0][0] == "0:00" and d["script"][-1][1] == "0:55"
    assert 100 <= d["script_words"] <= 160                              # ~2.5 words a second


def test_the_tool_is_read_only_and_outside_the_backend():
    src = (ROOT / "tools" / "weekly_digest.py").read_text(encoding="utf-8")
    assert not re.search(r"requests\.(post|patch|put|delete)\(", src)      # GET only
    assert "googleapis" not in src and "YOUTUBE_API_KEY" not in src         # no YouTube quota
    assert not (ROOT / "backend" / "weekly_digest.py").exists()


def test_nothing_before_the_series_start(monkeypatch):
    monkeypatch.setattr(wd, "INDEX_START_DATE", "2026-09-27")
    rs = week() + [rec(70, 500, 9999.0, day="2026-09-26")]
    d = wd.build(["2026-09-25", "2026-09-26"] + DAYS[3:], rs)
    assert d["week"][0] == "2026-09-27" and all(t["day1_vpi"] != 9999.0 for t in d["top"])
    with pytest.raises(ValueError):
        wd.build(["2026-09-25", "2026-09-26"], rs)
