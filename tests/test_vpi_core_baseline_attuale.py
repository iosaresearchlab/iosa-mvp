"""Characterisation of backend/vpi_core.py AS IT IS on 25 September 2026 (T-03).

These tests pin the current (v1) behaviour, including behaviour that the v2
protocol replaces. They are not a statement that it is correct: they exist so
that every later change to the measurement core shows up as a deliberate,
visible diff. When T-08 changes the baseline rule, the tests below marked
"v2 changes this" must fail and be rewritten in the same commit, citing
docs/01-methodology-protocol.md.

Each assertion message starts with PINS: and names the behaviour it fixes.

T-08 (25/09/2026): the v2 rule is vpi_core.baseline_v2() (tests/test_baseline.py).
baseline_from_samples() is kept unchanged for the v1 records, on its own frozen
floor V1_BASELINE_MIN_AGE_DAYS = 14, so the pins on it below still hold. The two
constant pins that v2 changed were rewritten, citing docs/01 section 2.
"""

import vpi_core as core


def _s(video_id, views, age_days):
    return {"video_id": video_id, "views": float(views), "age_days": age_days}


# ------------------------------------------------------------- constants

def test_constants_as_they_are():
    current = {
        "SHORT_MAX_SECONDS": 180,
        "CAMPAIGN_DAYS": 15,            # v2 changes this: renamed CLAIM_DAYS
        "BASELINE_MIN_AGE_DAYS": 7,     # v2, docs/01 section 2 (was 14 in v1)
        "V1_BASELINE_MIN_AGE_DAYS": 14, # the v1 floor, kept for v1 records
        "BASELINE_MAX_AGE_DAYS": 90,
        "MIN_BASELINE_SAMPLES": 5,
        "MIN_BASELINE_VIEWS": 500,
        "MIN_VPI_FOR_INGESTION": 1.0,   # v2 changes this: deleted
    }
    for name, value in current.items():
        assert getattr(core, name) == value, f"PINS: {name} == {value}"


def test_v2_baseline_constants_and_what_does_not_exist_yet():
    assert (core.BASELINE_SAMPLES_MAX, core.BASELINE_PAGES_MAX) == (20, 3), \
        "PINS: v2 at most 20 samples, uploads read up to 3 pages (docs/01 section 2, T-08)"
    for name in ("SCALE_VERSION", "CLAIM_DAYS"):
        assert not hasattr(core, name), f"PINS: {name} not defined yet"


def test_scale_thresholds_as_they_are():
    pairs = tuple((t, lvl) for t, lvl, _, _ in core.VPI_SCALE)
    assert pairs == (
        (2500.0, 10), (1500.0, 9), (1000.0, 8), (250.0, 7), (100.0, 6),
        (50.0, 5), (25.0, 4), (10.0, 3), (5.0, 2), (1.5, 1),
    ), "PINS: the owner's thresholds (25/09/2026), highest first; below 1.5x no level"


# ------------------------------------------------ baseline_from_samples: window

def test_age_equal_to_min_age_counts_as_mature():
    samples = [_s(f"m{i}", 1000, 14) for i in range(5)] + [_s("f", 1, 13.99)]
    assert core.baseline_from_samples(samples) == (1000.0, 5), \
        "PINS: age == 14 days is mature (>=), 13.99 is not"


def test_age_equal_to_max_age_is_inside_the_window():
    samples = [_s(f"a{i}", 100, 90) for i in range(5)] + [_s("b", 10**6, 90.001)]
    assert core.baseline_from_samples(samples) == (100.0, 5), \
        "PINS: age == 90 days is kept, 90.001 is dropped (> 90 excluded)"


def test_window_is_measured_from_now_not_from_the_measured_video():
    # Nothing in the v1 signature knows the measured video's publishedAt:
    # sample ages are relative to "now" (optionally shifted by giorni_indietro).
    samples = [_s(f"v{i}", 100, 30) for i in range(5)]
    assert core.baseline_from_samples(samples, giorni_indietro=0) == (100.0, 5), \
        "PINS: v2 changes this - window anchored to now, not to publishedAt"


def test_giorni_indietro_shifts_ages_and_drops_later_videos():
    later = [_s(f"l{i}", 5, 9.99) for i in range(5)]       # age -0.01 once shifted
    earlier = [_s(f"e{i}", 700, 25) for i in range(5)]     # age 15 once shifted
    assert core.baseline_from_samples(later + earlier, giorni_indietro=10) == (700.0, 5), \
        "PINS: age - giorni_indietro < 0 is excluded; maturity judged on the shifted age"


# ------------------------------------------- baseline_from_samples: which sample

def test_mature_only_when_at_least_five_mature():
    mature = [_s(f"m{i}", 1000, 30) for i in range(5)]
    fresh = [_s(f"f{i}", 10, 2) for i in range(10)]
    assert core.baseline_from_samples(mature + fresh) == (1000.0, 5), \
        "PINS: with >= 5 mature samples, fresh ones are ignored"


def test_fallback_to_all_recent_when_fewer_than_five_mature():
    mature = [_s(f"m{i}", 1000, 30) for i in range(4)]
    fresh = [_s(f"f{i}", 10, 2) for i in range(10)]
    assert core.baseline_from_samples(mature + fresh) == (10.0, 14), \
        "PINS: v2 changes this - fewer than 5 mature widens to every recent video (mature included)"


def test_no_cap_on_the_number_of_samples():
    samples = [_s(f"v{i}", i, 30) for i in range(1, 31)]
    assert core.baseline_from_samples(samples) == (15.5, 30), \
        "PINS: v2 changes this - all 30 samples used, no cap at 20, no even spread"


def test_median_of_an_even_count_is_the_mean_of_the_middle_two():
    samples = [_s(f"v{i}", v, 30) for i, v in enumerate([10, 20, 30, 40, 50, 60])]
    assert core.baseline_from_samples(samples) == (35.0, 6), \
        "PINS: statistics.median on an even count"


def test_zero_median_returns_none_with_the_count():
    samples = [_s(f"v{i}", 0, 30) for i in range(5)]
    assert core.baseline_from_samples(samples) == (None, 5), \
        "PINS: median <= 0 -> baseline None, sample count still reported"


def test_returns_a_pair_without_rule_span_or_ids():
    out = core.baseline_from_samples([_s(f"v{i}", 100, 30) for i in range(5)])
    assert isinstance(out, tuple) and len(out) == 2, \
        "PINS: v2 changes this - (baseline, n) only; no baseline_rule, span or ids"


def test_exclusion_matches_on_video_id_only():
    samples = [_s("x", 10**6, 30)] + [_s(f"v{i}", 100, 30) for i in range(5)]
    assert core.baseline_from_samples(samples, exclude_video_id="X") == (100.0, 6), \
        "PINS: exclude_video_id is compared exactly (case-sensitive)"


# ------------------------------------------------ ratio, level, rounding

def test_ratio_with_non_positive_baseline_is_one():
    assert core.calculate_vpi_ratio(500, -3) == 1.0, \
        "PINS: baseline <= 0 -> VPI 1.0, not an error and not null"


def test_ratio_with_missing_views_is_zero():
    assert core.calculate_vpi_ratio(None, 50) == 0.0, \
        "PINS: views None counts as 0"


def test_level_of_an_unreadable_value_is_none():
    assert core.get_vpi_metadata("n/a") == (None, None, None), \
        "PINS: unparseable VPI -> no level (was level 1 before 25/09/2026)"


def test_level_of_a_negative_value_is_none():
    assert core.get_vpi_metadata(-2)[0] is None, \
        "PINS: below 1.5x no level (was level 1 before 25/09/2026)"


def test_round_vpi_one_decimal_and_fallback():
    assert core.round_vpi(3.14159) == 3.1, "PINS: one decimal"
    assert core.round_vpi("x") == 1.0, "PINS: unreadable -> 1.0"


# ------------------------------------------------ the rule of this file

def test_every_assertion_in_this_file_names_what_it_pins():
    import ast
    from pathlib import Path
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    unnamed = [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Assert)
               and "PINS:" not in (ast.unparse(n.msg) if n.msg else "")]
    assert not unnamed, f"PINS: every assert carries a PINS: message; missing at lines {unnamed}"
