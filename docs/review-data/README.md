# Data package for external reviewers

Supporting data for `../05-external-review-dossier.md`. Every claim in
section 5 of the dossier can be recomputed from these files.

Collected 22-23 September 2026 from the official YouTube Data API v3.

---

## `chart-census-by-slice.csv`

One row per chart slice queried. 544 rows: 34 countries × 16 slice types
(the general chart plus 15 category IDs), of which 448 responded and 96
returned HTTP 404.

| Column | Meaning |
|---|---|
| `country` | ISO country code passed as `regionCode` |
| `category` | Category name |
| `category_id` | YouTube `videoCategoryId` (empty = general chart) |
| `pages` | Pages of 50 fetched before `nextPageToken` ran out |
| `total_results` | `pageInfo.totalResults` as reported by the API |
| `videos` | Distinct videos returned by this slice |
| `distinct_channels` | Distinct channels among those videos |
| `shorts` | Of those videos, how many are ≤180s |
| `short_channels` | Distinct channels among the Shorts |
| `error` | Empty, or the HTTP status returned |

**Supports:** the 200-per-chart ceiling; the 448/476 slice count; the 1,486
call count (= sum of `pages` plus one call per 404); the claim that Travel &
Events and Education never chart; the near-equality of `videos` and
`distinct_channels` within a slice.

**Contains no creator identifiers.** Counts only.

---

## `channel-sample-upload-ages.csv`

A random sample of 220 channels that had at least one Short charting on
22 September 2026. For each, the age of every upload returned by
`playlistItems` (the 50 most recent).

| Column | Meaning |
|---|---|
| `channel_key` | First 12 hex characters of the SHA-256 of the channel ID |
| `upload_rank` | 1 = oldest of the returned uploads |
| `age_days` | Days between publication and the moment of measurement |

Channel IDs are hashed. The hash is stable within the file, so per-channel
analysis works, but the channels are not identifiable from it.

**Supports:** the baseline computability table (75.9% / 84.1% / 88.6% /
94.1% at the four windows); the finding that 19% of channels have zero
samples in the 14-90 day window because all 50 of their uploads fall inside
14 days.

**Does not support** the baseline-shift table (median ratio 1.000), which
needs view counts. Those are available on request — see below.

---

## Available on request

- **The full census of 22/09/2026**: 29,433 unique videos with video ID,
  channel ID, format, publication date, view count, and the list of charts
  each appeared in. Contains real video and channel identifiers — all of it
  public data from a public API, but we share it on request rather than
  publishing it.
- **The 28,917 historical records** collected under the v1 method. Useful
  only for studying the defects described in section 7 of the dossier; not
  valid data.
- **Source code** of the ingestion engine and the VPI computation.

Contact: iosa.research.lab@gmail.com

---

## How to reproduce

Every figure came from paginating `videos.list` with `chart=mostPopular`
over the 34 countries and the category IDs, and from `playlistItems.list` on
each channel's uploads playlist (`UC…` → `UU…`). A full pass costs 1,486
quota units and takes about two minutes with 12 threads.
