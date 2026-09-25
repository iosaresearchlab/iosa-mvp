# Selection bias and scale calibration

Originally written 22 September 2026, after three content proposals were
rejected. All three rejections were justified. Two proposals died; the third
opened a product problem.

> **CORRECTION NOTICE — 23 September 2026.** Section 4 of this document
> proposed a recalibrated scale (level 10 at ≥250×). **That proposal is
> withdrawn and must not be used.** It was computed on the censored
> population — the one that excluded every video with VPI ≤ 1.0 — so every
> threshold in it is wrong. The correct sequence is in section 4.4. The rest
> of this document stands.

---

## 1. What actually enters the index

Before any statistic, the list of filters a video passes before becoming a
row. They live in `backend/vpi_core.py` and `vpi_engine.py`. This is the v1
state, as of 22 September 2026.

| Filter | Value | Effect |
|---|---|---|
| Source | YouTube "most popular" chart, by country and category | **not a sample of YouTube, it is the shop window** |
| Duration | ≤180s for `SHORT` | — |
| Age | 15-day window | — |
| Subscribers | 1,000 to 1,500,000 | *(defined but never actually applied — see note)* |
| Minimum baseline | ≥500 views | excludes channels that post Shorts rarely |
| Baseline samples | ≥5 videos | — |
| **Minimum VPI** | **> 1.0** | **discards every video that does not beat its own median** |

*Note added 22/09: `MAX_SUBSCRIBERS` and `MIN_SUBSCRIBERS` are defined at the
top of `vpi_engine.py` but appear in no comparison anywhere in the
ingestion path. We believed we were filtering by subscriber count. We were
not.*

The last row is what invalidates the statistics.
`MIN_VPI_FOR_INGESTION = 1.0`, with the comment "below or equal is not an
outlier". Consistent with the product — the index catalogues outliers — but
it means **the database contains only the survivors**.

Direct consequence: *no* median we publish is the median of a real
population. The "index median of 7.0×" is the median of videos that had
already beaten themselves. The true median of Most Popular videos is by
construction lower, and we do not know by how much, because **the discards
are counted nowhere**: the engine logs them per cycle and then the number is
lost.

### The second, subtler bias

YouTube's documentation on Most Popular states that placement takes into
account, among other factors, "how well the video performs compared to other
recent uploads from the same channel". That is, **YouTube already
pre-selects partly on the same quantity we measure**. We are not observing a
neutral population to which we apply our index: we are measuring how much of
an outlier videos are, when those videos were chosen partly for being
outliers.

This cannot be corrected by changing our filters. It can only be declared.

### How YouTube's charts work

From the official guide: refreshed **roughly every 30 minutes**; not
personalised, identical for everyone in the same country; they exist per
country and for some categories; they hold "a limited number" of videos,
undeclared. Ranking factors include view count, rate of growth, external
traffic, topical relevance, video age, and the comparison with recent
uploads from the same channel.

Operational note: we were polling every 20 minutes a source that changes
every 30. We were querying more often than the data moves.

---

## 2. "Music outperforms everything" — dead

The claim was: Music median 19.4× against 7.0× for the index, 44 level-10
records out of 133.

**It dies for two independent reasons.**

**The sample is tiny and censored.** 133 records out of 16,234, and they are
the 133 that passed the filter. We do not know how many Most Popular music
videos were discarded for falling below 1.0×. It could be most of them.

**The number is a denominator effect, not performance.** Direct comparison:

| | Music | All others |
|---|---|---|
| Records | 133 | 16,101 |
| Median VPI | 19.4× | 7.0× |
| **Median baseline** | **39,997** | **76,746** |
| Median views | 722,086 | 780,672 |
| Median subscribers | 288,000 | 271,000 |

Music videos **do not get more views** than the others: they get slightly
fewer. Their VPI is higher because their baseline is roughly half. The ratio
is high because the denominator is low.

The category's top entries confirm it: `nightlife` with 346,000 subscribers
and a baseline of **854**; `Tearbluee` 42,100 subscribers, baseline **625**;
`sugarTap` baseline **544.5**. These are music channels that rarely post
Shorts — the same pathology as ARY Digital, the broadcaster at 13,382×.

**Verdict: not publishable.** It would be a headline true in form and false
in substance.

---

## 3. "Long-form versus Shorts" — also dead

The claim was: `LONG` median 2.6× against `SHORT` 7.4×, nearly three times.

The comparison mixes different populations: 859 long records from 812
channels against 15,375 Shorts from 11,388 channels. Almost no channel
appears in both groups, so the gap could be composition rather than format.

**The correct comparison is paired**, over the 329 channels active in both
formats:

| Measure | Value |
|---|---|
| Channels with both formats | 329 |
| Median ratio (Shorts median ÷ long median) within the same channel | **1.29×** |
| Channels where Shorts beat long-form | 200 (61%) |
| Channels where long-form beats Shorts | 116 (35%) |

The real format effect is **1.3×, not 2.8×**, and it holds for six channels
in ten, not for all. Most of the gap in the raw comparison is composition.

**Verdict: the strong claim dies.** What remains is an honest, smaller
finding — "on channels that post both, Shorts beat their own baseline about
one and a half times as often as long videos, and in four cases out of ten
it is the other way round" — publishable, but not a headline.

---

## 4. The scale — needs rebuilding

### 4.1 Where it stands

With the current `VPI_SCALE`, across 16,234 active records:

| Level | Threshold | Share | Cumulative from top |
|---|---|---|---|
| Lvl 10 — Hyper Outlier | ≥50× | **16.78%** | 16.8% |
| Lvl 9 — Mega Outlier | ≥25× | 9.97% | 26.8% |
| Lvl 8 — Outlier | ≥15× | 8.72% | 35.5% |
| Lvl 7 — Super Viral | ≥10× | 7.66% | 43.1% |
| Lvl 6 — Viral | ≥7.5× | 5.65% | 48.8% |
| Lvl 5 — Breakout | ≥5× | 8.20% | 57.0% |
| Lvl 4 — Trending | ≥3× | 11.57% | 68.5% |
| Lvl 3 — Rising | ≥2× | 9.94% | 78.5% |
| Lvl 2 — Moderate | ≥1.5× | 8.29% | 86.8% |
| Lvl 1 — Standard | <1.5× | 13.24% | 100% |

A sixth of the index is called "Hyper Outlier". Half the index sits at level
6 or above, i.e. is called "Viral" or better. **The words no longer describe
anything.**

The distribution's actual percentiles: p50 = 7.0 · p75 = 28.0 · p90 = 89.7 ·
p95 = 196.8 · p97.5 = 410 · p99 = 879 · p99.9 = 4,157.

The 50× threshold falls around the 83rd percentile. To sit in the first to
fifth percentile — where a top level is normally expected — the threshold
would need to be between 200× and 880×.

### 4.2 Proposed scale — WITHDRAWN

*(The table that stood here proposed level 10 at ≥250×, giving it 4.05% of
records. **It is withdrawn.** It was computed on the censored population, so
every threshold is wrong. Recalibrating on the censored distribution and
then removing the censoring would mean calibrating twice, and publishing a
scale we would have to change again within weeks.)*

### 4.3 Decided: numeric thresholds, fixed once

**This is settled and is not an open question.** The procedure:

1. Collect until there is enough data (the minimum is stated with the first
   audit, not guessed now).
2. Set the ten thresholds as **numbers** — level 10 above 250x, or above
   1,000x, whatever the distribution supports.
3. Those numbers are then **frozen**, and the vintage they were calibrated on
   is printed on the plaque.
4. If they are ever revised, the revision is published with the how, the when
   and the why. Not silently.

Historical v1 percentiles are **not** admissible as calibration evidence: the
dataset was produced by a censored, non-probability sampling method this
document itself declares invalid.

### 4.4 Absolute or percentile-based? — background

**Absolute**, and this follows from the plaque. The plaque is a permanent
document carrying a date and a frozen number: if the level were a percentile
computed against the index at that moment, a creator's level would drift on
its own over time, without their video changing. A plaque that devalues
itself is worth nothing. Fixed thresholds, recalibrated when needed, with
the calibration date declared.

*(Open question for external reviewers: this argument is a product
argument, not a statistical one. Whether it survives statistical scrutiny is
one of the questions in `05-external-review-dossier.md`.)*

### 4.4 The order of operations matters

**Any calibration computed today is computed on the censored population.**
The correct sequence:

1. **Measure how much we discard.** The engine already computes
   `skipped_vpi` every cycle; it simply needs writing down.
2. **Remove the filter** and keep everything that passes the quality checks.
3. **Accumulate** enough data under the new method — the protocol says
   roughly 3 weeks.
4. **Recalibrate** on the complete population.
5. **Regenerate card 4**, which prints "Lvl 10 starts at 50x".

Steps 1 and 2 are superseded by the v2 method, which removes the filter
entirely. Step 3 begins on day 1 of v2 collection.

---

## 5. What changes for communication

The rule that comes out of this, effective immediately: **before publishing
a number, ask which population the number belongs to.** Almost everything we
can say must be qualified with "among the Most Popular videos we measured", not
"on YouTube".

Three sentences we used, or were about to use, that do not hold:

- "the index median is 7.0×" → it is the median of the filter's survivors
- "Music outperforms other categories threefold" → a denominator effect on
  133 records
- "Shorts beat their own baseline three times more than long videos" →
  paired, it is 1.3×

What does hold, and stays publishable, is anything about **a single case**:
a creator's video with its baseline, its view count and its date. There is
no inference about a population there, only a ratio between two measured
numbers. It is also the format that brought the only external visitor so
far.
