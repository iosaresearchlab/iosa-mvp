# Day-1 audit — 2026-09-27

Computed by `tests/audit_day1.py 2026-09-27` from production (read-only). The reference day is 2026-09-26. Perimeter: long-form only (`01` §1). This is the first day of the published
series (`01` §1: the index starts on 2026-09-27); nights 0 and 1 are
reference states only.

**Reading the figures (no figure below is estimated):**
- The budget held with 1,389 units of margin at 9.8% of long-form entering
  channels already in the inventory (186 of 1,898): 3.55 units per channel,
  against 3.87 on night 1 with both formats.
- `exits` 1,160 are night-1 records (reference-only vintage) that left the
  charts: the first exits the index has observed.
- `not_computable` 15.1%: the real coverage on long-form is 84.9%, against
  88.6% measured on the v1 sample (`01` §2), which mixed formats.
- The VPI bands are as far apart as on v1 data (median 188.5 in 100-1k,
  0.66 in >=100k): no figure is ever pooled across bands (`01` §4.2). The
  scale is the owner's (`01` §4.3) and this audit changes nothing in it.
- The retention of `trend_snapshot` is not implemented; at 221 bytes per row
  and ~27,600 rows a day it grows ~6 MB a day. Waiting for Migert.

## Run

| | |
|---|---|
| `outcome` | ok |
| `baselines_complete` | true |
| `quota_total` | 8,111 |
| `quota_charts` | 1,369 |
| `quota_channels` | 38 |
| `quota_playlists` | 0 |
| `quota_playlist` | 3,660 |
| `quota_videos` | 3,044 |
| `slices_ok` | 412 |
| `slices_404` | 30 |
| `slices_error` | 0 |
| `videos_seen` | 27,618 |
| `channels_seen` | 21,987 |
| `entries` | 1,950 |
| `updated` | 6,928 |
| `exits` | 1,160 |
| `entering_channels` | 5,393 |
| `entering_channels_in_inventory` | 352 |
| `entering_long_channels` | 1,898 |
| `entering_long_in_inventory` | 186 |
| `started_at` | 2026-09-27T23:59:01.602711+00:00 |
| `finished_at` | 2026-09-28T00:37:56.93343+00:00 |

Notes: slice order seed 2158512876; countries 34, categories 13; quota limit 9500; baselines: 6742 units for 1898 channels = 3.55 per channel (channels 38, itemCount 0, uploads 3660, videos 3044); skipped by itemCount 0; videos checked 150997, other-format not checked 1180; entering channels in the inventory: 352/5393 all formats, 186/1898 long-form

## Coverage

| baseline_rule | records | share |
|---|---|---|
| `not_computable` | 295 | 15.1% |
| `standard` | 1,655 | 84.9% |
| total | 1,950 | |

Short records: 0; entries not certain: 0.

## 24-hour turnover

| | |
|---|---|
| videos in the charts | 27,618 |
| of which not in the reference day | 5,644 (20.4%) |
| long-form among them | 1,950 |
| channels in the charts | 21,987 |
| channels not in the reference day | 2,361 (10.7%) |
| channels of the entries | 5,393 |

## Age at first observation (days), records of the day

| n | min | p10 | p25 | median | p75 | p90 | max |
|---|---|---|---|---|---|---|---|
| 1,950 | 0 | 0.0 | 0.0 | 0.0 | 1.0 | 1.0 | 34 |

## VPI by baseline band and format (never pooled)

| format | band | n | p25 | median | p75 | p90 |
|---|---|---|---|---|---|---|
| LONG | <100 | 1 | 718.65 | 718.65 | 718.65 | 718.65 |
| LONG | 100-1k | 11 | 131.61 | 188.52 | 758.57 | 849.64 |
| LONG | 1k-10k | 84 | 10.25 | 24.36 | 93.95 | 231.14 |
| LONG | 10k-100k | 678 | 0.84 | 1.47 | 3.22 | 7.55 |
| LONG | >=100k | 881 | 0.41 | 0.66 | 1.18 | 2.21 |

## Storage

| table | rows | bytes | bytes per row |
|---|---|---|---|
| `posts` | 8,088 | 18,448,384 | 2,281 |
| `post_daily` | 13,066 | 2,392,064 | 183 |
| `trend_snapshot` | 82,894 | 18,317,312 | 221 |
| `channel_inventory` | 3,712 | 10,117,120 | 2,726 |
| `ingest_run` | 3 | 49,152 | 16,384 |
| `posts_v1` | 28,917 | 17,883,136 | 618 |
