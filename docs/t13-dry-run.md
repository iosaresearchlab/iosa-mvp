# T-13 — dry run on 3 countries, 25 September 2026

Measured with `tests/dry_run_t13.py` against the real YouTube Data API v3,
`QUOTA_MAX_DAILY=2000`, countries IT, US, DE. Nothing written to production:
the v2 engine ran against a scratch PostgreSQL with every migration applied.
Raw figures, per batch: `docs/t13-dry-run.json`.

## What was spent, counted

| Phase | Calls = units | Detail |
|---|---|---|
| Census, day-0 mode (39 slices) | **127** | 38 slices read, 1 answered 404; 4,564 videos, 3,900 channels |
| Baselines, 6 complete batches | **972** | 300 channels, 349 videos: `channels.list` 6, `playlistItems` 620, `videos.list` 346 |
| **Recorded total** | **1,099** | every call also tallied as an HTTP response: 1,099, no drift |
| Lost from the record | **unknown, one batch** | see below |

**The baseline costs 3.24 units per channel** (3,240 per 1,000), measured on 300
channels: `playlistItems` 2.07, `videos.list` 1.15, `channels.list` 0.02. The
first version of `02` §4.4 assumed ~1.6. 311 of the 349 videos got a
`standard` baseline and 38 `not_computable`: 89.1%, against the 88.6% measured
on the 220-channel sample in `01` §2.

## A batch lost from the record

The first run was not kill-proof. A device shell call is cut at 180 s, and the
counter was saved to disk only at the end of each batch. One call was cut
while batch 5 was running, between **14:59:09 and about 15:00:05 UTC**: its
requests reached the API but not the record. Complete batches cost 141-173
units. The exact figure is only in the Google Cloud console, and it is:

> console total for 14:54:00-15:04:30 UTC − 1,099

Batch 5 was then re-run in full in the clean window below, so its figures in
the JSON are complete; those channels were read twice.

The script now writes and flushes one line per HTTP attempt **before** sending
it, and caps a call so that no batch straddles the shell limit.

## The check against the console (T-13 closing check)

A clean window: two minutes of silence before and after, one batch, every call
in the kill-proof log.

| Window (UTC) | `channels.list` | `playlistItems.list` | `videos.list` | Total |
|---|---|---|---|---|
| 15:02:39 - 15:03:47 | 1 | 107 | 59 | **167** |

The console must show exactly 167 requests to the YouTube Data API in that
window (17:02:39-17:03:47 Rome time), split as above. Any difference is a bug
in the counter.

## What it implies — an estimate, not a measurement

Day-1 cost = 1,350 (census) + 3.24 x the channels of the day's entries. The
number of entries has never been measured (it comes from day 0 / day 1). At
the 24% turnover assumed in `01` §5, with 23,764 channels, it would be of the
order of 5,700 channels, i.e. ~18,500 units for the baselines alone:
**about twice the 9,500 brake** *(estimate: the turnover is not measured).*

Two facts that bear on the choice `01` §5 foresees for an overrun:

- **`BASELINE_SAMPLES_MAX` does not drive this cost.** Since the format is known
  only after `videos.list` (`02` §4.4, corrected), `videos.list` reads every
  in-window id whatever the cap, and `playlistItems` pages do not depend on it.
  Lowering the cap from 20 to 10 would save ~0 units.
- **The cost is per entry, every day, not only on day 1**: the window is
  anchored to each video's publication, so even a channel already seen needs
  its uploads read again for a new video. Nothing is cached across runs.


---

# T-13 re-run after GATE-2 — channel inventory, 25 September 2026

Same perimeter (IT, US, DE), `QUOTA_MAX_DAILY=2000`, no production write.
Window 18:46:13 - 18:54:14 UTC. Raw figures: `docs/t13-dry-run-2.json`.
Census, then the same 150 channels (188 measured videos) twice: **cold**, the
inventory filled from nothing, and **warm**, on the saved inventory as on
every following day.

## Cost per channel, measured

| | `channels.list` | `playlistItems` | `videos.list` | **per channel** |
|---|---|---|---|---|
| Cold (150 channels) | 0.02 | 2.15 | 1.65 | **3.82** |
| Warm (same 150) | 0.02 | **1.00** | 1.65 | **2.67** |

The forward refresh cut `playlistItems` to exactly one page per channel. The
in-window check (existence, privacy, views of every candidate) stays at what
a cold read costs: that is the price of changing no baseline (`02` §4.4). The
cold figure differs from the 3.24 of the first run because the 150 channels
are a different sample of the 3,900; per-batch cold costs ranged 141-199.

## The closing check: call log against counter

Every HTTP attempt was written and flushed to the call log before it was
sent. For every call that completed, the log delta equals the counter delta,
to the unit:

| Call | Log | Counter |
|---|---|---|
| Census | 127 | 127 |
| Cold batch 0 | 191 | 191 |
| Cold batch 1 | 199 | 199 |
| Cold batch 2 | 183 | 183 |
| Warm batch 0 | 136 | 136 |
| Warm batch 1 | 138 | 138 |
| Warm batch 2 | 126 | 126 |

In total the log holds 1,299 lines and the counter 1,100. The 199 difference is
one call I launched with an 85 s shell limit, shorter than a cold batch: it was
cut while running cold batch 1, and its counter died with the process. The
log kept every one of its calls — 1 `channels`, 111 `playlistItems`, 87
`videos` — the exact split of the same batch re-run in full right after
(1 / 111 / 87). That is the case the log exists for.

## Warm against cold on the real API

| | |
|---|---|
| Measured videos compared | 188 |
| Same sample ids | **188** |
| Same `baseline_rule` | **188** |
| Same baseline to the unit | 102 |
| The other 86 | same samples, baseline moved by the views gained in the minutes between the two reads: median 0.0035%, max 0.09% |

Views are read fresh by rule, so the baseline is expected to move with them;
what must not move is which videos are chosen, and it did not.

## What it implies — an estimate, not a measurement

Steady state: each day's entries mostly belong to channels already in the
inventory, at ~2.67 units per channel; new channels cost ~3.82. The day-1 cost
is still of the order of twice the 9,500 brake at the assumed turnover
*(estimate: the turnover is not measured)*. By the GATE-2 decision the brake
stays: the entries a run cannot reach are `quota_stop` records, counted.
