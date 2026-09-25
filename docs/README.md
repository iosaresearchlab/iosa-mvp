# IOSA VPI — documentation

Canonical documentation for the IOSA Viral Performance Index. These files
are versioned with the code they describe. When something here disagrees
with the code, one of the two is a bug.

**Everything in this folder is in English.** The project's working language
is Italian, but the documentation is not: external reviewers read it, and
so does anyone who later contributes to the repository.

---

## What each document is

| File | What it is | Who reads it | Lifespan |
|---|---|---|---|
| `01-methodology-protocol.md` | **What** we measure and why. The project's constitution. | Future maintainers, external reviewers, the public methodology page | Durable. Changes only by explicit decision |
| `02-technical-specification.md` | **How** to build it. A work order against this codebase, file by file. | Whoever writes the code | Disposable. Once implemented it survives only as a record of what changed |
| `03-trending-population-measurements.md` | The measured facts about YouTube's trending charts. | Anyone questioning a number in the protocol | Durable until re-measured |
| `04-bias-and-scale-analysis.md` | Analysis of the selection biases and of the level scale. | Reviewers, and whoever recalibrates the scale | Historical, with corrections noted inline |
| `05-external-review-dossier.md` | Self-contained dossier for third-party reviewers, including review prompts. | External reviewers | Durable, updated when the method changes |
| `06-claude-project-settings.md` | Replacement text for the claude.ai project description and instructions. | Migert, to paste manually | Delete once pasted |
| `07-review-engagement-playbook.md` | How to engage external reviewers: what to send, exact prompts, how to process the answers. | Migert | Durable |
| `08-implementation-plan.md` | **In what order** to build it, and how each step proves itself. Sequential tasks, closing checks, gates. | Whoever writes the code | Disposable. Closed tasks stay as a record |
| `review-data/` | Anonymised data package supporting the dossier's figures. | External reviewers | Durable until re-measured |

---

## The dependency between them

```
03 measurements  ──┐
04 bias analysis ──┼──>  01 methodology protocol  ──>  02 technical spec  ──>  08 plan  ──>  code
                   │              │
                   └──────────────┴──>  05 review dossier  ──>  external reviewers
```

Read in this order if you are new: **05** for the whole picture, then **01**
for the method, then **02** and **08** if you are going to write code — `02`
says what to change, `08` says in what order and how each step is proved.

---

## Rules for changing these documents

1. **A number that appears in a document must have been measured.** If it is
   an estimate, it says so. The measurement scripts live alongside the data
   they produced.
2. **The protocol changes before the code, never after.** If the code does
   something the protocol does not describe, the code is wrong.
3. **A parameter chosen because it fits the budget is not a method
   parameter.** If the budget does not allow something, reduce the scope —
   do not bend the rule.
4. **Corrections are written inline, not silently removed.** A retracted
   claim stays visible with the reason. See `04` for an example.

---

## Status — 24 September 2026

- The v2 method is **approved** (`01`) and **not yet implemented** (`02`).
- Ingestion on Render is **suspended**.
- All social and outreach activity is **suspended** until the scale is
  recalibrated.
- The 28,917 historical records were collected under the v1 method and are
  **not valid data**. They are useful only for studying the defects.

---

## Correction log

### 24 September 2026 — external review, reviewer #2

Six claims corrected. All were overclaims by this project, not disputed
opinions; each is now stated at the level the evidence supports.

| # | Claim as published | Problem | Where |
|---|---|---|---|
| 1 | "Only 4.3% entered in the last 24 hours: videos stay in the chart for days" | the table measures age since **publication**, not since entry; entry is unobservable | `03` §5, `05` §5.3 |
| 2 | "No systematic bias at any floor" (14→7 maturity test) | a median ratio of 1.000 is a sensitivity result, not evidence of absence of bias; no CI, paired test or subgroup analysis exists | `01` §2, `03` §8, `05` §5.4 |
| 3 | "truncated from above on our own metric" | YouTube's ranking signal is *correlated with* VPI, not VPI; the evidence supports outcome-related selection, not truncation | `05` §6.1 |
| 4 | "the only alternative would be random sampling" | not established | `05` §6.1 |
| 5 | "it scales as 1/baseline" | two bands establish an association, not a functional law; testing it needs a regression of log(views) on log(baseline) with controls | `01` §8, `05` §6.3, `07` §2 |
| 6 | population "videos that **enter** the trending chart" | we observe first appearance in a daily snapshot, which is a weaker event; the index is not a census of chart entrants | `01` §1, `05` §3 |

Two design changes followed:

- **Missing snapshot.** A gap no longer produces entry events. Records first
  seen after a gap are written with `entry_certain = false` and excluded
  from every statistic that depends on the entry date (`01` §4, `02` §3.2
  and §3.5).
- **The published value.** The record lifecycle — daily trajectory while
  charting, one declared value at exit, always with `days_charting` — is now
  documented (`01` §4.1, `05` §2.1). It was decided on 23/09 but never
  written down, which is why the first dossier appeared to leave the
  measurement age undefined.

Open and **not** accepted: age-standardisation of the denominator (comparing
views at equal age). The API returns only current cumulative views, with no
historical series and no per-video history without channel-owner OAuth. It
becomes possible only from our own longitudinal archive, prospectively.

### 24 September 2026 — reviewer #2, follow-up rounds

**All three publication-blocking defects are cleared.**

| Defect (reviewer's own severity) | Outcome |
|---|---|
| Undefined observation age | **withdrawn by the reviewer** once the record lifecycle was disclosed: the estimand is time-indexed and the closing rule is explicit |
| Outcome-related population selection | not removable; corrected in the claim (`05` §6.1) |
| Entry not observed | not removable; corrected in the population definition (`01` §1, `05` §3) |

Three decisions follow, now written into the protocol (`01` §4.2) and the
specification (`02` §3.2, §3.3, §4.5, §6.2, §6.3, §6.5):

1. **Every cross-video comparison runs at a fixed day index.** `post_daily`
   gains `day_index`; rankings and aggregates read it. A ranking by exit VPI
   is confounded by observation duration and is not published as a
   performance ranking.
2. **Aggregates include active and closed records**, require an actual
   observation at that day, and report `n`. Restricting them to closed
   records conditions on future information.
3. **Age at first observation** is stored (`age_at_first_obs_days`),
   published alongside aggregates, and must be tested for residual effect
   once data exists (regression of `log(VPI)` on age at each day index).

Language rule, permanent: the measure is **age-indexed, never
age-adjusted**. The two public sentences carrying the estimand are quoted
verbatim in `02` §6.5.

### 25 September 2026 — decisions closed after the three reviews

The review is finished: three reviewers, all rounds complete, no follow-up
pending. None of them still regards the method as unpublishable.

**Corrections of fact**

| | |
|---|---|
| Slice count | **544 = 34 x 16** (general chart + 15 categories), of which 96 return 404 and 448 carry data. The earlier "476 (34 x 14)" was never measured |
| YouTube's general chart | **not** a subset of the category charts: 58.8% of its videos appear in no category chart. Its ordering is not by views (Italy: #2 had 14,655 views, #20 had 6,881,481) — it is a curated showcase |
| Naming | the Trending page was retired on 22 July 2025. The population is **YouTube's Most Popular charts**, never "trending" |
| Monotonicity | withdrawn — YouTube removes views on audit, so a daily series can fall |

**Decisions of method**

1. **Baseline anchored to the measured video's own `publishedAt`**, not to the
   measurement date. Without this the denominator absorbed videos published
   during the event it was meant to precede (27% of charting Shorts are 7+
   days old when first seen). Zero cost.
2. **The general chart is not read.** 414 category slices, 1,350 units/day.
   Our own overall ranking is built from the union of the category charts,
   ordered by views, with each video's VPI beside it.
3. **Declared limitation**: Music (~29 items per country), People & Blogs
   (~22), Gaming (~121) are capped well below 200, so for those categories the
   observable window is only the head of the chart.
4. **Exit** = absent from **all** charts, across countries too.
5. **The plaque carries the peak VPI observed**, with views and days in Most
   Popular. Not the exit value: a downward view revision by YouTube after the
   peak is not a demerit of the video.
6. **Cross-video comparisons at day 1 only.** Every record has a day-1
   reading by construction; from day 2 a ranking would silently restrict
   itself to videos that stayed long enough to have that reading. No
   post-exit reading of views.
7. **No segment figure pooled across baseline bands or formats.** Entering a
   200-slot chart needs absolute views, so a large-baseline channel enters at
   1.5x while a small one can only enter at 6,000x; a pooled median moves with
   who happened to chart that day.
8. **The scale**: numeric thresholds set on the first data, then frozen, with
   the calibration vintage printed on the plaque. Any future revision
   published with the how, when and why.

**Dropped, and not to be revived before v1 ships**: category-level averages;
the control analysis on ordinary channel uploads (VPI 1.0x already *is* the
normal video, by construction — only its dispersion survives, as an input to
threshold calibration); a subscriber-count baseline (the API returns only the
current count, rounded to three significant figures, with no history and no
value at publication date, so it cannot be a pre-event denominator).

**Day-0 exclusion, made explicit (decided by Migert, 25/09).** `01` §4 said
day-0 videos never enter; `02` enforced it only by comparing with the
previous snapshot, which fails when a partial run left a day-0 video out of
that snapshot — it would then enter as a false entry. Now: day
0's snapshot is kept permanently (`permanent = true`) as the reference state
of the population; a separate list, `day0_pending`, holds the day-0 IDs not
yet observed absent and drains after each complete run; a day-0 video that
is observed absent and then returns is a legitimate entry. Day 0 must be
complete before day 1 runs (`01` §4, `02` §3.1, §3.1.1, §3.5, `08` T-06,
T-15). `01` §1 also states that **the series begins on day 1** and that the
index carries an explicit start date, a placeholder until T-16, to be filled
in with the day-1 audit (`08` T-17) and shown on the public methodology page
(`02` §6.5).

**GATE-0 decisions (Migert, 25/09).**

1. The v1 pg_cron trigger is **switched off** until T-14. `method_version`
   defaults to `'v1'` and the v2 pipeline writes `'v2'` explicitly, so a
   legacy writer can only produce rows that public queries exclude.
2. **A partial reading observes presence but not absence** (`01` §4): it can
   produce entries, never exits, and is never the reference snapshot for the
   next day. The reference is the last run with `outcome = 'ok'`.
3. `baseline_score` becomes nullable, and a constraint makes the two record
   states (`standard` with baseline and VPI, `not_computable` with neither)
   the only possible ones for v2 rows (`02` §3.2).

**Still to measure when collection resumes**: the 14→7 maturity-floor
sensitivity ran on 167 of 220 channels, excluding by construction the ones
where the floor mattered most. ~660 units.
