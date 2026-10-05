# IOSA — Viral Performance Index (VPI)

**[iosaresearch.org](https://iosaresearch.org)** · an independent, non-profit
index of the YouTube videos that break out against their own channel.

A view count says how big a channel is. It does not say whether a video did
anything unusual. The VPI measures the second thing:

```
VPI = video views / channel baseline, within the same format
```

The **baseline** is the median view count of the same channel's videos in the
same format, published between 7 and 90 days before the measured video was
published: at least 5 of them, at most 20 spread evenly across the window. It
is computed once, when we first observe the video, and then frozen. Anchoring
the window to the video's own publication keeps the denominator pre-event.
Subscribers play no part.

The method passed independent external review and is closed. The
authoritative description is in [`docs/`](docs/README.md); where this page
and `docs/` disagree, `docs/` is right.

## What we observe

- **The population.** Videos **first observed** in YouTube's Most Popular
  category charts, across 34 countries and 13 categories
  (`TARGET_COUNTRIES` and `CATEGORY_MAP` in `backend/census.py`), read once a
  day through the YouTube Data API v3.
- **First observed, not entered.** YouTube exposes no entry timestamp. We see
  that a video is in today's charts and was not in the previous complete
  reading; a video can enter and leave between two readings. The index is not
  a census of chart entrants.
- **YouTube's own general chart is not read.** It is a curated showcase, not
  ordered by views. Our overall ranking is the union of the category charts,
  ordered by views, with each video's VPI beside it.
- **The series starts on 27 September 2026** (`INDEX_START_DATE` in
  `backend/vpi_core.py`). Earlier readings are kept as reference states and
  are not published.
- **Two formats, never mixed and never compared.** A Short is what YouTube
  calls a Short: a square or vertical video up to three minutes long (up to
  60 seconds for uploads before 15 October 2024). Everything else is
  long-form. The rule is in `formato()` in `backend/vpi_core.py` and in
  `docs/01` §1.1.
- **For now only long-form is measured** (`MEASURED_FORMATS` in
  `backend/vpi_engine.py`). Shorts are read and recorded in the daily
  snapshot but get no baseline and no VPI. This is a declared, provisional
  limit forced by the API quota, not a property of the method.

## What a published number says

- While a video is charting, its VPI is recomputed every day it is observed.
  The public sees the trajectory and no award.
- When the video leaves all charts, the record closes. The published value is
  the **highest VPI observed**, always shown with the view count and the
  number of days in Most Popular. Not the exit value: YouTube removes views
  on audit, so a series can fall.
- Videos are compared with each other only **at day 1**, the first day each
  was observed. No figure is ever pooled across baseline bands or across
  formats.
- High levels come almost entirely from channels with a small baseline. That
  follows from the chart-entry threshold, not from the metric, and it is
  disclosed with the figures of the latest audit
  ([`docs/09-day1-audit.md`](docs/09-day1-audit.md),
  [`docs/04-bias-and-scale-analysis.md`](docs/04-bias-and-scale-analysis.md)).
- The measure is **age-indexed, never age-adjusted**.
- A record whose baseline cannot be computed exists without a VPI. It is never
  discarded, and never computed under a different rule.

## The level scale

Ten levels on the VPI, set by the project owner. Thresholds and names are
defined once in `VPI_SCALE` (`backend/vpi_core.py`), mirrored in
`frontend/src/lib/vpi-scale.ts` and in `docs/01` §4.3; a test keeps them in
agreement. Below the first threshold a record has a VPI and no level.

## Records

Records never expire and are never deleted. If your video appears in the
index and you would rather it did not, write to us: the record is hidden from
every public page and from the public API.

## How it runs

One reading a day at a fixed UTC time: `pg_cron` on Supabase calls
`POST /api/ingest/run`. A second attempt fires when the day is not complete,
and a morning pass after the quota reset finishes what the quota did not
reach. A day whose chart census is complete is never read again: whatever is
left is finished from the stored snapshot. Schedules are in
`supabase/migrations/` and in `docs/02` §5.

## Repository

| Path | What it is |
| --- | --- |
| `docs/` | **the authoritative documentation**: method, specification, measurements, plan, audits |
| `docs/task-log.md` | the state of the work |
| `CLAUDE.md` | working agreement for Claude sessions in this repository |
| `backend/vpi_engine.py` | the daily run: census, new records, daily updates, closes |
| `backend/census.py` | reads the Most Popular category charts |
| `backend/baseline.py` | computes and freezes the baseline |
| `backend/vpi_core.py` | the ratio, the format rule, the scale, the series start |
| `backend/quota.py` | the quota brake |
| `backend/reprocess_day.py` | finishes a day from its stored snapshot |
| `backend/retention.py` | archives snapshot rows to Storage before they are deleted |
| `backend/main.py` | FastAPI service: ingestion trigger, public API, plaque, claim |
| `supabase/migrations/` | schema, row-level security, `pg_cron` schedules |
| `frontend/` | the Next.js site |
| `tests/`, `backend/tests/` | the test suite and the nightly check (`tests/check_run.sql`) |
| `archive/` | v1 code, kept for the record, not in use |

**Stack:** Python and FastAPI on Render · Supabase PostgreSQL with row-level
security and `pg_cron` · Next.js on Vercel · YouTube Data API v3. Runtime
versions are pinned in `.github/workflows/ci.yml`.

Data comes from the official API only. There is no scraping.

## Funding

IOSA is self-funded. A creator whose video is in the index can claim a plaque
of the record from its page; ordering printed items is currently switched off.

## Contact

X [@IOSAResearch](https://x.com/IOSAResearch) ·
Instagram and Threads [@iosa.research.lab](https://instagram.com/iosa.research.lab) ·
Bluesky [@iosaresearch.bsky.social](https://bsky.app/profile/iosaresearch.bsky.social)
