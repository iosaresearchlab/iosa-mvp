# IOSA — Viral Performance Index (VPI)

**[iosaresearch.org](https://iosaresearch.org)** · independent non-profit study
of video performance relative to a channel's own baseline.

> **Status, 25 September 2026.** The method was rebuilt after an external
> review and the v2 documentation in **[`docs/`](docs/README.md)** is the only
> authoritative description. Collection is suspended while v2 is implemented
> (see `docs/08-implementation-plan.md`). Parts of this page still describe
> v1 and are corrected below where they were plainly wrong; the rest is
> rewritten when v2 goes live.

A view count says how big a channel is. It does not say whether a video did
anything unusual. The VPI measures the second thing:

```
VPI = views of the video / median views of that channel's recent videos
                           in the same format
```

Two formats are measured and never mixed: **Shorts** (≤180s) and
**long-form** (>180s).

Because the reference is the channel's own baseline, a 20,000-subscriber
channel and a 9-million-subscriber channel can appear on the same scale
honestly. A Short at 3× its own baseline is a real outlier whether it did
30,000 views or 3 million.

## The scale

| VPI | Level | Name |
| --- | --- | --- |
| ≥ 50 | 10 | Hyper Outlier |
| 25 – 49.9 | 9 | Mega Outlier |
| 15 – 24.9 | 8 | Outlier |
| 10 – 14.9 | 7 | Super Viral |
| 7.5 – 9.9 | 6 | Viral |
| 5 – 7.4 | 5 | Breakout |
| 3 – 4.9 | 4 | Trending |
| 2 – 2.9 | 3 | Rising |
| 1.5 – 1.9 | 2 | Moderate |
| < 1.5 | 1 | Standard |

The scale is defined once, in `backend/vpi_core.py`, and mirrored for the
frontend in `frontend/src/lib/vpi-scale.ts`.

**These thresholds are inherited from v1 and await recalibration.** On
historical data level 10 holds 16.8% of records, which is not a usable top
band. They must not be cited as settled. See
`docs/04-bias-and-scale-analysis.md`.

## What is measured, and what is not

- Shorts (≤180s) **and** long-form (>180s), from the official platform APIs,
  never mixed in one figure.
- **v2**: the *baseline* is frozen at the video's entry into the index; the
  *view count* is re-read every day the video is observed in YouTube's Most
  Popular charts, and the published figure is the peak reached. (The sentence
  previously here — views frozen at measurement, records expiring after 15
  days — described v1 and is no longer the method.)
- Records do not expire. Once written, a record stays.
- The baseline is a median, not a mean, so one earlier spike on the same
  channel does not flatten the next one.

Known limits: a channel that publishes rarely, or whose recent Shorts are
unrepresentative, gets a fragile baseline — a broadcaster posting clips can
show an extreme ratio that means very little. Those cases are visible in the
data, not hidden from it.

## Repository

| Path | What it is |
| --- | --- |
| `backend/vpi_engine.py` | ingestion: queries the official APIs, computes baselines and ratios |
| `docs/` | **the authoritative documentation** — method, spec, measurements, implementation plan |
| `CLAUDE.md` | working agreement for Claude sessions in this repository |
| `backend/vpi_core.py` | the scale and the ratio, single definition |
| `backend/main.py` | FastAPI service: ingestion trigger, analytics, plaque rendering |
| `backend/generate_trophy.py` | renders a creator's digital plaque |
| `backend/backfill_vpi.py` | batch recalculation and cleanup |
| `frontend/` | Next.js dashboard: leaderboard, insights, creator pages |

**Stack:** Python 3.12 · Supabase (PostgreSQL, RLS) · Next.js / React ·
YouTube Data API v3 · TikTok Commercial Research API.

Data collection uses official APIs only. There is no scraping.

## Status

Running, and openly a work in progress. The dashboard is live at
[iosaresearch.org](https://iosaresearch.org); the leaderboard and the macro
insights are public and free to read, with no account.

## Contact

Instagram [@iosa.research.lab](https://instagram.com/iosa.research.lab) ·
X [@IOSAResearch](https://x.com/IOSAResearch)

If your channel appears in the index and you would rather it did not, write to
us and it is removed.
