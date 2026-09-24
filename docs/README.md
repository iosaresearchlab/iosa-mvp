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
| `review-data/` | Anonymised data package supporting the dossier's figures. | External reviewers | Durable until re-measured |

---

## The dependency between them

```
03 measurements  ──┐
04 bias analysis ──┼──>  01 methodology protocol  ──>  02 technical spec  ──>  code
                   │              │
                   └──────────────┴──>  05 review dossier  ──>  external reviewers
```

Read in this order if you are new: **05** for the whole picture, then **01**
for the method, then **02** if you are going to write code.

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
