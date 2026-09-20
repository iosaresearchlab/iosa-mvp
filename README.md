# IOSA — Viral Performance Index (VPI)

**[iosaresearch.org](https://iosaresearch.org)** · independent non-profit study
of short-form video performance.

A view count says how big a channel is. It does not say whether a video did
anything unusual. The VPI measures the second thing:

```
VPI = views of the video / median views of that channel's recent Shorts
```

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

## What is measured, and what is not

- Only short-form video, 0–180 seconds, from the official platform APIs.
- The view count is **frozen at the moment of measurement**. It is not updated
  afterwards, so ratios stay comparable between channels measured on different
  days. Every published figure carries its measurement date for this reason.
- A measurement stays active for 15 days, then expires. Nothing is claimed
  about a video after that window.
- The baseline is a median, not a mean, so one earlier spike on the same
  channel does not flatten the next one.

Known limits: a channel that publishes rarely, or whose recent Shorts are
unrepresentative, gets a fragile baseline — a broadcaster posting clips can
show an extreme ratio that means very little. Those cases are visible in the
data, not hidden from it.

## Repository

| Path | What it is |
| --- | --- |
| `backend/vpi_engine_2.py` | ingestion: queries the official APIs, computes baselines and ratios |
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
