# VPI Measurement Protocol — v2

**Status: approved 23 September 2026.** Supersedes v1 of 21 September
(fixed-age measurement at T=7 days: abandoned).

Every figure here was measured against the official YouTube Data API v3.
Sources in `03-trending-population-measurements.md`.

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
> trending charts, across 34 countries and 12 categories, starting from our
> day 1.**

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
> published between 7 and 90 days before the measurement, at least 5 of
> them, at most 20 spread evenly across the window.**

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

Videos already in the chart on day 0 will never enter the index: we could
not say when they entered.

### Day 1 onward

1. Read the 448 charts. View counts arrive **free** in the same call:
   `part=statistics` costs no extra quota.
2. Store the complete snapshot of IDs, **including videos we do not
   ingest**. Without it, "absent yesterday" is not computable tomorrow.
3. **New entries** = present today, absent yesterday, never seen before →
   baseline computed and frozen → record written.
4. **Already tracked and still charting** → views updated, today's VPI
   recomputed. Zero cost.
5. **Gone** → record closed with `left_on`. Stays in the database forever.
6. **Re-entries** → no new record, no baseline recomputation.

**If a day's reading is missed, entry status becomes indeterminate.** The
comparison still runs against the most recent existing snapshot rather than
"yesterday" by definition, but a video first seen after a gap cannot be
called a new entrant: it may have entered and been present throughout the
gap. Such records are written and tracked normally, carrying
`entry_certain = false` and the size of the gap, and they are excluded from
every statistic that depends on the entry date.

**A gap never manufactures an entry event.**

### 4.1 The published value and the record lifecycle

VPI is **not a single scalar read at an unspecified moment**. It is a
trajectory with a declared closing rule.

| Phase | What happens | What the public sees |
|---|---|---|
| Day 1 in chart | baseline computed and frozen, first VPI | "In trending, day 1 — currently 3.2× the channel median. Measurement in progress." |
| Days 2..n | views updated, VPI recomputed, no baseline change | the current value and the day count; **no award is issued** |
| Exit | record closed, `left_on` and `days_charting` written | "In trending for 4 days, VPI at exit 3.5×. The plaque is now available." |

**The published value is the VPI at exit.** Because the denominator is
frozen and cumulative views never decrease, VPI is monotonically
non-decreasing over the record's life: the value at exit is therefore also
the maximum by construction. We publish it as the exit value, not as a
"maximum", because calling it a maximum would suggest a selection that never
takes place.

**What that number claims, stated exactly:**

> For the whole period in which we observed this video in the trending
> charts, it reached N times the median view count of the same channel's
> videos in the same format published between 7 and 90 days before it was
> first observed.

It does **not** claim to be independent of the video's age, and it is not
comparable across videos observed for different lengths of time without
reporting `days_charting` alongside it. Both figures therefore always travel
together, on the plaque and in the API.

This is the answer to the objection that "current VPI" is not a well-defined
estimand: there is no floating current value in the published material. There
is a trajectory while the measurement is open, and one declared value once it
is closed.

The days available to claim the plaque (`CLAIM_DAYS`) are an outreach
parameter counted from first observation. They do not touch the measurement.

### 4.2 Comparability between records

A single record's value is well defined. **Two records are not automatically
comparable.** Two things differ between them, and only one is under our
control:

| Source of non-comparability | Controllable? | What we do |
|---|---|---|
| **Days observed in the chart.** The numerator is cumulative and the denominator is frozen, so a video observed for 12 days has had six times the accumulation opportunity of one observed for 2 days. | **Yes** | every comparison is made at the **same day index** |
| **Age at first observation.** A video may be 3 days old or 10 days old when it first appears in the charts, carrying very different amounts of views into the comparison. | **No** | recorded on every record, published alongside every aggregate, and tested for residual effect |

**The comparison rule:**

> Two VPI values may be compared only if both were observed at the same
> number of days since first observation in the chart, and only among
> records for which that day was actually observed.

**What this permits and forbids:**

| Construction | Status |
|---|---|
| A single record's trajectory and exit value | **permitted** — a descriptive statement about one video, always shown with `days_charting` |
| A leaderboard at a fixed day index ("Top VPI — day 3") | **permitted** — stated as "VPI at N days after first observation", not as age-independent performance |
| Aggregates (country, category, format) at a fixed day index, active and closed records together, with `n` reported | **permitted** |
| A single all-time leaderboard ranked by exit VPI, presented as "best-performing videos" | **forbidden** — the ordering is confounded by observation duration |
| Aggregates computed on exit VPI | **forbidden as the primary statistic** — a segment with longer average chart persistence would look different from one with shorter persistence even with identical trajectories |
| Any of the above described as "age-adjusted" | **forbidden** — the measure is age-**indexed**, never age-adjusted |

A table of exit VPI may still be published as a **historical record of the
highest values observed**. That is a different claim from a performance
ranking and must be labelled as such.

**Selection at day N.** Conditioning on being observable at day N is itself
a selection: day-7 statistics describe *videos still in the chart on day 7*,
not all videos in the index. Acceptable, and stated every time.

**Restricting aggregates to closed records is wrong** as the primary
statistic: it conditions on future information (how long the video would
ultimately stay) and drops every record currently charting. A day-3 figure
uses every video with a valid day-3 observation, whether it left on day 4,
on day 10, or is still charting. An exit analysis on closed records is a
**secondary**, separately labelled statistic.

**Validation to run once data exists.** At each day index, regress
`log(VPI)` on age at first observation with controls for format, baseline
size, category and country. If the age coefficient stays materially
non-zero, the fixed-day ranking still carries systematic age dependence and
must be qualified further.

---

## 5. The budget

| Item | Units |
|---|---|
| Reading the 448 charts | 1,486 |
| View counts for every video | 0 (included above) |
| `channels.list` batched in 50s | ~96 |
| `playlistItems` per new channel (with pagination) | ~1.2 per channel |
| `videos.list` batched in 50s, 20 samples | ~0.4 per channel |

`channels.list` and `videos.list` accept 50 IDs per call.
`playlistItems.list` does not: one playlist per call (two comma-separated
`playlistId` values return HTTP 400). That is the floor.

Estimated steady-state cost: **~9,000 units out of 10,000**, with 23,764
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
| Charts queried | 448 of 476 (28 return 404) |
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
