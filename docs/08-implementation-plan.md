# Implementation Plan — v2

**Status: approved 25 September 2026.** Derived from
`02-technical-specification.md`. The methodology is closed
(`01-methodology-protocol.md`); this document only says in what order to
build it and how each step proves itself.

---

## 0. How this loop works

Tasks run **in order**. A task is closed only when its **closing check**
passes — a command that returns a verdict, not an opinion. If the check
fails, the task stays open and is worked again. Nothing downstream starts.

```
pick the first open task
  -> implement
  -> run its closing check
       pass  -> commit, mark closed, next task
       fail  -> stay on this task
  -> at a GATE: stop, report, wait for a decision
```

Three rules that make the loop honest:

1. **A check is a command, not a judgement.** "It looks right" never closes a
   task.
2. **One task, one commit.** The commit message names the task ID. A failed
   check is never committed as closed.
3. **A gate is a hard stop.** No gate is passed on the assumption that the
   next check will pass.

Standing invariants, verified by `CHK-REG` after every task:

- **Printify must not break.** Its branch is suspended, not removed.
- Stripe, checkout, trophy generation and existing claim tokens keep working.
- The frontend keeps building.
- No public copy changes before GATE-2.

---

## Phase 0 — make the loop possible

Nothing here touches measurement. Without it there is no closed loop, only
good intentions.

### T-01 — test and CI scaffolding
Create `tests/` and a GitHub Actions workflow that runs on every push to
`docs/methodology-v2` and on pull requests: install `backend/requirements.txt`,
run `pytest -q`, run `npm ci && npm run build` in `frontend/`.

- **Files**: `.github/workflows/ci.yml`, `tests/__init__.py`,
  `tests/conftest.py`, `backend/requirements-dev.txt` (pytest, pytest-cov,
  responses)
- **Closing check**: the workflow runs green on a trivial pushed commit, and
  `pytest -q` passes locally.
- **Rollback**: delete the workflow file; nothing else depends on it.

### T-02 — regression harness for what must not break
A single command that asserts the standing invariants. It is re-run as
`CHK-REG` after every later task.

- **Files**: `tests/test_regressione.py`
- **Asserts**: `backend/printify_service.py` imports and its public functions
  are present; `backend/trophy_pipeline.py` and `generate_trophy.py` import;
  every route registered in `main.py` today is still registered; the frontend
  build exits 0.
- **Closing check**: `pytest -q tests/test_regressione.py` green **against
  today's untouched code**. If it is not green now, it is testing the wrong
  thing.
- **Rollback**: n/a.

### T-03 — pin the current behaviour of the measurement core
Characterisation tests for `vpi_core.py` **as it is**, so that later changes
show up as intentional diffs rather than surprises.

- **Files**: `tests/test_vpi_core_baseline_attuale.py`
- **Closing check**: green on current code, and each assertion names the
  behaviour it pins.
- **Rollback**: n/a.

---

## Phase 1 — database

### T-04 — migration: new tables
`trend_snapshot`, `post_daily` (with `day_index`), `ingest_run`, indexes, RLS
as specified in `02` §3.1, §3.3, §3.4.

- **Closing check**: `list_tables` shows the three tables with the expected
  columns; an insert-then-select round trip succeeds for each; RLS is enabled
  on all three.
- **Rollback**: `drop table` for the three; nothing reads them yet.

### T-05 — migration: new columns on `posts`
Per `02` §3.2, including `entry_certain`, `age_at_first_obs_days`, `gap_days`,
`baseline_video_ids`, and making `vpi_ratio` / `vpi_level` nullable.

- **Closing check**: every column present with the right type; a row with
  `vpi_ratio = null` inserts successfully; the existing 28,917 rows are
  unchanged (`count(*)` and a checksum of `id, external_post_id` match the
  values recorded before the migration).
- **Rollback**: `drop column` for the added columns; the `not null` removal
  stays, it is harmless.

### T-06 — `entries_of_day()` and the archiving of v1
The SQL function from `02` §3.5, the `permanent` column and the
`day0_pending` table from `02` §3.1 / §3.1.1 (the table was dropped at
GATE-1: see `02` §3.1.1), and
`update posts set method_version='v1' where entered_on is null`.

- **Closing check**: `tests/test_entries.py` green on a seeded
  `trend_snapshot` covering: normal entry, exit, re-entry, day 0 with no
  previous snapshot, **a missing day** (which must produce
  `entry_certain = false`, never a certain entry), **a day-0 video still
  present** (never a record), and **a day-0 video observed absent that then
  returns** (a record). Plus:
  `select count(*) from posts where method_version='v1'` = 28,917.
- **Rollback**: `drop function`; reset `method_version`.

**GATE-0 — database.** All of T-04..T-06 closed, `CHK-REG` green. The old
engine still runs unchanged at this point; if it does not, stop.

---

## Phase 2 — the measurement

### T-07 — `backend/census.py`
`read_charts()`, `save_snapshot()`, `entries()`, `close_exits()` per `02`
§4.3. **414 category slices, not the general chart.** `CATEGORY_MAP` drops to
13 entries (19 and 27 removed).

Plus the partial-reading rule of `01` §4: `entries_of_day()` takes as
reference the most recent day with `ingest_run.outcome = 'ok'` (`02` §3.5), and
`close_exits()` never runs after a partial run (`02` §4.3).

- **Files**: `backend/census.py`, `tests/test_census.py`, a migration
  replacing `entries_of_day()`, `tests/test_entries.py` extended
- **Closing check**: `tests/test_census.py` green on mocked HTTP —
  pagination to exhaustion, 404 on a slice skips it without failing the run,
  403 stops everything with `outcome='partial'`, dedup across slices, and the
  call count for a 3-country fixture equals the expected number exactly;
  `close_exits(day, run_complete=False)` makes no database call.
  `tests/test_entries.py` green, including: yesterday partial -> the
  reference is the last complete day and the entry is uncertain; entries
  detected during a partial run when the reference is yesterday.
- **Rollback**: the module is new and unreferenced; delete it.

### T-08 — `backend/baseline.py`
Per `02` §4.4, with the **window anchored to the measured video's
`publishedAt`** (`01` §2), pagination up to 3 pages, at least 5 samples, at
most 20 spread evenly, `baseline_rule` set to `standard` or
`not_computable`, and `baseline_video_ids` stored.

- **Files**: `backend/baseline.py`, `tests/test_baseline.py`
- **Closing check**: `tests/test_baseline.py` green — blocks of 50 for
  `channels.list` / `videos.list`, `UC`→`UU`, pagination stops at 3, the date
  filter runs **before** `videos.list` (asserted by call count), even
  sampling across the window, `not_computable` when fewer than 5 samples
  survive, and the window computed from `publishedAt` **not** from today (a
  fixture with a video published 40 days ago must select a different sample
  set than the same channel measured today).
- **Rollback**: delete the module.

### T-09 — quota counter and brake
One counter incremented by every call, written to `ingest_run`; hard brake at
`QUOTA_MAX_DAILY` (default 9,500) producing `outcome='partial'`.

- **Files**: `backend/quota.py`, `tests/test_quota.py`
- **Closing check**: a fixture run with the limit set to 10 stops at exactly
  10 calls and reports `partial`; the counter equals the number of HTTP calls
  the mock recorded, with no drift.
- **Rollback**: delete the module.

### T-10 — rewrite the ingestion entry point
`fetch_and_ingest_real_youtube_content` replaced by the daily procedure of
`01` §4: census → snapshot → entries (baseline, frozen) → update views →
close exits → run report. Randomised processing order, so that a partial run
does not systematically drop the same slices.

- **Files**: `backend/vpi_engine.py`
- **Closing check**: `pytest -q` fully green, including the rewritten
  `tests/test_formati_motore.py`; plus an end-to-end test on mocks that
  writes one full simulated day and asserts the resulting rows in
  `posts`, `post_daily` (with `day_index = 1`) and `ingest_run`. Every
  `posts` row it writes carries `method_version = 'v2'` **explicitly** (the
  column default is `'v1'`).
- **Rollback**: the old function is kept in `archive/backend/` for one
  release, so a revert is a one-line import change.

### T-11 — move the dead branches to `archive/`
TikTok branch and `weekly_digest.py` per `02` §4.2. **Printify is not
touched.**

- **Closing check**: `CHK-REG` green; `grep -r "tiktok" backend/ --include=*.py`
  returns nothing outside `archive/`.
- **Rollback**: `git mv` back.

**GATE-1 — the engine.** T-07..T-11 closed, `pytest -q` green, `CHK-REG`
green. **Nothing has called the real API yet.**

---

## Phase 3 — API

### T-12 — endpoints
Per `02` §4.5: `/api/posts` (`min_vpi` default 0, `method_version='v2'`),
`/api/analytics/top10` rewritten on `post_daily` at `day_index = 1`,
`/api/analytics/insights` with segment figures by baseline band and format
only, `POST /api/ingest/run` with the daily lock (409), new
`GET /api/ingest/status`. Trophy / checkout / Stripe **unchanged**.

- **Files**: `backend/main.py`, `tests/test_api.py`
- **Closing check**: `tests/test_api.py` green — each endpoint's shape, the
  409 on a second run for the same day, and an assertion that **no segment
  response pools baseline bands or formats**. `CHK-REG` green.
- **Rollback**: revert the file; the frontend still reads the old shapes
  until T-18.

---

## Phase 4 — dry run against the real API

### T-13 — dry run on 3 countries
`QUOTA_MAX_DAILY=2000`, 3 countries, real API key, writing to a scratch
schema or with a `dry_run` flag that rolls back its writes.

- **Closing check** *(changed at GATE-2, 25/09: the console is not reachable
  from the session)*: the counter matches the kill-proof call log — one line
  per HTTP attempt, written before it is sent — **to the unit**, on a re-run of
  the same perimeter with the channel inventory. Any discrepancy is a bug in
  the counter, not a rounding difference.
- **Rollback**: truncate the scratch rows.

**GATE-2 — decision point.** The counter is trustworthy, or the day-0 run is
not attempted. Report the measured consumption before proceeding.
*Passed 25/09 by Migert's decision: no country reduction; channel inventory
and per-run dedup; the brake stays, entries it stops are `quota_stop`
records.*

---

## Phase 5 — day 0, day 1, and the go/no-go

### T-14 — scheduling and reactivation
`cron.job` to `59 23 * * *` and **re-enabled** (switched off at GATE-0),
Render reactivated, `IOSA_ENGINE_MODE` left `off` so only the HTTP trigger
runs the job.

- **Closing check**: `GET /api/ingest/status` answers from the deployed
  service; the pg_cron job is listed with the new schedule; a
  snapshot-only reading of one country, with the real API, against the test
  database (as at T-13) ends `outcome='ok'` with the call log equal to the
  counter. **Changed 25/09/2026 (Migert):** the one-country run was a manual
  trigger on production; it would have written that day's `ingest_run` row
  and refused day 0 the same night.
- **Rollback**: disable the cron job, suspend Render.

### T-15 — day 0: snapshot only
One full run with `SNAPSHOT_ONLY=true`. Expected spend **1,350 units**.

- **Closing check**: `trend_snapshot` holds one row per (day, video) with
  ~28,000 distinct videos, all with `permanent = true`; `ingest_run` reports
  `outcome='ok'` and `quota_total` within 5% of 1,350; **zero rows written
  to `posts`**.
- **This check protects the archive, not only the quota budget.** An
  incomplete day 0 cannot produce false entries (it is not a reference), but
  the permanent record of the population at the start would have a hole
  (`02` §3.1.1). T-16 does not start until this check passes.
- **Rollback / on a partial day 0**: delete that day's snapshot rows and
  re-run day 0. Do not proceed.

### T-16 — day 1: first real records
Second full run. This is the first day of the index.

- **Closing check**: `ingest_run.outcome='ok'`; `quota_total ≤ 9,500`;
  entries detected > 0; for every new record either `baseline_rule='standard'`
  with `vpi_ratio not null`, or `baseline_rule='not_computable'` with
  `vpi_ratio null` — no third case, and the constraint
  `posts_baseline_state` (`02` §3.2) makes one impossible; every record has a `post_daily` row at
  `day_index = 1`; `entry_certain = true` for all (no gap yet).
- **Rollback**: the run is idempotent per day; delete the day's rows and
  re-run.

### T-17 — day 1 audit and data validation
The numbers that decide whether this is a measurement or not:

| Reading | Why |
|---|---|
| `quota_total` | over 9,500 → reduce `BASELINE_SAMPLES_MAX` to 10, re-measure; still over → reduce countries, and only that |
| share of `baseline_rule='not_computable'` | the real coverage, against the 88.6% measured on the sample |
| 24-hour turnover of videos and channels | never measured; it drives steady-state cost |
| distribution of `age_at_first_obs_days` | the confounder we disclose |
| VPI distribution **by baseline band** | if the bands are as far apart as on v1 data, the scale must be set per band |
| rows written, bytes per row | the 500 MB free tier |

- **Closing check**: a written audit committed to
  `docs/09-day1-audit.md`, containing every figure above, computed by a
  script committed alongside it. No figure estimated.
- **Same commit: the start date.** The `YYYY-MM-DD` placeholder in `01` §1 is
  replaced with the date of the first successful day-1 run (T-16), and the
  same date is written into the text that `02` §6.5 prescribes for the public
  methodology page. `grep -rn "YYYY-MM-DD" docs/` returns nothing. The
  claude.ai project description must state the date too: Migert pastes it,
  since no session can edit it — the check is his confirmation.

**GATE-3 — GO / NO-GO.** Decided on the audit, by Migert. *(25/09/2026: the
scale is no longer part of it, `01` §4.3; the frontend work no longer waits
for it, by the owner's decision to put the app back online.)*

---

## Phase 6 — frontend and public material

~~Only after GATE-3.~~ Now, by the owner's decision of 25/09/2026 to put the
app back online.

### T-18 — data layer and the overall chart
`lib/supabase-server.ts` per `02` §6.1; `app/page.tsx` shows **our own
overall chart**: the union of the category charts ordered by views, with each
video's VPI beside it.

- **Closing check**: `npm run build` exits 0; the page renders against real
  v2 data; the two false claims at lines 750 and 759 and the "15-day window"
  at line 439 are gone (`grep` returns nothing).

### T-19 — leaderboard at day 1
Per `02` §6.3: VPI ranking on `post_daily` at `day_index = 1`, titled "Top
VPI — first day observed", with `n` and the range of
`age_at_first_obs_days` displayed, and the peak-VPI table as a separate
section labelled "highest values observed".

- **Closing check**: build green; no day selector present; the query filters
  `day_index = 1` (asserted in a test, not by reading the code).

### T-20 — claim page and plaque
`app/claim/[token]/page.tsx`: expiry from `entered_on + CLAIM_DAYS` computed
server-side; the plaque carries **peak VPI, views, days in Most Popular**;
"MEASUREMENT EXPIRED" and the 15-day copy removed.

- **Closing check**: build green; an existing claim token issued under v1
  still resolves (`CHK-REG` covers this); the three figures are present on the
  rendered plaque.

### T-21 — public methodology text
`components/MetodologiaModal.tsx` rewritten per `02` §6.5, including verbatim
the two sentences that carry the estimand and the phrase **"Most Popular"**
as the name of what we read.

- **Closing check**: `tests/test_frontend_methodology.py` green. It bans
  claims, not a word: no frontend copy states or implies that a video
  "entered Trending", or treats YouTube's retired Trending page (removed 22
  July 2025) as the population; "popular" appears only as the proper name
  "Most Popular", never to describe what VPI means (popularity is absolute
  views, VPI is performance against the channel's own baseline); "Most
  Popular" names what we read. Comments are not copy; a level label such as
  "Lvl 4 - Trending" carries no claim about YouTube's chart. Plus: `grep "VPI
  ≤ 1.0x is excluded"` returns nothing; the two estimand sentences are
  present. *(Reformulated 25/09/2026, Migert: the first version banned the
  string "trending" and forced a level rename, now reverted.)*

---

## Phase 7 — accumulation

### T-22 — three weeks, nothing published
Collection runs. No statistics published.

- **Closing check**: 21 consecutive `ingest_run` rows with
  `outcome='ok'`; zero days with `entry_certain=false` records, or a written
  explanation for each.

### T-23 — the deferred measurements
- The 14→7 maturity-floor sensitivity, re-run on all 220 channels including
  the 53 the earlier test excluded by construction (~660 units).
- Spillover: `baseline_at_exit / baseline_at_entry` on the same
  `baseline_video_ids`, against matched control channels — correlation alone
  proves nothing.
- Dispersion of ordinary channel uploads, as an input to threshold
  calibration.

- **Closing check**: each result committed under `docs/`, with the script
  that produced it.

### ~~T-24 — scale calibration~~
Removed 25/09/2026: the thresholds are set by the project owner (`01`
§4.3), who may change them at any time. Not a task, not a gate.

### T-25 — final review and production
Full re-read of the documentation, external review pass on the closed
solution with real distributions in hand, then live.

---

## Milestone C — collection (outside the loop)

*(Owner decision, 25/09/2026.)* A task whose closing check cannot pass
without elapsed collection time is not a loop task: the loop does not wait
on the calendar. These close when the calendar lets them, each still on its
own closing check above, and are reported as they do:

| Item | Needs | Earliest |
|---|---|---|
| T-15 day 0 | tonight's 23:59 UTC reading | 26/09 00:10 UTC |
| T-16 day 1 | the next night's reading | 27/09 |
| T-17 day-1 audit, and the start date | T-16 | 27/09 |
| GATE-3 GO / NO-GO | T-17, decided by Migert | after T-17 |
| T-18 "renders against real v2 data" (the rest of T-18 is in the loop) | T-16 | 27/09 |
| T-22 three weeks | 21 readings | mid-October |
| T-23 deferred measurements | spillover needs exits and matched controls | after T-22 |
| T-25 final review | real distributions in hand, external reviewers | after T-23 |

The loop itself ends with T-21.

---

## Closing checks, as commands

```
CHK-REG    pytest -q tests/test_regressione.py && (cd frontend && npm run build)
CHK-UNIT   pytest -q
CHK-CI     the GitHub Actions workflow green on the pushed commit
CHK-DB     Supabase: list_tables + the round-trip assertions of T-04/T-05
CHK-QUOTA  ingest_run.quota_total vs the Google Cloud console, to the unit
```

`CHK-REG` runs after **every** task, not only where it is named.

---

## What this plan does not do

- It does not touch Printify.
- It does not change any public copy before GATE-3.
- It does not read videos after they leave the charts.
- It does not publish a segment figure pooled across baseline bands or
  formats.
- It does not treat the 28,917 v1 records as anything other than archived
  and flagged.
