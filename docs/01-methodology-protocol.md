# VPI Measurement Protocol — v2

**Status: approved 23 September 2026.** Supersedes v1 of 21 September
(fixed-age measurement at T=7 days: abandoned).

Every figure here was measured against the official YouTube Data API v3.
Sources in `03-Most Popular-population-measurements.md`.

> **Naming.** YouTube retired the *Trending* page on 22 July 2025. The
> endpoint we read is `videos.list?chart=mostPopular`, so throughout this
> documentation and in public material the population is called **YouTube's
> Most Popular charts**, never "trending". The word survives only in the
> filename `03-trending-population-measurements.md` and in quotations from
> earlier material.

---

## 1. What we measure

```
VPI = video views / channel baseline, within the same format
```

**The comparison is always within format.** A Short is measured against the
channel's median for Shorts; a long-form video against the median for
long-form. The two never mix: on almost every channel they have different
view distributions, so a mixed baseline would measure the channel's
publishing mix rather than the video's performance.

The population:

> **Videos — Shorts (≤180s) and long-form — FIRST OBSERVED in YouTube's
> Most Popular charts, across 34 countries and 12 categories, starting from our
> day 1.**

**The series begins on day 1.** The index starts on `YYYY-MM-DD` (to be fixed
at the first successful day-1 run — T-16). Everything present in YouTube's
Most Popular charts before that date is outside the measurement: we did not
observe it arrive, so we do not measure it.

The day-0 snapshot is retained permanently as the reference state of the
population at the start, and produces no records for that period. A day-0
video becomes eligible only once we have observed it absent from all charts;
if it later returns, that return is an entry we did observe and is measured
like any other. Its view count is cumulative and therefore includes the
earlier period, which is one reason `age_at_first_obs_days` is published
alongside every ranking.

*(The start date is a placeholder until T-16 closes; it is replaced in the
commit that records the day-1 audit, T-17. A reader who cannot tell what
period the index covers cannot judge any figure in it.)*

**First observed, not "entered".** YouTube exposes no entry timestamp:
verified by pulling every available API part — the only date present is
`publishedAt`, the video's publication. What we observe is that a video is
present in today's snapshot and absent from the previous one. With one
reading a day that is not the same event as entry into the chart:

- a video that enters and leaves between two readings is never observed;
- a video that enters at 03:00 and one that enters at 23:58 are both
  recorded on the same day;
- after a missed reading, a video first seen may have entered during the
  gap (see §4).

The population is therefore defined by **our observation**, and the
documentation says so everywhere. This index is not a census of chart
entrants and must never be described as one. *(Wording corrected 24/09/2026
after external review.)*

---

## 2. The baseline — one rule

> **Median view count of videos from the same channel and the same format,
> published between 7 and 90 days before the measured video was published,
> at least 5 of them, at most 20 spread evenly across the window.**

**Before the measured video's own publication — not before the measurement.**
This was corrected on 25/09/2026 after external review. Anchoring the window
to the measurement date meant that a video first observed at, say, 10 days of
age had baseline videos published *after it*, during its own breakout: the
denominator absorbed part of the event it was supposed to precede. 27% of
charting Shorts are 7 days old or more when we first see them, so this was
not a corner case. Anchoring to `publishedAt` makes the baseline genuinely
**pre-event**, and costs nothing.

**One rule for every record.** There are no fallback rules that widen the
window when data is scarce: two records computed over different windows
would be two different estimators placed on the same scale.

### Why 7 days and not 14

The maturity floor used to be 14 days. Measured on 220 channels:

| Window | Channels with ≥5 samples | Median baseline shift |
|---|---|---|
| 14-90 days | 75.9% | — |
| 10-90 days | 84.1% | ±0.0% |
| **7-90 days** | **88.6%** | **±0.0%** |
| 5-90 days | 94.1% | ±0.0% |

Lowering the floor does not move the **central value** of the baseline: the
median ratio is exactly 1.000. It widens per-channel dispersion (p10 moves
from 0.85 to 0.78). A Short collects most of its views in the first days, so
by day 7 it has essentially plateaued.

This is a sensitivity result, not a proof that no bias exists: it does not
rule out systematic differences inside subgroups or in the tails, and the
effect on individual level assignments has not been measured. The decision
rests on the coverage gain plus the absence of a central shift.

### Why 19% of channels had no baseline

Not channels that publish rarely — **channels that publish too much.**
`playlistItems` returns only the 50 most recent uploads, and for a channel
posting 5 videos a day all 50 fall inside 14 days. Verified: 41 cases
out of 42.

**Countermeasure: pagination.** If the first 50 uploads do not cover the
window, request the next page, up to 3 pages. This is not a different rule —
it is the same rule with complete data.

If after 3 pages there are still fewer than 5 samples, **the record still
exists**, with a null `vpi_ratio` and `baseline_rule = not_computable`,
counted in the daily run report. Nobody is excluded from the population: we
state that for that video the ratio cannot be computed.

### Other criteria

- **Median, not mean**: a previous breakout on the channel must not inflate
  the denominator.
- **If more than 20 videos fall in the window, take 20 spread evenly across
  it**, not the 20 most recent: the most recent are also the least mature,
  so they would lower the denominator and inflate the VPI.
- **The measured video is excluded from its own baseline.**
- Every record carries `baseline_samples`, `baseline_rule`, the span covered
  in days, and **the IDs of the videos composing the baseline**.

---

## 3. Frozen, and why

The baseline is computed **once, when the video enters the chart, and stays
that way forever**.

This is not a budget decision. The denominator must be a **pre-event**
measurement: when a video explodes it lifts the rest of the channel, and
those videos enter the baseline window days later. The denominator would
rise because of the very event the numerator measures.

The counter-argument is real: if a video stays in the chart for 20 days, the
baseline is 20 days stale.

**That is why we store the IDs of the baseline videos.** In three weeks we
compare baseline-at-entry against baseline-at-exit for the same channels: if
the shift correlates with the video's VPI, spillover is demonstrated and
freezing is correct. If it does not correlate, updating is harmless and we
switch. **The choice becomes a result, not an opinion.**

| | |
|---|---|
| Baseline | **frozen** at first sighting |
| Views | **updated daily** while the video is in the chart |
| VPI | recomputed daily: today's views / frozen baseline |
| The record | permanent, never deleted, never expires |

---

## 4. The daily procedure

One reading per day, at **23:59 UTC**.

*(The YouTube quota resets at midnight Pacific. 23:59 UTC is 16:59 Pacific,
mid quota-day: no risk of straddling the reset. Fixed UTC hour year-round —
a time that shifts with daylight saving is not a method parameter.)*

### Day 0 — snapshot only

Read all 448 charts and store every ID. **Nothing is ingested, no baseline
is computed.** Cost: 1,486 units.

Videos already in the chart on day 0 do not enter the index while they
remain in it: we could not say when they entered. **Day 0's snapshot is
retained permanently as the reference state of the population**; it never
enters the metrics. **A day-0 video becomes eligible again only once we have
observed it absent from all charts**: if it later returns, we observed that
entry, and it is recorded like any other. *(Made explicit 25/09/2026. No
separate exclusion list is kept: the reference for every day is the last
complete reading, so a day-0 video still charting is in the reference
snapshot and excluded by the ordinary test, and one that leaves and returns
is an entry we genuinely observed.)*

### Day 1 onward

1. Read the 448 charts. View counts arrive **free** in the same call:
   `part=statistics` costs no extra quota.
2. Store the complete snapshot of IDs, **including videos we do not
   ingest**. Without it, "absent yesterday" is not computable tomorrow.
3. **New entries** = present today, absent yesterday, never seen before →
   baseline computed and frozen → record written.
4. **Already tracked and still charting** → views updated, today's VPI
   recomputed. Zero cost.
5. **Gone** → record closed with `left_on`, only after a complete reading.
   Stays in the database forever.
6. **Re-entries** → no new record, no baseline recomputation.

**If a day's reading is missed, entry status becomes indeterminate.** The
comparison still runs against the most recent **complete** reading rather
than "yesterday" by definition, but a video first seen after a gap cannot be
called a new entrant: it may have entered and been present throughout the
gap. Such records are written and tracked normally, carrying
`entry_certain = false` and the size of the gap, and they are excluded from
every statistic that depends on the entry date.

**A gap never manufactures an entry event.**

**A partial reading observes presence but not absence: it can produce entries
and never exits, and it cannot serve as the reference snapshot for the
following day.** *(25/09/2026.)*

### 4.1 The published value and the record lifecycle

VPI is **not a single scalar read at an unspecified moment**. It is a
trajectory with a declared closing rule.

| Phase | What happens | What the public sees |
|---|---|---|
| Day 1 in chart | baseline computed and frozen, first VPI | "In Most Popular, day 1 — currently 3.2x the channel median. Measurement in progress." |
| Days 2..n | views updated, VPI recomputed, no baseline change | the current value and the day count; **no award is issued** |
| Exit | record closed, `left_on` and `days_charting` written | "In Most Popular for 4 days, peak VPI 3.5x, 1.4M views. The plaque is now available." |

**The published value is the highest VPI observed during the record's life**,
alongside the view count and the number of days in Most Popular. The three
always travel together, on the plaque and in the API.

The earlier claim that "the exit value is the maximum by construction" is
**withdrawn**: it assumed view counts never decrease, and YouTube removes
views on audit, so a daily series can fall. That is also why the maximum,
not the exit value, is the published figure — a downward revision by YouTube
after the peak is not a demerit of the video. `vpi_max` and `vpi_max_on` are
**stored as observed**, never inferred.

**What that number claims, stated exactly:**

> During the period in which we observed this video in YouTube's Most
> Popular charts, it reached at its peak N times the median view count of
> the same channel's videos in the same format published between 7 and 90
> days before **this video was published**.

It does **not** claim to be independent of the video's age.

The days available to claim the plaque (`CLAIM_DAYS`) are an outreach
parameter counted from first observation. They do not touch the measurement.

### 4.2 Comparability between records

A single record's value is well defined. **Two records are not automatically
comparable**, because the numerator is cumulative while the denominator is
frozen: a video observed for 12 days has had six times the accumulation
opportunity of one observed for 2 days.

**The comparison rule:**

> Cross-video comparisons are made at **day 1** — the first day the video was
> observed in a chart.

Day 1 is the only index that needs no correction and costs nothing: **every
record has a day-1 reading by construction**, since we read the video the day
we first see it. From day 2 onward a comparison would silently restrict
itself to the videos that stayed in the charts long enough to have that
reading, which is selection on an outcome correlated with VPI. We therefore
do not publish day-2-or-later comparisons, and we do not keep reading videos
after they leave the charts.

What remains uncontrollable, and is disclosed rather than corrected: **age at
first observation**. A video may be 3 days old or 10 days old when it first
appears, carrying different amounts of accumulated views into the comparison.
It is stored on every record (`age_at_first_obs_days`) and published
alongside any ranking. Once data exists, regress `log(VPI at day 1)` on it
with controls for format, baseline size, category and country; if the
coefficient is materially non-zero, the ranking must be stratified by
age-at-entry band rather than pooled.

**What this permits and forbids:**

| Construction | Status |
|---|---|
| A single record's trajectory, peak VPI, views and days | **permitted** — a descriptive statement about one video |
| A ranking at day 1, with `age_at_first_obs_days` disclosed | **permitted**, stated as "VPI on the first day observed" |
| Our own overall chart: the union of the category charts ordered by **views**, with each video's VPI shown beside it | **permitted** — the quantitative figure is YouTube's, the qualitative one is ours, and neither is averaged away |
| A single all-time ranking by peak VPI presented as "best-performing videos" | **forbidden** — the ordering is confounded by observation duration |
| Any segment average that mixes baseline bands, or Shorts with long-form | **forbidden** — see below |
| Any of the above described as "age-adjusted" | **forbidden** — the measure is age-**indexed**, never age-adjusted |

**Why segment averages must not mix baseline bands.** Entering a 200-slot
chart requires absolute views. A channel with a baseline of 2M enters with a
small relative jump; a channel with a baseline of 500 can only enter by doing
something enormous relative to itself. Both appear in the chart, at 1.5x and
at 6,000x, and the difference is the entry threshold, not the merit. A pooled
median therefore moves with how many small-baseline channels happened to
chart that day. If a segment figure is ever published, it is published **by
baseline band and by format**, with `n` shown.

**Baseline bands — provisional.** Decades of the frozen baseline: `<100`,
`100-1k`, `1k-10k`, `10k-100k`, `>=100k`. The 100 and 100,000 edges come from
our own measurement (§8); the others are powers of ten, chosen before seeing
any v2 data rather than fitted to it. They are to be reviewed against day-1
data, under the same rule as the scale: **the bands are never re-cut after
seeing which split produces a nicer number.** Any revision is published with
the how, when and why. *(Set 25/09/2026, GATE-1.)*

## 5. The budget

### What we read, and what we deliberately do not

We read the **414 category slices** (34 countries x 13 categories that
return data) and **not** YouTube's own general chart.

The general chart is a different population. Measured on 25/09/2026, Italy:
58.8% of its videos appear in no category chart at all, and its ordering is
not by views — the #2 video in Italy had 14,655 views while the #20 had
6,881,481. It is a curated showcase carrying trailers and promoted releases,
consistent with YouTube's own description of Charts after the Trending page
was retired. The category charts, by contrast, are recognisably ordered by
view count.

Our own overall ranking is therefore **built by us**, from the union of the
category charts, ordered by views, with each video's VPI shown beside it. We
do not inherit YouTube's editorial selection.

**Declared consequence.** Some category charts are capped far below 200, so
for those categories our observable window is only the head of the ranking:

| Category | Mean items per country |
|---|---|
| 29 — Nonprofits | 1.0 |
| 22 — People & Blogs | 22.1 |
| 10 — Music | 29.4 |
| 20 — Gaming | 120.6 |
| 25 — News & Politics | 144.9 |
| 28 — Tech | 147.5 |
| the other seven | 195-200 |

The general chart used to recover a few of these — a music video with
millions of views sitting outside Music's top 30 — but it recovered them
**unsystematically**, mixed with promotional content. An irregular patch is
worth less in a measurement protocol than a stated boundary.

| Item | Units |
|---|---|
| Reading the 414 category charts | 1,350 |
| View counts for every video | 0 (included above) |
| `channels.list` batched in 50s | ~96 |
| `playlistItems` per new channel (with pagination) | ~1.2 per channel |
| `videos.list` batched in 50s, 20 samples | ~0.4 per channel |

`channels.list` and `videos.list` accept 50 IDs per call.
`playlistItems.list` does not: one playlist per call (two comma-separated
`playlistId` values return HTTP 400). That is the floor.

Estimated steady-state cost: **~8,900 units out of 10,000** (the general
chart's 136 calls are no longer spent), with 23,764
unique channels and 24% turnover. It is tight. **The real 24-hour turnover
has not yet been measured** — it comes free from the day 0 / day 1
comparison, and it is the gate that decides whether we proceed as-is or
reduce the number of countries.

If it overruns, in order: drop to 10 baseline samples, then reduce
countries. No quota extension request to Google.

---

## 6. The population in figures

Census of 22 September 2026:

| | |
|---|---|
| Charts queried | 448 of 544 (96 return 404) |
| Unique videos | 29,433 |
| of which Shorts | 20,073 |
| of which long-form | 9,360 |
| Unique channels | 23,764 |
| Calls per full pass | 1,486 |
| Wall-clock time | 112 seconds |

Every chart holds at most 200 videos. Category charts are not subsets of the
general chart: the general chart is almost entirely long-form, category
charts are ~70% Shorts.

**There are 12 usable categories, not 15.** Travel & Events (19) and
Education (27) return 404 everywhere. Nonprofits (29) responds in 6 countries
out of 34 with 1 video. Music (10) caps at 30.

---

## 7. What disappears relative to v1

- **`MIN_VPI_FOR_INGESTION = 1.0`** — censored the population from below.
- **`CAMPAIGN_DAYS = 15` as a measurement window** — survives only as an
  outreach parameter (`CLAIM_DAYS`), counted from entry into the chart.
- **Random sampling** — becomes a full census.
- **Categories 19 and 27** — wasted roughly one cycle in seven.
- **Excluding channels with no handle** (the "- Topic" Art Tracks) — they
  stay in the index, flagged `auto_generated_channel`, excluded only from
  outreach.
- **`MIN_BASELINE_VIEWS = 500` as an ingestion filter** — everything is
  measured; the minimum becomes a declared criterion of the public showcase
  only.
- **`MAX_SUBSCRIBERS` / `MIN_SUBSCRIBERS`** — defined but never used.
- **The `is_real_youtube_short()` HTTP check** — the only non-API call in
  the pipeline. Classification is by duration, which is official data.

---

## 8. Open questions

1. **The scale.** Absolute thresholds need recalibrating: today level 10
   holds 16.8% of records. Not before ~3 weeks of data. Still to decide:
   anchor it to percentiles (but then a video's level depends on who else is
   in the index) or keep declared absolute thresholds. See
   `04-bias-and-scale-analysis.md`.
2. **The ratio as a functional form.** On historical data the median VPI is
   strongly associated with the size of its own denominator — 6,103× for
   baselines under 100 views, 3.7× above 100,000 — instead of staying flat.
   The two-band comparison establishes the association, not a 1/baseline
   law. Whether to replace the ratio with a log transform, shrinkage, or a
   within-channel percentile rank is **the first question we put to external
   reviewers.** Note that a log transform is monotonic: it changes the
   spacing of the scale, not the ordering, and therefore cannot by itself
   remove a systematic difference between denominator bands.
3. **A two-speed population**: records with a VPI and records with
   `baseline_not_computable`. Coherent, but it needs third-party judgement.
4. **The 27,000 v1 records**: archived and flagged, never mixed in.

*(The question "the baseline compares mature videos against a freshly
released one" was retracted on 23/09: it is not a defect but correct
behaviour. The denominator is the level a video of that channel normally
reaches, and the numerator's climb toward it is the trajectory we want to
observe.)*

---

## 9. What must be corrected in published material

- **"15 categories" is false.** There are 12.
- Every **median, percentage and correlation** published so far comes from a
  censored, randomly-sampled population: it does not hold.
- **Counts** and **individual dated cases** do hold.

---

*Social and outreach activity suspended until the scale is recalibrated.
Ingestion service on Render suspended since 22 September 2026.*
