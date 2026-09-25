# IOSA VPI — Dossier for External Review

**Version 1, 23 September 2026.**

This document is written for someone who does not know the project and whom
we are asking to **find its flaws**. It is not promotional material.
Everything we know to be wrong is written here, including the things we got
wrong and corrected.

Review prompts are in section 10.

---

## 1. What IOSA is, and what the index claims to measure

IOSA is an independent, non-profit index that measures **how far a video
beats its own channel's median**, not how many views it gets.

The premise: raw view counts only reward those who are already large. A
video with 200,000 views on a channel with 3 million subscribers is a modest
result; the same 200,000 views on a channel that normally gets 5,000 is an
event. The ratio between those two things is what the index calls VPI.

It does **not** claim to measure the quality of a video, its commercial
value, the creator's skill, or virality in absolute terms. It measures one
thing — a ratio — over a defined population.

Site: iosaresearch.org. Zero-budget project, one person, free tooling
(Supabase free tier, Render free tier, Vercel free tier, YouTube Data API v3
on the standard quota).

---

## 2. The metric

```
VPI = video views / channel baseline, within the same format
```

**Numerator**: the video's public view count, read from the official API,
updated daily for as long as the video remains in the chart.

**Denominator (baseline)**: the median view count of videos from the same
channel and **the same format**, published between 7 and 90 days before the
measurement, at least 5 of them, at most 20 spread evenly across the window.
Computed **once, at the moment the video enters the chart, and then frozen**.

There are two formats and they never mix: **Shorts** (≤180 seconds) and
**long-form** (>180 seconds).

**Median, not mean**, so that a previous breakout does not inflate the
denominator.

The value is then placed on a 10-level scale with absolute thresholds
(Lvl 1 below 1.5× up to Lvl 10 above 50×). **This scale is inherited from
the previous version and is one of the points we most want attacked** — see
section 6.

### 2.1 When the value is read (added 24/09/2026)

This was missing from the first release of this dossier and is material to
any judgement about measurement age.

VPI is not a single scalar read at an unspecified moment. It is recomputed
**every day the video is observed in the chart**, and published as a
trajectory:

- while the video is charting, the public sees the current value and the day
  count, with the measurement explicitly marked as open. **No award is
  issued.**
- when the video leaves the chart, the record is closed and the published
  value is the **VPI at exit**, always displayed together with the number of
  days charting.

VPI generally rises over a record's life, since the denominator is frozen
and views accumulate — but not by construction: YouTube removes views on
audit, so the series can fall. The maximum is therefore stored as observed,
never inferred from the exit value.

The claim attached to the published figure is therefore:

> For the whole period in which we observed this video in the Most Popular
> charts, it reached N times the median view count of the same channel's
> videos in the same format published between 7 and 90 days before it was
> first observed.

It is explicitly **not** claimed to be independent of the video's age.

**Comparability between videos** (added 24/09/2026). Two records are not
automatically comparable. Two things differ, and only one is controllable:
days observed in the chart (controllable — every comparison is made at the
same day index), and age at first observation (not controllable — recorded,
disclosed, and tested for residual effect). The rule: two VPI values may be
compared only at the same number of days since first observation, among
records for which that day was actually observed.

Consequently the index publishes **day-indexed** rankings and aggregates
("VPI at day N"), including active and closed records alike; exit VPI is a
per-record descriptive value and a secondary, separately labelled statistic,
never the basis of a "best-performing videos" ranking and never the unit of
a segment aggregate. The measure is age-**indexed**, never age-adjusted.

---

## 2.2 Decisions closed after review (25/09/2026)

For a reviewer returning to this dossier, the design changed in five ways:

1. The baseline window is anchored to the **measured video's own
   `publishedAt`**, not to the measurement date — so the denominator is
   genuinely pre-event.
2. **YouTube's general chart is no longer read.** Measured: 58.8% of its
   videos appear in no category chart, and its ordering is not by views
   (Italy: #2 had 14,655 views, #20 had 6,881,481). It is a curated showcase.
   Our own overall ranking is built from the union of the 414 category charts,
   ordered by views, with each video's VPI beside it.
3. The published figure is the **peak VPI observed**, with views and days in
   Most Popular. Monotonicity was withdrawn: YouTube removes views on audit.
4. **Cross-video comparisons at day 1 only** — the one index every record has
   by construction. From day 2 a ranking conditions on residence, which
   correlates with VPI. No post-exit tracking.
5. **No segment figure pooled across baseline bands or formats**, because
   chart entry requires absolute views and therefore sets a different VPI
   threshold for each channel size.

## 3. The population

> Videos — Shorts and long-form — **first observed** in YouTube's "Most Popular"
> charts, across 34 countries and 13 categories, starting from a declared
> start date.

*(Corrected 25/09/2026: 12 → 13, see `01` §1.)*

**a) Entry into the chart is not observable; first observation is.** YouTube
does not expose entry. Verified on 22/09/2026 by pulling every available API
part (`snippet`, `contentDetails`, `statistics`, `status`, `topicDetails`,
`recordingDetails`, `liveStreamingDetails`, `player`, `localizations`): the
only date present is `publishedAt`. No field says since when a video has
been charting, or at what position.

What we actually observe is: **present in today's snapshot, absent from the
previous one**. With one reading a day that is a weaker event than entry.
A video that enters and leaves between two readings is never seen; a video
entering at 03:00 and one entering at 23:58 are recorded on the same day;
after a missed reading, a video first seen may have entered during the gap.

The population is therefore defined by our observation, not by YouTube's
event, and the index must never be described as a census of chart entrants.
*(Wording corrected 24/09/2026 after external review.)*

**b) The population is already pre-selected by YouTube.** YouTube's own
documentation states that among the ranking signals for Most Popular is *"how
well the video performs compared to other recent uploads from the same
channel"* — **a quantity correlated with the one we measure**. This is a
declared structural limitation that cannot be engineered away. See 6.1.

**c) Videos already in the chart on day 0 never enter the index**, because
we cannot say when they entered.

---

## 4. The collection procedure

One reading per day, at **23:59 UTC**.

**Day 0** — all charts are read and the IDs stored. Nothing is ingested, no
baseline computed.

**Day 1 onward**

1. Read all 448 charts (34 countries × 12-13 slices), paginating to
   exhaustion. View counts arrive in the same call.
2. Store the complete snapshot of IDs.
3. **New entries** = present today, absent yesterday, never seen before. For
   each, compute the baseline at that moment and freeze it.
4. **Already-tracked videos still charting**: update views, recompute
   today's VPI against the frozen baseline.
5. **Videos that left**: close the record. It stays forever.
6. **Re-entries**: no new record, no baseline recomputation.

No filter on VPI value. No expiry window on records.

---

## 5. What we actually measured

All figures from direct measurements against the official API, 22-23
September 2026.

### 5.1 Population size

| | |
|---|---|
| Charts queried | 448 carrying data of 544 queried (96 return 404) |
| Unique videos | 29,433 |
| of which Shorts (≤180s) | 20,073 |
| of which long-form | 9,360 |
| Unique channels | 23,764 |
| API calls for one full pass | 1,486 |
| Wall-clock time | 112 seconds |

Every chart holds **at most 200 videos**: verified across 20 countries,
`totalResults` = 200 in all of them.

**Category charts are not subsets of the general chart**: they are separate,
nearly disjoint lists. The general chart is almost entirely long-form
(Shorts are 5-12%); category charts are ~70% Shorts. Average overlap factor
2.4 — each video appears in 2.4 different charts.

### 5.2 Categories that do not exist

Tested across 10 countries: **Travel & Events (19) and Education (27) return
404 in every country**. Nonprofits (29) responds in 6 countries out of 34
and returns 1 video. Music (10) caps at 30. Confirmed against 27,000
historical records: Travel and Education have **zero**.

### 5.3 Population turnover

Two readings ~16 hours apart: **24.2% of channels had never been seen
before**. The 24-hour figure has not yet been measured.

Age of charting videos (20,127 Shorts):

| Age since publication | Share |
|---|---|
| < 1 day | 4.3% |
| 1-3 days | 23.5% |
| 3-7 days | 44.8% |
| 7-14 days | 23.5% |
| over 14 days | 3.9% |

**This table measures age since publication, not age since entry into the
chart**, and the two are not interchangeable: YouTube exposes no entry
timestamp. It therefore cannot support any claim about how long videos
persist in the chart. It shows only that charting videos are overwhelmingly
between 1 and 14 days old. *(Corrected 24/09/2026 after external review: the
earlier wording inferred chart persistence from publication age.)*

### 5.4 Baseline computability (sample of 220 channels)

| Window | Channels with ≥5 samples |
|---|---|
| 14-90 days | 75.9% |
| 10-90 days | 84.1% |
| 7-90 days | 88.6% |
| 5-90 days | 94.1% |

19% of channels have **no** samples in the 14-90 day window. Established
cause: `playlistItems` returns only the 50 most recent uploads, and for
hyper-prolific channels all 50 fall within 14 days. **41 cases out of 42
confirmed.** Not data scarcity — the API call's ceiling.

Baseline shift from lowering the maturity floor (n=167):

| Comparison | Median ratio | p10 | p90 |
|---|---|---|---|
| 10-90 vs 14-90 | 1.000 | 0.85 | 1.20 |
| 7-90 vs 14-90 | 1.000 | 0.78 | 1.22 |
| 5-90 vs 14-90 | 1.000 | 0.73 | 1.32 |

The **central value** of the baseline does not move; per-channel dispersion
widens. This is a sensitivity result, not evidence that no bias exists: a
median ratio of 1.000 is compatible with systematic subgroup or tail
effects, and no confidence interval, paired test or subgroup analysis has
been computed. The move from 14 to 7 rests on the coverage gain (75.9% →
88.6%) together with the absence of a central shift — not on a demonstration
of unbiasedness. *(Corrected 24/09/2026 after external review.)*

### 5.5 Quota constraint

YouTube Data API v3: **10,000 units per day**, 1 unit per read call
regardless of `part`.

`channels.list` and `videos.list` accept 50 IDs per call.
`playlistItems.list` does not (two comma-separated `playlistId` values
return HTTP 400). That is the floor: 1 unit per new channel.

Estimated steady-state cost: **~9,000 of 10,000 units**. Tight, and the
margin depends on the real 24-hour turnover, measured on day 1.

---

## 6. Known limitations and contestable choices

This is the section we want attacked.

### 6.1 The population is selected on a variable correlated with the outcome

YouTube ranks Most Popular partly on how much a video outperforms others from
the same channel. That signal is **correlated with** VPI; it is not VPI.
YouTube's ranking is a different functional quantity, and we have access to
neither its definition, nor its weighting, nor any threshold it may apply.
What the evidence supports is therefore **selection related to the
outcome** — not truncation of the population at a VPI value.

The consequence stands either way: no statistic we compute describes
"YouTube videos". It describes "videos YouTube placed in Most Popular", and the
observed VPI distribution cannot tell us how unusual a given VPI would be
among ordinary uploads.

A representative population cannot be obtained from the Most Popular endpoint at
all. Whether some alternative sampling design exists under other constraints
is outside what we have tested. **We declare the selection. Is declaring it
enough?**

*(Corrected 24/09/2026 after external review: the earlier wording claimed
the population was truncated on our own metric, and claimed random sampling
was the only alternative. Neither is supported by the evidence here.)*

### 6.2 The 10-level scale is inherited and poorly calibrated

The thresholds were chosen a priori, before any data existed. On historical
data **the top level contains 16.8% of records**.

Historical percentiles: p50 = 7.0× | p90 = 89.7× | p95 = 196.8× | p99 = 879×.

The scale needs recalibrating, **not before ~3 weeks of data**. The open
question: calibrating on percentiles means a video's level depends on who
else is in the index that month. **Is that acceptable, or are absolute
thresholds preferable?**

Our current argument for absolute thresholds is a product argument: the
plaque is a permanent document with a frozen number, and a level that
drifts over time would make it worthless. **That argument has not been
tested statistically.**

### 6.3 Small denominators produce enormous ratios

With a baseline of 10 views, a video with 500,000 yields VPI 50,000. On
historical data the median VPI by baseline band runs from 6,103× (baseline
< 100) to 3.7× (baseline > 100,000): **VPI is strongly associated with the
size of its own denominator** instead of staying flat, which is precisely
what a normalisation should not do.

Two bands establish the association. They do not establish a 1/baseline
functional law: testing the functional form requires regressing log(views)
on log(baseline) with controls for age, format, category and channel, and
that has not been done. *(Corrected 24/09/2026 after external review.)*

The previous version excluded records with baseline < 500. But exclusion is
censoring. The current choice: **measure everything, apply a declared
minimum only to the public showcase.**
**Is that right, or should the ratio be replaced by something more robust
(log transform, standardised score, within-channel percentile rank)?**

### 6.4 The baseline is frozen

Freezing at entry makes the denominator a **pre-event** measurement. The
reason: when a video explodes it lifts the rest of the channel, and those
videos enter the baseline window days later — the denominator would rise
because of the very event the numerator measures.

Counter-argument: if a video stays charting for 20 days, the baseline is 20
days stale and the channel may have grown for unrelated reasons.

We decided to **freeze, and store the IDs of the baseline videos**, so that
in three weeks we can compare baseline-at-entry against baseline-at-exit and
test whether the shift correlates with the video's VPI. **Does that test
design hold up?**

### 6.5 The measured video is excluded from its own baseline… or is it?

The measured video is excluded explicitly. But **other videos from the same
channel that entered Most Popular in the same period** are not, and may have
been inflated by the same event. We have no countermeasure.

### 6.6 Filters that remain, and need justifying

- **Auto-generated channels** ("Artist - Topic", music catalogue Art Tracks
  with no handle): they stay in the index, flagged, excluded only from
  outreach. They used to be discarded, which is why Music holds 432 records
  out of 27,000.
- **Baseline not computable** (fewer than 5 samples after 3 pages): the
  record exists with a null VPI. **This creates a two-speed population. Is
  that a problem?**
- **Duration**: videos with no duration (live streams, premieres) excluded.

### 6.7 The ramp-up period

For the first ~14 days the index is partial by construction. **How should
that be declared, and from when do statistics become publishable?**

### 6.8 Operational constraints that can corrupt the data

- A missed reading falsifies the "absent yesterday" comparison and every
  video looks like a new entry. Countermeasure: compare against the most
  recent existing snapshot and record the gap size.
- The quota can run out mid-pass. Countermeasure: a brake at 9,500 units,
  the pass marked partial, videos picked up next day with a flag.
- Free-tier database space (500 MB) runs out in ~2 months at projected
  growth. Countermeasure: aggregating closed series.

---

## 7. What we already got wrong

Set out in full because a reviewer should know how unreliable the project
has been, and because the errors point at where to look.

**7.1 A population censored from below.** Until 22/09/2026 the engine
discarded every video with VPI ≤ 1.0. The distribution of levels was
uninterpretable: the entire lower tail was missing.

**7.2 Random sampling presented as a census.** Every 20 minutes the engine
read US + 2 random countries out of 34 × 1 random category out of 15 × 2
pages out of 4. At most 300 videos out of ~63,000 slots. No video had a
known probability of being observed.

**7.3 Measurement-age confounding.** Views were frozen at first detection,
and the video's age at that moment ranged from 0.1 to 15 days:

| Age at measurement | Records | Median VPI | Share at Lvl 10 |
|---|---|---|---|
| < 1 day | 2,135 | 4.2× | 10.0% |
| 1-2 days | 4,032 | 5.0× | 12.1% |
| 2-4 days | 5,458 | 6.9× | 15.8% |
| 4-7 days | 3,504 | 11.4× | 24.1% |
| > 7 days | 1,105 | 16.8× | 28.5% |

Spearman ρ(age, VPI) = 0.20. **The level assigned depended on when we
happened to look.**

**7.4 A 15-day window conflating measurement with outreach.** Records
dropped out of the population after 15 days for a commercial reason.

**7.5 False public figures.** The site states "15 categories": there are 12.
Every median, percentage and correlation published so far comes from the
censored, randomly-sampled population.

**7.6 Filters we believed were active and were not.** `MAX_SUBSCRIBERS` and
`MIN_SUBSCRIBERS` are defined in the engine but used in no comparison.

**All public material is under review and all social activity has been
suspended since 22/09/2026.**

---

## 8. What we are NOT asking

Not whether the project is a good idea, whether the positioning works, or
whether the scale should have different labels. We are asking whether **the
number we publish means what we say it means**, and whether the procedure
that produces it survives scrutiny.

---

## 9. Data available to the reviewer

- the full census of 22/09/2026 (29,433 videos, 448 charts) with country,
  category, format, publication date and view count
- the 220-channel sample with the ages of all recent uploads
- the 28,917 historical records collected under the old method (to study the
  defects, not as valid data)
- the source code of the ingestion engine and the VPI computation

---

## 10. Review prompts

### 10.1 Adversarial review of the method

> You are an applied statistician asked to find the flaws in an index before
> it is published. You are not being asked to judge whether it is good: you
> are being asked to identify every point at which the number produced does
> not mean what its authors say it means.
>
> Read the attached document. Then:
>
> 1. List, in order of severity, the defects that invalidate or weaken the
>    interpretation of the metric. For each, explain the mechanism, not just
>    the name of the problem.
> 2. For each defect, say whether it is correctable within the declared
>    constraints (10,000 API calls per day, one reading per day, no budget)
>    or whether it can only be disclosed.
> 3. Flag every claim in the document that is not supported by the data
>    presented.
> 4. Specify which control analyses should be run on the data, once
>    collected, to verify that the disclosed defects are actually under
>    control.
>
> Do not soften anything. If the method does not hold up, say so and explain
> why.

### 10.2 Targeted review of the estimator

> An index computes, for each video, the ratio between its view count and
> the median view count of recent videos from the same channel and the same
> format. The denominator is computed once and frozen.
>
> Evaluate this estimator:
>
> - Is the ratio the right functional form, or would a log transform, a
>   within-channel standardised score, or the video's percentile rank within
>   its own channel's distribution be preferable?
> - Is the ratio's behaviour when the denominator is small a defect to fix
>   in the formula, or something to manage with a publication criterion?
> - Is a median over 5-20 observations stable enough to assign a level on a
>   10-step scale?
> - Is freezing the denominator at entry the right choice when the measured
>   event can influence the denominator itself? What design would let this be
>   verified empirically?

### 10.3 Review of the scale

> An index classifies the values of a ratio on a 10-level scale with
> absolute, a priori thresholds. On the data collected, the top level
> contains 16.8% of observations, and the distribution's percentiles are
> p50 = 7.0 | p90 = 89.7 | p95 = 196.8 | p99 = 879.
>
> 1. Should the absolute thresholds be recalibrated on observed percentiles,
>    or does a percentile-anchored scale introduce a worse defect (an
>    observation's level depending on the other observations present)?
> 2. If recalibrating, on what criterion are the thresholds chosen, and how
>    is comparability with already-published values handled?
> 3. Does a single scale make sense for such a skewed distribution, or are
>    separate scales needed for sub-populations (format, baseline band,
>    category)?

### 10.4 A note on the independence of this review

The protocol was written with the assistance of a Claude model. **Having the
same protocol reviewed by a model of the same family is not independent
review**: it will tend to find the same things reasonable.

For a verification worth having:

- use a session **without** the context of the conversation in which the
  protocol was written, fed only this dossier
- use **at least two models from different vendors**, so that blind spots do
  not coincide
- and, before declaring the index publishable and citable, **a human
  reviewer with statistical expertise**

---

*Contact: iosa.research.lab@gmail.com — iosaresearch.org*
