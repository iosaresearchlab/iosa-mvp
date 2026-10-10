# YouTube Most Popular charts — what we measured

Direct measurements against the official YouTube Data API v3, 22-23
September 2026. These are the figures the methodology protocol rests on.
None of them are estimates unless explicitly labelled as such.

---

## 1. What the official documentation says

`videos.list` with `chart=mostPopular`
(https://developers.google.com/youtube/v3/docs/videos/list):

- `maxResults` accepts 1 to 50, default 5
- the documentation **declares no total limit** on results
- results are per country (`regionCode`) and optionally per category
  (`videoCategoryId`); they are not personalised

Quota (https://developers.google.com/youtube/v3/determine_quota_cost):

- **10,000 units per day** per project, shared across all endpoints
- every read call costs **1 unit**, regardless of the `part` values
  requested and of how many IDs are passed

---

## 2. The general chart is finite: 200, everywhere

Paginated to exhaustion following `nextPageToken`. 20 countries tested (US,
GB, IT, DE, FR, ES, BR, JP, IN, CA, AU, MX, KR, ID, NG, VN, PL, TR, AR, SE):
**`totalResults` = 200 in all 20**, 4 pages of 50. No exceptions.

### But category charts are not subsets

A category chart is **not** a filter over the general chart: it is a
separate, nearly disjoint list. Combining general + all categories reaches
~1,850 videos per country, not 200.

Two consequences:

1. The reachable population per country is **~1,850 videos**.
2. **The general chart is almost devoid of Shorts** (10-24 out of 200, i.e.
   5-12%), while category charts are full of them (~70%). Anyone looking
   only at the general chart never sees the format we measure.

---

## 3. The number: full census of 34 countries

Run 22 September 2026, **544 slices (34 countries × 16 slice types: the
general chart plus 15 categories)**, full pagination. **These are counted,
not estimated.**

Of the 544, **96 return 404** and carry nothing:

| Slice | Countries returning 404 |
|---|---|
| 19 — Travel & Events | 34 of 34 |
| 27 — Education | 34 of 34 |
| 29 — Nonprofits & Activism | 28 of 34 |

**448 slices carry data.** *(Corrected 25/09/2026: the earlier figures
"476 slices (34 × 14)" were never measured — recomputed from the census
file.)*

| | |
|---|---|
| Slices queried | 544 |
| of which carrying data | 448 |
| **Quota calls** | **1,486** |
| **Unique videos** | **29,433** |
| of which Shorts (≤180s) | 20,073 |
| of which long-form | 9,360 |
| Unique channels (all formats) | 23,764 |
| Unique channels with at least one Short | 15,989 |
| Wall-clock time | 112 seconds |

Calls are 1,486 rather than ~1,900 because many slices are short: Music caps
at 30, Nonprofits at 1, People & Blogs ranges from 6 to 89.

**Reading every Most Popular chart in the world costs 1,486 units out of 10,000,
and takes two minutes.** Reading is not the constraint.

The gross sum across slices is 69,726 videos; deduplicated it is 29,433.
**The average overlap factor is 2.4**: each video appears in 2.4 different
charts. Within a single chart, distinct channels almost equal videos (2,247
channels for 2,249 videos in the US): a channel almost never places two
videos in the same chart. All the duplication is across charts.

---

## 4. Two categories out of fifteen do not exist

Tested across 10 countries:

- **19 – Travel & Events: 404 everywhere.** Never charts.
- **27 – Education: 404 everywhere.** Never charts.
- 29 – Nonprofits & Activism: 404 almost everywhere; where it responds it
  returns **1 video**.
- 10 – Music: responds, but `totalResults` = **30**, not 200.
- 22 – People & Blogs: highly variable (6 in IT, 89 in US).

Confirmed by the database: across 27,000 historical records, **Travel &
Events and Education have zero records**. The genuinely present categories
are **13**, one of which (Nonprofits) has 7 records in total.

→ **The public claim of "15 categories" is false.** There are 12 useful
ones. `CATEGORY_MAP` in `vpi_engine.py` contains 15, so roughly one cycle in
seven picks a category that returns 404 and scans nothing.

---

## 5. Age of charting videos

Snapshot of 20,127 Shorts, measured at the moment of reading:

| Age since publication | Shorts | % |
|---|---|---|
| < 1 day | 857 | 4.3% |
| 1-2 days | 2,333 | 11.6% |
| 2-3 days | 2,399 | 11.9% |
| 3-5 days | 4,956 | 24.6% |
| 5-7 days | 4,074 | 20.2% |
| 7-14 days | 4,729 | 23.5% |
| 14-30 days | 675 | 3.4% |
| over 30 days | 104 | 0.5% |

**This table measures age since publication, not age since entry into the
chart.** The two are not the same: a video published five days ago may have
entered the chart five minutes ago, and YouTube exposes no entry timestamp.
The figure therefore says nothing about how long a video persists in the
chart and must not be used to argue that it persists at all.

What it does support: charting Shorts are overwhelmingly between 1 and 14
days old (91.8%), and those published within the last 24 hours are a small
minority (4.3%).

Chart persistence becomes measurable only from our own daily snapshots, as
the number of consecutive days a video is observed. *(Corrected 24/09/2026
after external review: the earlier wording inferred chart persistence from
publication age.)*

---

## 6. Channel turnover

Direct comparison of channel sets between two readings ~16 hours apart:

```
channels, earlier reading:   12,690
channels, later reading:     16,012
in common:                   12,135   (75.8%)
new:                          3,877   (24.2%)
```

Two honest caveats: the gap is ~16 hours, not 24, so real 24-hour turnover
will be higher; and the earlier reading stopped against quota exhaustion, so
it is probably incomplete — which pushes the other way, making 75.8% a
**lower bound** on overlap.

~~**The 24-hour figure has not been measured.**~~ **Measured 27/09/2026**
(`docs/night1-turnover.sql`), night 1 against day 0, a full 24 hours, both
readings complete:

```
videos 26/09:                27,683    in both days: 21,544 (77.8%)
entering videos:              6,139    (22.2%)
  long-form                   2,015    from 1,962 channels
  Shorts                      4,124    from 3,882 channels
entering channels:            5,822    of 21,933
```

At night 1's baseline cost, 3.87 units per channel read cold, the whole
turnover would need ~22,500 units against 9,500: this is why the perimeter
became long-form only (`01` §1). Long-form alone: 1,962 × 3.87 + 1,370 =
8,963.

---

## 7. Baseline computability — sample of 220 channels

| Window | Channels with ≥5 samples | Median samples |
|---|---|---|
| 14-90 days | 75.9% | 20 |
| 10-90 days | 84.1% | 25 |
| **7-90 days** | **88.6%** | 31 |
| 5-90 days | 94.1% | 36 |
| 0-90 days | 99.5% | 50 |

Distribution of samples in the 14-90 day window:

| Videos in window | Channels | % |
|---|---|---|
| 0 | 42 | 19.1% |
| 1-2 | 4 | 1.8% |
| 3-4 | 7 | 3.2% |
| 5-9 | 21 | 9.5% |
| 10-19 | 34 | 15.5% |
| 20-49 | 111 | 50.5% |
| 50+ | 1 | 0.5% |

### Why 19% have zero samples

Not because they publish rarely — **because they publish too much.**
`playlistItems` returns only the 50 most recent uploads. For a channel
posting 5 videos a day, all 50 fall inside 14 days, leaving nothing in the
14-90 window.

Diagnostic on those 42 channels: the oldest of their 50 returned uploads is

| Age of oldest upload | Channels |
|---|---|
| 0-7 days | 19 |
| 7-14 days | 22 |
| 14+ days | 1 |

**41 out of 42 confirmed.** This is an artefact of the API call ceiling, not
data scarcity. The countermeasure is pagination, not a different rule.

For reference: the median channel's 50 most recent uploads span **43 days**,
and only 22% of channels cover 90 days within 50 uploads.

---

## 8. Bias from lowering the maturity floor

Baseline computed under both rules, on channels where both are computable
(n=167):

| Comparison | Median ratio | p10 | p90 |
|---|---|---|---|
| 10-90 vs 14-90 | 1.000 (+0.0%) | 0.85 | 1.20 |
| 7-90 vs 14-90 | 1.000 (+0.0%) | 0.78 | 1.22 |
| 5-90 vs 14-90 | 1.000 (+0.0%) | 0.73 | 1.32 |
| 3-90 vs 14-90 | 1.000 (+0.0%) | 0.73 | 1.33 |

**The central value of the baseline does not move at any floor; per-channel
dispersion widens as the floor drops.** This is a sensitivity analysis, not
a proof that no bias exists: a median ratio of 1.000 is compatible with
systematic differences inside subgroups or in the tails, and no confidence
interval, paired test or subgroup breakdown has been computed.

What it supports is the narrower statement: lowering the floor to 7 days
does not move the central value and buys 12.7 percentage points of coverage.
Whether it moves individual level assignments is a separate question, still
open. *(Corrected 24/09/2026 after external review.)*

---

## 9. Batching — what can and cannot be grouped

Verified directly, 22 September 2026:

| Call | Batch of 50? | Evidence |
|---|---|---|
| `channels.list` | **Yes** | 50 ids → 50 items, 1 unit |
| `playlistItems.list` | **No** | 2 playlists → `HTTP 400 Bad Request` |
| `videos.list` | **Yes** | 50 ids → 50 items, 1 unit |

`playlistItems` is the floor: **1 unit per channel**, not reducible.

~~The uploads playlist ID does not need `channels.list`: it is deterministic,
`UC…` → `UU…`. Verified working.~~ *(27/09/2026: the convention is not
documented, so the id is now read from `channels.list`, in the same call
that already reads the snippet, at no extra cost. It held on all 2,000
channels of night 1: `docs/itemcount-check-2026-09-27.json`.)*

`playlists.list` **is** batchable, 50 ids per unit (`part=contentDetails`
returns `itemCount`). Measured 27/09/2026 on night 1's channels: 40 calls
for 2,000 playlists.

View counts come free with the chart read: adding `statistics` to `part`
returned `viewCount` for all 69,633 videos within the same 1,486 calls, at
no extra quota cost.

---

## 10. What the engine was doing instead

The cycle in production until 22 September 2026 (every 20 minutes) took US +
2 random countries out of 34, 1 random category out of 15, and 2 pages out
of 4.

At most **300 videos per cycle**, drawn at random from 448 slices holding
~70,000 slots (~29,000 unique).

It was not a census: it was a random sample of slices with the depth cut in
half, and no video had a known probability of being observed.

---

## 11. Shape of the chart entries *(measured 03-04/10/2026)*

Why: the duration-only rule (Short = up to 180 s) is not YouTube's rule,
which also needs the shape (`01` §1.1). Script `tests/measure_shape.py`, raw
output `docs/shape-2026-10-03.csv`.

Population: the entries of 03/10/2026 (in that day's snapshot, absent from
02/10's): 4,055 stored as Short by duration, 1,893 as long-form. Sample: the
first 1,000 and the first 100 by `md5(video_id || 's')`. One `videos.list`
call per 50 ids, `part=snippet,contentDetails,player,liveStreamingDetails`,
`maxHeight=1000`: **22 calls, 22 units**. 999 + 100 videos returned (one
removed or made private since).

| | Up to 180 s (stored Short) | Over 180 s (stored long-form) |
|---|---|---|
| returned | 999 | 100 |
| vertical (`embedWidth < embedHeight`) | 960 | 4 |
| square | 14 | 0 |
| **wider than tall** | **25 (2.5%)** | 96 |
| shape not returned | 0 | 0 |
| live broadcasts | 4 (all wider than tall) | **17** |

- The shape comes back in clean ratios: 563×1000 (9:16) 918 times,
  1778×1000 (16:9) 116, 750×1000 (3:4) 31, 1000×1000 14, then a few others
  (800, 1124, 1333 × 1000). No video without it.
- The 25 wide videos up to 180 s run from 15 to 180 s. For YouTube they are
  long-form; the duration-only rule called them Shorts and they were never
  measured. At 2.5% of ~4,000 such entries a day, about **100 long-form
  records a day** were missing (an estimate from this sample: a 95% interval
  on 25/999 is about 1.6-3.7%).
- The 4 vertical videos over 180 s (181 s to 2 hours) are long-form for
  YouTube as well: no change.
- Published before 15/10/2024 among the 999: none.

The chart call itself returns the shape too: one `videos.list
chart=mostPopular` page (IT, category 24) with `part=contentDetails,player,
liveStreamingDetails&maxHeight=1000` returned `embedWidth`/`embedHeight` for
all 50 videos. **1 unit**, measured 04/10/2026. Total spent on this
measurement: 23 units.

### 11.1 What the database already holds

Nothing that gives the shape. `trend_snapshot` and `channel_inventory` keep
the format computed from the duration, not the duration and not the shape;
`posts` keeps neither. Bringing the past under the new rule means reading
again (04/10/2026):

| | Ids | `videos.list` calls |
|---|---|---|
| Short-by-duration ids in `trend_snapshot` (27/09-03/10, 7 days kept) | 42,742 | ~855 |
| Short-by-duration items in `channel_inventory`, all channels | 311,932 | ~6,240 |
| of which near the windows of the 16,011 v2 long-form records (8,308 channels; window approximated per channel as the union of its records' windows) | 139,586 | ~2,790 |

## 12. One video per channel per category chart *(measured 10/10/2026, SOC-2)*

**Raw API responses, 25 non-music slices and 5 music slices**, read on
10/10/2026 00:37-00:38 UTC (`videos.list chart=mostPopular`, `part=snippet`,
every page, no deduplication, no filter; `tools/check_one_per_channel.py`,
output `tools/output/soc2_one_per_channel_2026-10-10.json`; 97 units through
the quota brake, in `quota_ledger` as `measurement`). The 25 non-music slices
cover the 11 non-music categories that return data, 1-3 countries each, the
largest slices of each category on 08/10 among them; all 30 answered.

| | Slices | Items | Channel-slice pairs | Pairs with ≥2 videos | Slices with one |
|---|---|---|---|---|---|
| Non-music | 25 | 4,354 | 4,354 | **0** | 0 |
| Music (category 10) | 5 | 150 | 133 | **12** | 5 of 5 |

In every non-music slice read, every item is a different channel (items =
distinct channels, 53 to 200 per slice). In every music slice, two or three
videos of the same channel appear (US 4 channels, KR 4, IN 2, JP 1, BR 1;
channel and video ids in the output).

**From the snapshot, 30/09-06/10** (before this measurement): among videos
listed in a single category, 302,581 non-music channel × country × category
× day cells, none with two videos of the same channel; music, 595 of 6,010.
Videos listed in more than one category could not be placed in an exact
slice (`countries[]` and `categories[]` are two separate sets): 2,382
non-music cells came out of the cross product, real or artifacts. From the
reading of 10/10 `trend_snapshot.slices` holds the exact pairs (`02` §3.1),
so the same count can be made on every slice of a day, at no quota cost.

What this claims, exactly: on the slices read, a non-music Most Popular
category chart listed no channel twice; music charts do. It is a property of
the charts as YouTube returns them: `census.read_charts` deduplicates by
video id only, reads every page and filters nothing by channel.

---

*All measurements run with the project's API key from Migert's machine.
Scripts and raw outputs retained.*
