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
- All social and outreach activity is **suspended**. *(25/09: the scale is
  set by the owner, `01` §4.3; it no longer gates anything.)*
- The 28,917 historical records were collected under the v1 method and are
  **not valid data**. They are useful only for studying the defects.

---

## Correction log

### 4 October 2026 — FMT-1: a Short is what YouTube calls a Short (Migert)

The split by duration alone (Short = up to 180 s) is not YouTube's rule:
YouTube's Short is a **square or vertical** video up to three minutes
(YouTube Help 15424877, from 15/10/2024; 60 s before). Measured on the
entries of 03/10 (`03` §11, 23 units): the API returns the shape
(`player.embedWidth/embedHeight` with `maxHeight`) for every video, at no
extra cost, and **2.5% of the entries up to 180 s are wider than tall**:
long-form for YouTube, called Shorts by the old rule and never measured.

- **The rule** is `01` §1.1 (duration and shape), built as `02` §4.9. It
  applies to every record opened from the first reading after the deploy;
  each record carries `format_rule` (`youtube_shape`, or `duration_180` for
  those opened before).
- **Live broadcasts are recorded, not reclassified**: `posts.was_live`. 17 of
  100 long-form entries of 03/10 had been live broadcasts.
- **Every record from the start of the series is brought under the rule**
  (FMT-2, owner, 04/10/2026, option A of three): the videos the old rule left
  out are measured as of their first observation, the old records are
  recomputed where their samples change, with the quota the daily reading
  leaves (`02` §4.10). The database holds no shape for them (`03` §11.1), so
  it costs a re-read: ~8,000 units, *estimated*.
- **Snapshot retention is not suspended** (owner's condition: suspend only if
  archiving harmed the recovery; it does not). The archive is an exact copy,
  and the recovery already needs it for 26/09.
- **FMT-2 as built** (developer, 04/10): what "changed" means exactly, the
  list of the inventory items unknown when FMT-1 started (captured before
  the first reading under FMT-1: without it a night's re-read would lose
  which items were old Shorts), and how a stopped run resumes (`02` §4.10,
  *As built*).
- **Out of FMT-2** (architect, 04/10): night 1, before `INDEX_START_DATE`.
  **Phase 3** (owner, 04/10): the 2,787 records (1,196 channels, measured
  04/10) whose window the capped inventory has dropped since their baseline
  read are checked too, by listing their channels' uploads again down to
  that read (estimate ~5,300 pages + ~1,700 `videos.list` calls, on
  leftover quota). Only a record whose check cannot be complete (an item
  deleted or made private since, a channel no longer listable) keeps
  `duration_180`, in `fmt2_left`; the final count is declared here when
  FMT-2 closes.
- *(Corrected: `01` §1 population, §1.1 new, §2 inventory note, §7;
  `02` §0, §3.1.2, §4.3, §4.4, §4.9 and §4.10 new; `03` §11 new; `04` filter table;
  `05` formats and limitation; `06` project description; root `README.md`.)*

### 29 September 2026 — INC-1: the reading of 28/09, and the census as the reference (Migert)

The reading of 2026-09-28 completed its chart census (442 slices, 0 errors,
27,455 videos in the snapshot) and then failed on the 8 s statement timeout
in the entry query (no index on `posts.external_post_id`; fixed, INC-1).
Owner decision: nothing is thrown away and the day gets its VPIs.

- **A complete census is the reference and a starting point for
  reprocessing, whatever broke after it** (`01` §4, `02` §5). The split of
  27/09 (census vs baselines) now also covers a crash: `census_complete`
  decides the reference, not `outcome`.
- **`reprocess_day`** finishes such a day from its stored snapshot, never
  re-reading the charts; the 00:30 second attempt resumes instead of
  answering 409; the 08:20 UTC morning pass completes the records a quota
  stop left without a VPI.
- **28/09 was reprocessed on 29/09.** Its numerators are the views stored at
  23:59; its baselines were read about fifteen hours late (the window is the
  same, anchored to publication; only the window videos' view counts are
  later). **Bookkeeping:** every such record carries `reprocessed_at`, and
  `baseline_computed_at` is the actual read time, so the late read can
  always be told apart. Accepted explicitly by the owner.
- Titles of the reprocessed records come from `videos.list` at reprocess
  time (the snapshot does not store titles); `country`/`category` are the
  first of the record's sets in canonical order.
- **Standing rule: completeness before read-timing precision** (`CLAUDE.md`
  §3). A missing record is a visible defect; a few hours of delay in reading
  a baseline is not.
- **Brake 9,500 → 9,900** (owner). Exceeding the real 10,000 costs no penalty;
  the margin only keeps the stop at a recorded point. What the brake does
  not reach is `quota_stop`, completed by the morning pass.
- **The second attempt fires whenever the day is not complete** (`02` §5):
  no run, a failed run, an incomplete census, or a complete census whose
  processing did not finish; a complete census is resumed, never re-read.

### 28 September 2026 — GATE-3, snapshot retention (Migert)

**GATE-3: GO**, on `09-day1-audit.md`, no condition attached.

**Snapshot retention: 7 days, no exception for day 0.** Once the first day
has been analysed and the system is in steady state, day 0 is a day like any
other: snapshots are working data, not an archive. The `permanent` column
existed only to exempt day 0 and is dropped. Every day leaving the window is
exported to Supabase Storage (private bucket `archivio`, one gzip file per
day), read back and verified, and only then deleted (`02` §3.1; `01` §1 and
§4 no longer say the day-0 snapshot is kept permanently). This supersedes
"day 0's snapshot is kept permanently" in the 25 September entries below.

**`posts_v1` reduced to what the v1 claim reads.** Every column exported to
Storage and verified first; the table keeps the 16 columns the claim page,
the plaque and the order flow read from a v1 record, so the claim links
already sent keep working (`02` §3.6).

### 27 September 2026 — perimeter: long-form only; the two completeness states (Migert)

**Vintage boundary.** Night 1 (2026-09-26) is a distinct vintage: both
formats, 6,138 records — 1,897 with a VPI, 205 `not_computable`, 4,036
`quota_stop` (the brake fired at 9,500 units). All kept, none deleted.
**From the next run (2026-09-27) the perimeter is long-form only and
`quota_stop` is an incident, not a state.** ~~Whether night 1 belongs to the
published series is the owner's decision, later; nothing here assumes
either way.~~ **Decided the same day (Migert): nights 0 (25/09) and 1
(26/09) are reference-only.** They stay in the database and remain
reference states — they are what makes the next night's entries computable
— but they are not part of the published series: night 1 mixed both formats
and left two thirds of its entries without a VPI. The published series
starts on the first run that passes `tests/check_run.py`; its date is set in
`01` §1, `02` §6.5 and the site (`INDEX_START_DATE`) once it passes, and
until then no record is published. Nothing is deleted.

- Shorts are out of the measurement for now (`01` §1): a scope reduction
  forced by the quota, declared and provisional. The census is unchanged.
- `02` §4.6 corrected: a quota stop is not a missed reading. The census
  alone decides the reference, the exits and entry certainty; baseline
  completeness decides only each record. Night 1's run report is re-labelled
  `ok` under the corrected rule.
- Reads: the uploads playlist id is read from `channels.list`, no longer
  derived from the channel id; `videos.list` on warm channels checks only
  unknown or measured-format ids (exact). Choosing candidates spread across
  the window before `videos.list` was proved to be a different estimator
  and is not applied. The `itemCount` skip was proved exact and measured not
  to pay; it is off.

### 25 September 2026 — privacy, v1 archive, claim tokens (Migert)

- `claims` was publicly readable (policy granted to PUBLIC) and would have
  exposed buyers' names, emails and addresses. Closed; the table was empty.
- The v1 records move out of `posts` into `posts_v1` (`02` §3.6 correction):
  flagging in place would have put two rules on the scale the site reads.
- The `claim_token` blocker raised at T-12 is withdrawn, not a defect: the
  token is a public identifier of a plaque, not a secret. Anyone may look at
  a plaque; only the creator can earn one.

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

**GATE-1 decisions (Migert, 25/09).**

1. `posts.vpi_level_name`, `vpi_color`, `author_handle` become nullable, and
   `posts_baseline_state` extends to the level, its name and its colour: they
   exist exactly when the VPI does (`02` §3.2).
2. **Baseline bands, provisional**: decades, `<100` to `>=100k`, never re-cut
   after seeing which split produces a nicer number (`01` §4.2).
3. **`day0_pending` dropped.** With the reference always the last complete
   reading it excluded nothing; the permanent day-0 snapshot stays as the
   archive (`01` §4, `02` §3.1.1).
4. `claim_token` publicly readable: a blocker on any public deployment
   (`docs/task-log.md`).

**GATE-2 decisions (Migert, 25/09).** Measured at T-13: 3.24 units per
channel read cold. No country reduction, no preliminary measurement run. Two
read optimisations that change no baseline — a persistent inventory of each
channel's uploads (ids, dates, durations; views are never cached) and one read
per channel per run — then the plan as written. The 9,500 brake stays;
entries it stops are valid records without a VPI, `baseline_rule =
quota_stop`, declared in the run report. T-13 closes against the kill-proof
call log. Perimeter tuning afterwards, on costs measured in production.

**Still to measure when collection resumes**: the 14→7 maturity-floor
sensitivity ran on 167 of 220 channels, excluding by construction the ones
where the floor mattered most. ~660 units.
