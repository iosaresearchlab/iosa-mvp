# Technical Specification — migration to the v2 index

**Status: approved 23 September 2026. No code written yet.**

Implements `01-methodology-protocol.md`. Population figures from
`03-Most Popular-population-measurements.md`.

Terminology: **day 0** = first reading, snapshot only. **day 1** = first
reading with a comparison, first real records.

---

## 0. Decisions taken

| # | Decision |
|---|---|
| Countries and categories | Start with **all 34 countries** and every category that responds. Reduce countries **only** if the day 0 / day 1 audit overruns the quota |
| Schedule | **23:59 UTC**, fixed year-round |
| `is_real_youtube_short()` | **Removed.** The only non-API call in the pipeline; classification is by duration and, from 04/10/2026, shape (§4.9) |
| `MIN_BASELINE_VIEWS` | **No longer an ingestion filter.** Everything is measured; it survives as a declared criterion of the showcase only |
| "- Topic" channels | **Stay in the index**, flagged `auto_generated_channel`, excluded only from outreach |
| Baseline | **7-90 day** window, ≥5 samples, ≤20 spread evenly, **one rule**, with pagination up to 3 pages |
| `BASELINE_SAMPLES_MAX` | **20** |
| Frozen baseline | **Yes**, at entry. Sample IDs are stored so the choice can be verified in three weeks |
| **Printify** | **Do not touch.** The branch is suspended but functional: `printify_product_id`, `printify_service.py`, `trophy_pipeline.py` and the related endpoints stay intact |
| Database | Optimise: drop dead and derivable columns, aggregate series on close |

---

## 1. How it works today

### 1.1 Ingestion

`backend/vpi_engine.py`, 796 lines.
`fetch_and_ingest_real_youtube_content()`:

```python
selected_countries = ['US'] + random.sample(other_countries, k=2)
selected_category_ids = random.sample(list(CATEGORY_MAP.keys()), k=1)
```

US + 2 random countries out of 34, 1 random category out of 15, 2 pages out
of 4. At most 300 videos out of ~63,000 slots.

Filters in sequence, each with a counter already in place:

| Filter | Effect | Fate |
|---|---|---|
| `formato_da_durata() is None` | live streams, premieres | stays |
| `age_days > CAMPAIGN_DAYS` (15) | old videos | **out** |
| `_filter_already_ingested()` | duplicates | stays, logic changes |
| `is_real_youtube_short()` | HTTP HEAD | **out** |
| `not channel_handle` | "- Topic" channels | **out** (they get flagged) |
| `baseline < MIN_BASELINE_VIEWS` | small denominator | **out of ingestion** |
| `vpi_ratio <= MIN_VPI_FOR_INGESTION` | censoring from below | **out** |

`MAX_SUBSCRIBERS = 1_500_000` and `MIN_SUBSCRIBERS = 1_000` are defined but
**used in no comparison**. Verified. To be removed.

### 1.2 Current baseline cost

`get_channel_video_samples()`: `channels.list` (1 id) + `playlistItems` +
`videos.list` (50 ids) = **3 units per channel**. File-backed cache
(`TTLCache("channel_baselines")`), which on Render is lost at every deploy
because the filesystem is ephemeral.

### 1.3 Scheduling

- `render.yaml`: one web service, `IOSA_ENGINE_MODE=off`
- `cron.job` id 1 on Supabase: `*/20 * * * *` → `chiedi_un_giro_di_ingestione()`
- that function does `net.http_post` to `/api/ingest/run` with the Vault
  token (`timeout_milliseconds: 90000`, to let Render wake up)
- `main.py` validates the token and runs `esegui_un_ciclo()` in the background

### 1.4 Database

`posts`, 28,917 rows, **21 MB → 759 bytes per row**.

```
id uuid pk | external_post_id | platform | format (SHORT|LONG, default SHORT)
channel_id | channel_handle | author_handle | author_name | subscribers
country text | category varchar | content_text | post_url
engagement_score | baseline_score | vpi_ratio | vpi_level | vpi_level_name
vpi_color | claim_token | status (ACTIVE|EXPIRED|INACTIVE) | comment_sent
created_at (= the video's publishedAt) | detected_at | window_id
printify_product_id
```

Other tables: `claims`, `claim_visite`, `claim_eventi`, `outreach`,
`outreach_esiti` (view), `waitlist`, `evaluation_windows` (empty, unused).

Composition: 28,914 YouTube (27,615 SHORT, 885 LONG), **1 TikTok,
1 Instagram**.

### 1.5 Frontend

Next.js, `frontend/src`, 4,029 lines.

- `app/page.tsx` (942) — reads Supabase from the browser, `status='ACTIVE'`,
  `vpi_ratio >= 1.4`, realtime on `postgres_changes`
- `app/leaderboard/page.tsx` (578) — `/api/analytics/top10`, timeframe
  24h / 7d / 15d, filtered on `created_at`
- `app/insights/page.tsx` (468) — `/api/analytics/insights` and `/keywords`
- `app/claim/[token]/page.tsx` (525) — 15-day countdown computed in the
  browser from `createdAt`
- `lib/supabase-server.ts` — segment pages, `MIN_VPI_DISPLAY = 1.4`
- `lib/vpi-scale.ts` — copy of the scale, checked by `tests/audit_scala.py`
- `lib/segments.ts` — 34 countries and **13 categories**, already correct
- `components/MetodologiaModal.tsx` — the public methodology text

---

## 2. What it becomes

```
23:59 UTC, once a day
   |
   +- 1. CENSUS       414 category charts (NOT the general chart)
   |                  part=snippet,contentDetails,statistics
   |                  -> ~28,000 videos, views included, 1,350 units
   +- 2. SNAPSHOT     writes trend_snapshot. Zero cost
   +- 3. ENTRIES      today \ yesterday \ ever_seen -> baseline -> insert
   +- 4. UPDATE       already tracked and still charting -> series. Zero cost
   +- 5. EXITS        absent today -> left_on. Zero cost
   +- 6. RUN REPORT   ingest_run: quota spent, counts, discards
```

---

## 3. Database

### 3.1 New table `trend_snapshot` — a working buffer, kept 7 days

**A working buffer: it is the reference point for "absent yesterday".** The
research data lives in the series and the records, which are never deleted.
Snapshot rows are working data, day 0 included *(owner decision 28/09/2026:
once the first day has been analysed and the system is in steady state, day
0 is a day like any other; the `permanent` column, which existed only to
exempt it, is dropped)*.

```sql
create table public.trend_snapshot (
  day           date not null,
  video_id      text not null,
  channel_id    text not null,
  format        text not null check (format in ('SHORT','LONG')),
  published_at  timestamptz,
  views         numeric,
  countries     text[] not null,
  categories    text[] not null,
  primary key (day, video_id)
);
create index trend_snapshot_day_idx on public.trend_snapshot (day);
alter table public.trend_snapshot enable row level security;
-- no policy: only the service role writes here
```

**Retention: 7 days, no exception** (implemented 28/09/2026,
`backend/retention.py`, migration `v2_ret1_snapshot_retention`). The window
is the reading day and the six before it; every older day is removed, one
day at a time, in this order and never another:

1. export the day's rows, every column, one `to_jsonb(row)::text` line each,
   in `video_id` order (`snapshot_export`);
2. write them gzip-compressed to Supabase Storage, private bucket
   `archivio`, one file per day: `trend_snapshot/<day>.jsonl.gz`;
3. read the stored file back and check it line for line against the export;
4. only then delete, through `purge_snapshot_day(day, keep_from, rows, md5)`,
   which deletes only when the row count and the md5 of the file read back
   equal those of the rows in the table, and refuses a day inside the window
   (against the caller's window and the database clock) and the reference —
   the last complete reading — whatever its age.

A failure at any step deletes nothing for that day and stops before every
later day; the run notes it (`RETENTION FAILED`) and keeps its outcome. The
purge runs only after a complete census, so the day it runs on is the next
reference. Destination: Storage, not the Render filesystem (the free tier
has no persistent disk) and not git. Storage on the free tier: **1 GB, 50 MB
per file**; measured 1,227,592 bytes for the 27,593 rows of 2026-09-25, so
**~1.2 MB a day, ~450 MB a year**; with the plaques and the `posts_v1`
archive (§3.6, 5.8 MB) the 1 GB lasts about two years. The nightly check
fails above 800 MB. The functions are executable by the
service role only; nothing public reads `trend_snapshot` or its archive.
What open records need stays in `posts`, `post_daily` and `ingest_run`.

The table holds the last 7 days; every earlier day is in the archive, and
each of its lines restores one row with
`insert into trend_snapshot select * from jsonb_populate_record(null::trend_snapshot, <line>::jsonb)`.

### 3.1.1 No day-0 exclusion list *(removed 25/09/2026, GATE-1)*

A `day0_pending` table was added at T-06 and dropped at GATE-1. Once the
reference for every day became the last complete reading (§3.5), it excluded
nothing: a day-0 video still charting is in the reference snapshot and is
excluded by the ordinary test; one that leaves and returns is an entry we
genuinely observed.

**Day 0 must still be complete.** An incomplete day 0 is not a reference, so
it cannot produce false entries: day 1 would simply find no reference and
record nothing, and the next reading is day 0 again (`vpi_engine`,
`has_complete_reading_before`). Its rows leave the table after 7 days like
every other day's.

### 3.1.2 New table `channel_inventory` *(GATE-2, 25/09/2026)*

The immutable part of each channel's uploads, kept across runs (§4.4).

```sql
create table public.channel_inventory (
  channel_id      text primary key,
  items           jsonb not null,   -- {video_id: [published_epoch_s, format]}
  covered_back_to timestamptz,      -- oldest upload read contiguously from the newest
  capped          boolean not null default false,  -- 150 most recent held
  ended           boolean not null default false,  -- the playlist was read to its end
  refreshed_on    date
);
alter table public.channel_inventory enable row level security;
-- no policy: only the service role reads and writes here
```

`format` is `SHORT`, `LONG`, `NONE` (no usable duration, or shape not
returned) or null (not yet known; from 04/10/2026 also every item that was
`SHORT` under the duration-only rule, §4.9). At most the 150 most recent uploads are kept per channel.
*Estimate*: a few tens of MB at 24,000 channels (TOAST-compressed jsonb, ~80
items per channel); to be measured once populated.

### 3.2 New columns on `posts`

```sql
alter table public.posts
  add column entered_on           date,
  add column left_on              date,
  add column days_charting        int,
  add column countries            text[],
  add column categories           text[],
  add column baseline_computed_at timestamptz,
  add column baseline_samples     int,
  add column baseline_rule        text,   -- standard | not_computable
  add column baseline_span_days   numeric,
  add column baseline_video_ids   text[], -- to verify the freezing choice
  add column auto_generated_channel boolean default false,
  add column scale_version        text default 'v1',
  add column method_version       text default 'v2',
  add column gap_days             int default 0,
  add column entry_certain        boolean default true,
  add column age_at_first_obs_days int,   -- entered_on - published_at
  add column vpi_max              numeric,
  add column vpi_max_on           date,
  add column views_max            numeric,
  add column views_final          numeric;

alter table public.posts alter column vpi_ratio drop not null;
alter table public.posts alter column vpi_level drop not null;

create index posts_entered_idx    on public.posts (entered_on desc);
create index posts_countries_idx  on public.posts using gin (countries);
create index posts_categories_idx on public.posts using gin (categories);
create index posts_method_idx     on public.posts (method_version);
```

`vpi_ratio`, `vpi_level` and `baseline_score` become nullable: a record with
`baseline_rule = not_computable` exists without a baseline and without a VPI,
and is never discarded (`01` §2).

**The two states cannot drift apart.** A constraint makes a third case
impossible in the database, rather than tested for afterwards:

```sql
alter table public.posts alter column baseline_score drop not null;
alter table public.posts add constraint posts_baseline_state check (
  coalesce(method_version = 'v1', false)
  or coalesce(baseline_rule = 'standard'
              and baseline_score is not null and vpi_ratio is not null
              and vpi_level is not null and vpi_level_name is not null
              and vpi_color is not null, false)
  or coalesce(baseline_rule in ('not_computable', 'quota_stop')
              and baseline_score is null and vpi_ratio is null
              and vpi_level is null and vpi_level_name is null
              and vpi_color is null, false)
);
```

*(`quota_stop` added at GATE-2: entries a run could not reach because of the
brake, `01` §2.)* *(Extended at GATE-1, 25/09/2026: the level, its name and its colour follow
the VPI, so a record cannot carry a level name without a level, nor a level
without a VPI. `vpi_level_name`, `vpi_color` and `author_handle` become
nullable at the same time: a `not_computable` record has no level, and a
channel without a handle stays in the index, `01` §7.)*

The `coalesce(..., false)` is not decoration: a `CHECK` that evaluates to
NULL passes, so without it a v2 row with `baseline_rule` null would satisfy
the constraint. Measured on 25/09: all 28,917 v1 rows evaluate to NULL under
the bare form, which is why the v1 archive is exempted explicitly instead.

**`method_version` defaults to `'v1'`; the v2 pipeline writes `'v2'`
explicitly.** Any legacy writer then produces rows that every public query
excludes by construction, instead of rows that silently claim to be current.
*(Changed 25/09/2026: the default was `'v2'` at T-05.)*

`country` and `category` remain as the **primary value** (the first chart
the video appeared in) so existing queries and pages keep working;
`countries` and `categories` are the complete truth. Segment pages move to
`.contains('countries', [code])`.

`status` changes meaning: **`ACTIVE`** = currently charting, **`CLOSED`** =
gone. `EXPIRED` leaves the measurement and survives only as a claim-token
state.

**Removal requests** *(OPTOUT-1, owner decision 01/10/2026)*: `hidden boolean
not null default false` and `hidden_on date`. A removal request sets
`hidden = true`: the record disappears from every public page and from the
public API, and is never deleted. The engine keeps measuring it. RLS is the
guarantee, because the site reads with the public key: the select policy on
`posts` is `not hidden`, and the one on `post_daily` requires its record not
hidden. The backend's public reads (`/api/posts`, the day-1 analytics, the
claim lookup behind the plaque, the window and the order) filter
`hidden = false` too. A claim link of a hidden record resolves to nothing.
Migration `20261001010027_v2_optout1_hidden`, `tests/test_optout.py`.

### 3.3 The daily series

```sql
create table public.post_daily (
  post_id   uuid not null references public.posts(id) on delete cascade,
  day       date not null,
  day_index int not null,          -- 1 = first day observed in the chart
  views     numeric not null,
  vpi_ratio numeric,
  vpi_level int,
  primary key (post_id, day)
);
create index post_daily_day_idx   on public.post_daily (day);
create index post_daily_index_idx on public.post_daily (day_index, vpi_ratio desc);
alter table public.post_daily enable row level security;
create policy "public read" on public.post_daily for select using (true);
```

`day_index` is the comparison key: **every cross-video comparison and
ranking runs at `day_index = 1`** (see `01-methodology-protocol.md`
§4.2). It is redundant with `day - entered_on`, but storing it turns the
main query of the whole site into an index scan. Four bytes well spent.

`countries` and `categories` are **not** repeated here: they change little
day to day and already live on the record. That is ~60 bytes per row saved
across 29,000 rows a day.

### 3.4 New table `ingest_run`

The report for each run. **Without it the day 0 / day 1 audit cannot be
computed.**

```sql
create table public.ingest_run (
  id                uuid primary key default gen_random_uuid(),
  day               date not null unique,
  started_at        timestamptz not null,
  finished_at       timestamptz,
  outcome           text,           -- ok | partial | failed
  quota_charts      int,
  quota_channels    int,
  quota_playlist    int,
  quota_videos      int,
  quota_total       int,
  slices_ok         int,
  slices_404        int,
  slices_error      int,
  videos_seen       int,
  channels_seen     int,
  entries           int,
  new_channels      int,
  updated           int,
  exits             int,
  discards          jsonb,
  notes             text
);
-- 27/09/2026 (v2_perimeter_long_census_state):
--   baselines_complete boolean    -- false when the brake fired or reads failed
--   quota_playlists    int        -- playlists.list (itemCount), 0 while off
--   entering_channels, entering_channels_in_inventory,
--   entering_long_channels, entering_long_in_inventory  int
--     the share of today's turnover already in channel_inventory: no role in
--     the budget; it tells when Shorts can come back.
-- notes carry the units per channel of the baselines, by endpoint.
```

### 3.5 Function for entries

29,000 ids cannot be passed to an `in_()`: the comparison happens in the
database.

```sql
create or replace function public.entries_of_day(d date)
returns table (video_id text, gap_days int, entry_certain boolean)
language sql stable
set search_path = public
as $$
  with previous as (
    select max(r.day) as pd from ingest_run r
    where r.day < d and r.outcome = 'ok'
  )
  select s.video_id,
         case when previous.pd = d - 1 then 0 else d - previous.pd end,
         previous.pd = d - 1
  from trend_snapshot s, previous
  where s.day = d
    and previous.pd is not null
    and not exists (select 1 from trend_snapshot p
                    where p.day = previous.pd and p.video_id = s.video_id)
    and not exists (select 1 from posts po
                    where po.external_post_id = s.video_id);
$$;
```

Three exclusions, each for one reason: present in the reference snapshot
(already charting), already a record (re-entry: no new record, `01` §4 step
6), and **no reference at all**
(day 0 is snapshot only: with nothing to compare against, no entry is
observable). The function returns the gap with each ID, so the writer sets
`entry_certain` and `gap_days` from the database's answer rather than
recomputing them.

The reference is **the most recent day whose run completed**
(`ingest_run.outcome = 'ok'`), not "yesterday" by definition and not the most
recent snapshot: a partial reading observes presence but not absence, so it
cannot be the reference (`01` §4). If yesterday was partial, the reference is
further back, `gap_days > 1`, and the record is correctly marked uncertain.
The completion flag lives only in `ingest_run`; it is not copied onto
`trend_snapshot`.

Entries are still detected **during** a partial run when the reference is
yesterday: presence in a chart we read is observed, and discarding it would
lose real data.

*Limit, declared:* the reference snapshot is kept by the 7-day retention, so
more than 7 consecutive incomplete runs would leave no reference to compare
against. That is a stop condition for the operator, not a case the function
papers over.

That keeps the run from treating every video as new, but it does not restore
the missing information. When `previous.d < d - 1` the entry date is
**unknown**: the video may have entered during the gap. Every record created
in such a run is written with `entry_certain = false` and `gap_days = d -
previous.d` (0 when there is no gap), and every statistic that depends on the entry date filters
`entry_certain = true`. A gap must never manufacture an entry event.

### 3.6 Archiving the v1 records

```sql
update public.posts set method_version = 'v1' where entered_on is null;
```

They keep serving claim tokens already sent. Every public
v2 query filters `method_version = 'v2'`.

**Correction, 25/09/2026 (decision by Migert).** Flagging in place was not
enough: from day 1 the v2 series writes into the same table the site reads,
so values computed under two rules would sit on one scale. The v1 rows
**move out of `posts`** into `posts_v1` (migration `v2_archive_v1_records`):
nothing deleted, nothing recomputed, count and md5 checked inside the
migration before the delete.

- `posts_v1`: same columns as `posts` plus `archived_at`; `id` is the
  original post id. RLS on, no privilege for `anon`/`authenticated`: no page
  and no statistic reads it.
- `posts_v1_links`: the `outreach`, `claim_visite` and `claim_eventi` rows
  that pointed at a v1 post, with that post id. Their `post_id` is set null
  by the foreign key (`ON DELETE SET NULL`); the link stays reconstructable.
  *(APP-12, 01/10/2026: that same foreign key then refused every new visit
  to a v1 claim page, whose `post_id` is a `posts_v1` id: `claim_visite` has
  no row after 24/09. `claim_visite.post_id` and `claim_eventi.post_id` now
  name the record in `posts` or `posts_v1` and carry no foreign key; the 5
  nulled visits got their id back from their token. Migration
  `20261001010218_v2_app12_claim_visits`.)*
- `claim_record_v1(token)`: the one archived record with that token, for the
  claim page and the checkout, so a v1 claim token still resolves (`08`
  T-20). Lookup by token only: the archive cannot be listed.

**Reduced, 28/09/2026 (decision by Migert).** The v1 claim pages must keep
working — 226 contacts in `outreach` hold those tokens — and nothing else
reads the archive. Every column of all 28,917 rows, and `posts_v1_links`,
were exported first to Storage (private bucket `archivio`,
`posts_v1/posts_v1.jsonl.gz` and `posts_v1/posts_v1_links.jsonl.gz`, one
`to_jsonb(row)::text` line per row), read back and checked against the
table's md5; then `posts_v1` was rebuilt with the 16 columns the code reads
from a v1 record (`tests/test_v1_slim.py` derives the list from
`backend/main.py` and the claim page and fails if it changes): `id`,
`claim_token`, `platform`, `author_handle`, `content_text`,
`engagement_score`, `baseline_score`, `vpi_ratio`, `vpi_level_name`,
`vpi_max`, `views_max`, `days_charting`, `created_at`, `detected_at`,
`entered_on`, `method_version`. Migration `v2_v1slim_reduce`; `posts_v1`
17.9 → 8.9 MB. `posts_v1_links` and `outreach` unchanged. Access unchanged:
lookup by token only, the table and the bucket cannot be listed with the
public key (`tests/check_v1_claim.py`).

### 3.7 Storage optimisation

*(28/09/2026: not implemented, and not a pending task. Its estimate is
superseded by the measured figures in §3.8, and the choice it anticipated —
how to live within the free tier — is the owner's, §3.8.)*

Measured: **759 bytes per row**. At the projected growth (~5,000 new records
a day plus the series) that is **~8 MB a day, 240 a month**. The free tier
gives 500 MB, 21 already used: **it fills up in two months.**

**Columns to remove from `posts`:**

| Column | Why |
|---|---|
| `window_id` | `evaluation_windows` is empty and referenced by no code |
| `comment_sent` | YouTube comment outreach has been off since September |
| `vpi_color` | derivable from `vpi_level`, already in `vpi-scale.ts` |
| `vpi_level_name` | same |
| `post_url` | reconstructible from `external_post_id` |

**`printify_product_id` must NOT be touched.**

**Series aggregation**: when a post has been closed for 30 days, its
`post_daily` rows are summarised onto `posts` (`vpi_max`, `vpi_max_on`,
`views_max`, `views_final`, `days_charting`) and deleted. The full series
remains for the current window, which is the one that matters.

**`evaluation_windows`**: drop after verifying no query touches it.

Estimated effect: row from 759 to ~420 bytes, growth from 8 to ~4.5 MB/day,
**from 240 to ~135 MB a month**. The free tier then lasts beyond a year.

### 3.8 Known operating constraint: database size *(measured 28/09/2026)*

The Supabase free tier holds **500 MB**. Records are never deleted, by
design (`01` §3): `posts` grows with every day of the index and nothing in
this specification makes room for it. The snapshot retention (§3.1) caps
`trend_snapshot`; it does not touch this.

Measured with `docs/db-growth.sql` on the reading of 2026-09-27, the first
day of the series (bytes per row = total relation size, heap + toast +
indexes, over rows):

| table | bytes per row | rows per day | MiB per day |
|---|---|---|---|
| `posts` | 2,281 | 1,950 records | 4.24 |
| `post_daily` | 183 | 6,928 (one per active record) | 1.21 |
| `channel_inventory` | 2,726 | 1,712 channels not already in it | 4.45 |
| `trend_snapshot` | 221 | 27,618 | 5.82, until the table holds 7 days |

- `posts` alone: **~1.5 GiB a year** (1.6 GB), never reclaimable.
- Database after the 28/09 operations: **68.7 MiB** (72,084,627 bytes;
  77.2 MiB before, 8.5 MiB returned by the `posts_v1` reduction, §3.6).
- Growth: **15.7 MiB a day** until `trend_snapshot` holds 7 days (4 more
  readings), then **9.9 MiB a day**.
- Runway from 28/09/2026: the nightly check's 400 MiB alarm in **~31 days**,
  the 500 MB limit in **~41 days** (about six weeks, early November); `posts`
  alone would fill it in ~102 days. The free tier holds roughly two months of
  the index at this rate — measured, between six weeks with every table and
  three months if `posts` were the only one growing.
- These are one day's rates. Two of them move: `post_daily` grows with the
  number of active records (+790 on 27/09: 1,950 entries, 1,160 exits), and
  the new rows of `channel_inventory` should fall as the share of entering
  channels already in it rises (186 of 1,898 on 27/09). Re-measure with the
  script, not by extrapolation.

**Whose decision.** The choice between a larger tier and a smaller scope is
the owner's, and he takes it as the limit approaches. Nothing is engineered
around it in the meantime, and **records are never deleted to make room**.
The nightly check (`tests/check_run.sql`) carries the database size and fails
above 400 MiB, so the approach of the limit is reported, not discovered.

---

## 4. Backend

### 4.1 `backend/vpi_core.py`

| What | Action |
|---|---|
| `MIN_VPI_FOR_INGESTION` | **delete**, with every use |
| `CAMPAIGN_DAYS = 15` | rename `CLAIM_DAYS`, move to the outreach constants |
| `BASELINE_MIN_AGE_DAYS` | **14 → 7** |
| `BASELINE_MAX_AGE_DAYS` | 90, unchanged |
| `MIN_BASELINE_SAMPLES` | 5, unchanged |
| `BASELINE_SAMPLES_MAX` | **new**, 20 |
| `BASELINE_PAGES_MAX` | **new**, 3 |
| `MIN_BASELINE_VIEWS` | stays as a constant, but **for the showcase only**: no longer filters ingestion |
| `VPI_SCALE` | unchanged; add `SCALE_VERSION = "v1"` |
| `baseline_from_samples()` | rewrite: one rule, even sampling when >20 fall in the window, also returns rule/span/ids. `giorni_indietro` survives only for v1 records |

### 4.2 `backend/vpi_engine.py`

*27/09/2026 — perimeter.* `MEASURED_FORMATS = ("LONG",)`: only a long-form
entry is measured and written; a Short entry is counted in
`discards.out_of_perimeter_short` and nothing else. The census, the snapshot
and the daily views of existing records (night 1's Shorts included) are
unchanged. An entry whose reads fail after the retries is written as
`read_failed` (no baseline, no VPI) rather than left out: the day stays the
reference, so an entry not written would never be seen entering again.

`CATEGORY_MAP`: remove `'19'` and `'27'`. 13 entries remain (`'29'` responds
in 6 countries with 1 video: keep it, it costs 6 calls).

**To delete**: `random.sample(...)`, the 2-page limit,
`is_real_youtube_short()` and its cache, `mark_expired_campaign_data()`,
`dispatch_cautious_outreach()`, `MAX_SUBSCRIBERS`, `MIN_SUBSCRIBERS`,
`INGEST_INTERVAL_MINUTES`.

**To move to `archive/backend/`**: the entire TikTok branch
(`get_tiktok_access_token`, `get_tiktok_user_baseline`,
`fetch_and_ingest_tiktok_content`) — 1 record in the project's entire
history, and the Research API exposes no Most Popular chart, so entry into
Most Popular is not observable there. Same for `weekly_digest.py` (unwired stub,
names real creators, comment-based CTA).

### 4.3 New module `backend/census.py`

```python
def read_charts(countries, categories) -> tuple[dict, dict]:
    """Full census of the CATEGORY charts. Returns (videos, report).

    The general chart (no videoCategoryId) is NOT read: it is a different
    population — curated, not ordered by views, 58.8% of its videos absent
    from every category chart. See 01-methodology-protocol.md section 5.

    videos: {video_id: {channel_id, format, published_at, views,
                        countries:set, categories:set}}
    One call per page, part=snippet,contentDetails,statistics
    (+ player,liveStreamingDetails with maxHeight=1000 from 04/10/2026,
    section 4.9), maxResults=50, following nextPageToken to exhaustion.
    On 403 everything stops and outcome='partial'.
    """

def save_snapshot(day, videos) -> int
def entries(day) -> list[dict]     # calls entries_of_day()
def close_exits(day, run_complete: bool) -> int
```

**`close_exits()` never runs after a partial run.** Absence is not observable
in an unfinished read: the videos stay open and that day is simply not an
observation for them. `run_complete` is false as soon as the census stopped
early (403) ~~or the quota brake fired~~ *(27/09/2026: the census alone)*; the
function then returns 0 without touching the database.

Concurrency 8-12 threads. Measured: 1,486 calls in **112 seconds** for all
544 slices; the 414 category slices alone cost **1,350**.

`CATEGORIES` excludes 19 (Travel & Events) and 27 (Education), which return
404 in all 34 countries, so `CATEGORY_MAP` drops from 15 entries to 13 and no
cycle is wasted on a 404.

### 4.4 New module `backend/baseline.py`

```python
def baselines_for_videos(measured) -> tuple[dict, dict]
```

**Per video, not per channel.** The window is anchored to each measured
video's own `publishedAt` (`01` §2), so two new videos of the same channel
published on different days have different windows and possibly different
baselines. The channel's uploads are still read once per run.

Three phases:

1. **`channels.list` in blocks of 50** — `part=snippet,statistics,contentDetails`:
   subscribers, `customUrl` and the uploads playlist id. **1 unit per 50
   channels.** *(Corrected 27/09/2026, owner: the uploads id is the one
   `contentDetails.relatedPlaylists.uploads` returns. `UC…` → `UU…` is not
   documented and is no longer used, although on night 1's 2,000 channels it
   held for all of them: `docs/itemcount-check-2026-09-27.json`.)*
   - **1b, off:** `playlists.list` in blocks of 50 (`part=contentDetails`)
     for channels with no inventory: `itemCount < 5` cannot reach 5 samples,
     so the channel is `not_computable` without being enumerated. Exact
     (`tests/test_read_cost.py`, 60 randomised channel sets) but measured not
     to pay on night 1's real channels: 4 of 2,000 had fewer than 5 uploads
     (0 of the 1,813 with a standard record, so no false skip). ~0.02 units
     per cold channel to save ~2 units on 0.2% of them. `ITEM_COUNT_PROBE`
     in `baseline.py`, off.
2. **`playlistItems.list`, one per channel, with pagination** —
   `part=contentDetails`, `maxResults=50`. Not batchable (*verified:
   HTTP 400*). Paginate until the oldest window of that channel's measured
   videos is covered or 3 pages are reached. The response carries
   `videoPublishedAt`: **filter the window here, before spending the next
   call.**
3. **`videos.list` in blocks of 50** — for the ids inside the window, to
   read duration, shape (§4.9) and views. *(27/09/2026: on a channel already in the
   inventory, ids whose stored format is neither unknown nor a measured
   format are not checked: a duration never changes, so a known Short cannot
   become a long-form sample. Exact: same baseline and same ids as a cold
   read, `tests/test_read_cost.py` and the 300 randomised histories of
   `tests/test_inventory.py`. When the 150-upload cap binds, every one of
   the 150 is still checked. Worst case, a cold channel, is the previous
   behaviour.)*
   *(27/09/2026, not applied: choosing candidates spread across the window
   before `videos.list`, fetching 50 at a time and stopping at 20 of the
   right format. It picks the 20 among the spread subset instead of evenly
   over all same-format videos in the window, so it returns different
   sample ids and in general a different baseline: a different estimator.
   Counterexample in `tests/test_read_cost.py`.)* Then, per measured video: keep the samples of
   **the same format**, and if more than 20 remain take 20 **chosen evenly
   across the window**, not the most recent.

*Corrected 25/09/2026 (T-08).* The first version chose the 20 before
`videos.list`. That cannot satisfy `01` §2: the format comes from the
duration, which only `videos.list` returns, so on a channel that publishes
both formats a pre-selected 20 would leave fewer of the right format — often
fewer than 5, a false `not_computable`. The date filter still runs before
`videos.list`; the format filter and the even choice run after it.

Cost: the `~1.6 units per new channel` of the first version assumed 20 ids
per channel in phase 3. Phase 3 now reads every in-window id, so it costs
`ceil(in-window ids / 50)` over the run. *Not measured*: the in-window count
per channel is unknown until the dry run (T-13), which is where it is
measured.

**Per channel, once per run.** A channel is read once in a run even when
several of its videos enter on the same day, over the union of their
windows; a channel already refreshed earlier in the run is not read again.

**Channel inventory (GATE-2, 25/09/2026).** A video's id, `publishedAt` and
duration never change, so they are kept across runs in `channel_inventory`
(§3.1.2). Views and privacy change: they are read in the run that computes
the baseline, and never reused from an earlier run. With an inventory:

- the uploads are refreshed **forward only**: pages from the newest, stopping
  at the first page that holds an already-known video;
- a full read (from the newest, up to 3 pages, until the window is covered)
  happens only for a channel never read, or whose inventory does not reach far
  enough back for the video being measured;
- **every candidate a fresh read would consider is checked in the run**:
  existence, privacy, duration and views of every in-window id (plus all 150
  most recent when the 3-page cap truncates a window), in one `videos.list`
  call per 50 ids. Gone or no longer public -> removed.

**Why it changes no baseline — and the one case where it does.**

- *The 3-page cap is kept exactly*: only the **150 most recent** uploads are
  ever considered, which is what 3 pages return. When a video among them is
  removed while the cap truncates a window, the channel is read again from the
  newest, as a fresh read would.
- *Every in-window candidate is checked, not only the chosen 20.* Checking only
  the chosen samples looked sufficient and is not: a removed video left in the
  list shifts the even spacing and changes the choice. Found by
  `tests/test_inventory.py` on 25/09, before any production use.
- A test proves it on 300 generated histories plus named cases (new uploads,
  removals, unlisted videos, changed and hidden views, more than 150 uploads,
  a measured video needing a deeper window): the same measured video gives
  the same baseline and the same sample ids warm and cold.
- **Declared exception:** the forward refresh stops at the first page holding
  a known upload, so an *old* video that becomes public again deeper in the
  list (for example private -> public) is not seen until the channel's next
  full read; a fresh read would include it. It is pinned by a dedicated test.
  It follows from the refresh rule decided at GATE-2.

*Cost*: the forward refresh saves `playlistItems` pages (~1 instead of ~2.07
per channel measured at T-13); the in-window check keeps `videos.list` at about
what a cold read costs. Measured after the change at T-13 (re-run).

*Corrected 25/09/2026: the first text of this section said views were read
only for the chosen samples and claimed exact equivalence; both were wrong.*

### 4.5 `backend/main.py`

| Endpoint | Change |
|---|---|
| `GET /api/posts` | `min_vpi` default 1.4 → **0**; filter `method_version='v2'`; `status` optional |
| `GET /api/analytics/top10` | **rewritten**: ranks on `post_daily` at `day_index = 1`, not on `posts.vpi_ratio`. Timeframe filters on **`entered_on`**, not `created_at`. Returns `n` and the distribution of `age_at_first_obs_days` |
| `GET /api/analytics/insights` | filter `method_version='v2'`; any segment figure is computed at `day_index = 1`, **by baseline band and by format**, with `n` shown. No figure pooled across bands or formats |
| `GET /api/analytics/keywords` | same |
| `POST /api/ingest/run` | **daily lock**: if an `ingest_run` for today already exists with outcome `ok`, return 409. Without it, two close calls double the quota spend |
| **`GET /api/ingest/status`** | **new**: the latest `ingest_run`. This is how the audit is read without opening the database |
| Trophy / checkout / Stripe webhook endpoints | **unchanged** |

### 4.6 Quota accounting

A single counter, incremented by every call, written to `ingest_run`.
Counted, not estimated.

```python
class QuotaCounter:
    def __init__(self): self.per_endpoint = Counter()
    def mark(self, endpoint): self.per_endpoint[endpoint] += 1
    @property
    def total(self): return sum(self.per_endpoint.values())
```

**Brake**: `QUOTA_MAX_DAILY` (default **9,900**, set by the owner on 29/09/2026;
it was 9,500: exceeding the real 10,000 costs no penalty, the API answers
"quota exceeded" until the reset, so the margin only has to keep the stop at a
recorded point, and 100 units do; 500 were ~140 channels a night). On reaching the ceiling the
run stops cleanly: the entries it did not reach are written without a
baseline and without a VPI, `baseline_rule = 'quota_stop'` (`01` §2), their
count is in the run report. ~~and the run ends with `outcome='partial'`.~~
**Corrected 27/09/2026:** census completeness and baseline completeness are
two states. `outcome` is the census alone (`ok` when every slice was read,
else `partial`): it decides the next reference, the exits and the certainty
of entries. `baselines_complete` is false when the brake fired or reads
failed; it decides nothing beyond each record's own `baseline_rule`. The
first version made a brake-stopped run partial although its census was
complete, which with night 1's turnover would have made every day partial:
no reference after day 0, every later entry uncertain, no exit ever closed.
`01` §4 speaks of a missed reading; a quota stop is not one. Night 1's row
is re-labelled `ok` (migration `v2_perimeter_long_census_state`). A
`quota_stop` record is now an incident, reported in the notes as such. It
never hits the 403; a 403 during the baselines is treated the same way.
*(Changed at GATE-2: the first version deferred them with a
`baseline_delayed` flag that no table defined.)* A transient failure (5xx,
network) is different: ~~those entries are not written and return as
uncertain entries after the next complete run.~~ *(27/09/2026: they are
written as `read_failed`, no baseline and no VPI, because the day now stays
the reference and an entry not written would not return.)*

### 4.7 Other scripts

- `refresh_showcase.py` — align to the new meaning of `ACTIVE` and to the
  `method_version='v2'` filter
- `aggiorna_token_outreach.py` — detach "token expired" from `status` and
  tie it to `left_on + CLAIM_DAYS` (01 §4.1; no window while the record is
  `ACTIVE`)
- `tools/weekly_digest.py` *(DIG-1, owner decision 01/10/2026)* — replaces
  `archive/backend/weekly_digest.py` (v1: a pooled top 3 by current VPI,
  "broke the algorithm", a call to action). Outside the backend runtime,
  read-only (REST GETs, service key; no YouTube quota), it writes a DRAFT
  for the owner and publishes nothing. Week = the last 7 readings with a
  complete census, never before `INDEX_START_DATE`. Hook (long-form videos
  first observed, how many seen in a single reading only); 3-2-1 by day-1
  VPI within ONE baseline band rotating by ISO week (the next band with at
  least 3 if the rotation lands on a thinner one, said in the draft), band
  and n stated, certain entries only; #1's highest VPI observed, views and
  days together if closed, day N if still charting; one limit line with its
  figure (the featured band's day-1 median beside the largest band's, each
  its own band, or the share without a computable baseline); close:
  iosaresearch.org. Voiceover ~55 s with timings, carousel texts and an HTML
  file in the `assets/social` style, an X post within 280 with the link as
  23. Likely live streams and re-uploads are flagged, never dropped. The
  wording rules are checked on every output and a draft that breaks one is
  not written (`tests/test_weekly_digest.py`)
- `printify_service.py`, `trophy_pipeline.py`, `generate_trophy.py`,
  `archivio_targhe.py`, `scalda_targhe.py` — **unchanged** *(01/10/2026:
  `generate_trophy.py` changed at APP-2, §6.7: no gamma, the v2 figures;
  optional parameters only)*

---

### 4.8 The queries of a reading under the 8 s statement timeout *(INC-1, measured 29/09/2026)*

Every call of the run goes through PostgREST, whose role carries
`statement_timeout = 8s`. The cost that grows is the one tied to `posts`
(~2,000 records a day, never deleted) and to `post_daily`. Measured on
production with `explain analyze`, day 2026-09-28 (8,088 posts, 6,928
active, 27,455 snapshot rows):

| call | what grows | plan | time |
|---|---|---|---|
| `entries_of_day` | `posts` | before INC-1: nested-loop anti join, `posts` scanned once per snapshot row (timed out at 8 s; reproduced 6.0 s); now merge anti join on `posts_external_post_id_idx` | 97 ms |
| `tracked_of_day` (one page) | active `posts` | hash join; `posts` seq scan (status filter), snapshot by `trend_snapshot_day_idx` | 23 ms inner, 148 ms per page |
| `close_exits_of_day` (as a select) | active `posts`, `post_daily` | hash anti join on the snapshot pkey; the two subqueries by `post_daily_pkey` | 182 ms |
| `apply_daily_views` (500 rows) | none (batch) | `posts` and `post_daily` by primary key | per batch |
| `records_of_day` | `posts` | `posts_entered_idx` | ms |
| `snapshot_export` (one page), `purge_snapshot_day` | one day of snapshot, capped at 7 days | `trend_snapshot_pkey` | ~0.8 s per page |
| channel inventory reads | `channel_inventory` | primary key | ms |

Every probe side of every join is indexed (`trend_snapshot` (day,
video_id), `posts.external_post_id`, `post_daily` (post_id, day)), so a
misestimate after a bulk write can no longer turn into a scan per row. The
one scan that grows linearly is the sequential read of `posts` for the
active filter (5.5 ms at 8,088 rows): about 0.1 s at 100,000 records, far
from the limit. Nothing else is close; nothing else changed. Re-measure with
the same `explain analyze` when `posts` passes 100,000 rows.

### 4.9 The format rule: Short as YouTube defines it *(FMT-1, owner decision 04/10/2026)*

`01` §1.1 is the rule; this section is how it is built. Measurements in `03`
§11.

**One function, one rule.** `vpi_core.formato(seconds, embed_w, embed_h,
published_at)` returns `SHORT`, `LONG`, `UNKNOWN`, or `None`:

```python
SHORT_MAX_SECONDS = 180                 # YouTube Help 15424877
SHORT_MAX_SECONDS_BEFORE = 60           # uploads before the date below
SHORT_3MIN_FROM = "2024-10-15"          # the date YouTube's rule took effect
EMBED_MAX_HEIGHT = 1000                 # maxHeight sent with part=player

def formato(seconds, embed_w, embed_h, published_at):
    if not seconds or seconds <= 0:
        return None                     # live in progress, premiere: as before
    if seconds > SHORT_MAX_SECONDS:
        return "LONG"
    if not embed_w or not embed_h:
        return "UNKNOWN"                # never guessed
    if int(embed_w) > int(embed_h):
        return "LONG"                   # wider than tall
    limit = SHORT_MAX_SECONDS if published_at >= SHORT_3MIN_FROM else SHORT_MAX_SECONDS_BEFORE
    return "SHORT" if seconds <= limit else "LONG"
```

`embedWidth`/`embedHeight` arrive as strings. `published_at` is compared as a
UTC date; absent (never seen on a chart video), the format is `UNKNOWN`,
never guessed. `formato_da_durata()` and `is_short_duration()` stay, unchanged,
for the v1 path only (`vpi_engine.get_channel_video_samples`); nothing in
the v2 path calls them. `FORMAT_RULE = "youtube_shape"` names the rule;
records opened before it carry `"duration_180"`.

**Every `videos.list` of the v2 path asks for the shape**, at no cost (1
unit per call whatever the parts, measured 04/10/2026, `03` §11):

| call | `part` | added parameter |
|---|---|---|
| census, `chart=mostPopular` (`census.py`) | `snippet,contentDetails,statistics,player,liveStreamingDetails` | `maxHeight=1000` |
| baseline phase 3 (`baseline.py`) | `contentDetails,statistics,status,player` | `maxHeight=1000` |

The response carries `player.embedHtml` too: a few hundred bytes per video,
bandwidth only. Nothing else reads it.

**Census (`census._merge`).** The format is `formato(...)`. `None` is
discarded as today (`discards.no_duration`); `UNKNOWN` is kept in the
snapshot, opens no record and is counted in `discards.unknown_shape`. Each
video also carries `duration_s` (seconds), `shape` (`vertical`, `square`, `wide`, null when not
returned) and `live` (true when `liveStreamingDetails.actualStartTime` is
present).

**Baseline (`baseline.py` phase 3).** The inventory format of each item read
is `formato(...)`, `UNKNOWN` stored as `NONE` (not a sample). Everything else
in §4.4 holds: a shape never changes, like a duration, so an item of known
other format is still skipped, and the proofs of §4.4 still apply to the new
format values.

**Schema** (one migration, `v2_fmt1_youtube_shape`):

```sql
alter table public.trend_snapshot drop constraint trend_snapshot_format_check;
alter table public.trend_snapshot add constraint trend_snapshot_format_check
  check (format in ('SHORT','LONG','UNKNOWN'));
alter table public.trend_snapshot
  add column duration_s int,
  add column shape text check (shape in ('vertical','square','wide')),
  add column live  boolean;

alter table public.posts
  add column duration_s  int,
  add column shape       text check (shape in ('vertical','square','wide')),
  add column was_live    boolean,
  add column format_rule text;
update public.posts set format_rule = 'duration_180'
 where method_version = 'v2' and format_rule is null;

-- channel_inventory: a Short by the old rule is not known under the new
-- one. Its format becomes null (unknown): the next run that needs it reads
-- it again, exactly like an item never read.
update public.channel_inventory ci
   set items = (select jsonb_object_agg(k, case when v->>1 = 'SHORT'
                                               then jsonb_build_array(v->0, null)
                                               else v end)
                  from jsonb_each(ci.items) as e(k, v))
 where ci.items::text like '%"SHORT"%';
```

`posts_format_valido` stays `SHORT`/`LONG`: an `UNKNOWN` video never opens a
record. Snapshot columns are written by the census and read by
`reprocess_day`, so a day finished from its snapshot writes the same
`duration_s`, `shape`, `was_live` and `format_rule` as the run that read it.
`duration_s` and `shape` on the record make the classification checkable
afterwards without another read.

**Cost: the reads are free, the corrected perimeter is not.** *Estimates*,
from `03` §11 and the runs of 02-03/10 (2.96 units per long-form entry;
6,955-8,320 units a night):

- about **100 more long-form records a night** (2.5% of ~4,000 entries up to
  180 s): ~300 units;
- in the first nights, the in-window items of measured channels whose old
  format was `SHORT` are read again once (they are null after the
  migration): a few hundred units a night, falling as the inventory refills.

Under the 9,900 brake on every night measured so far. What the brake does
not reach is `quota_stop` and is finished by the morning pass, as today
(§4.6). The first nights' `quota_total` is reported against these estimates
in the task log.

**Not in FMT-1: the records opened before it.** They keep `format_rule =
'duration_180'` until FMT-2 (§4.10) brings them under the new rule.

### 4.10 Bringing the past under the rule *(FMT-2, owner decision 04/10/2026)*

Owner decision: **every** record from the start of the series follows `01`
§1.1, paid with the quota the daily reading leaves unused. Starts after
FMT-1 is deployed and closed. Two phases, in this order:

**Phase 1 — the records never opened.** Videos up to 180 s, wider than tall,
first observed from `INDEX_START_DATE` to the last day read before FMT-1:
long-form for YouTube, never measured.

1. For each day D in that range, oldest first: the entries of D (present in
   D's snapshot, absent from the last complete reading before D — the
   definition of `entries_of_day`, with its `gap_days` and `entry_certain`)
   that the snapshot stores as `SHORT` and that have no record.
2. `videos.list` on them (blocks of 50, `part=snippet,contentDetails,player,
   liveStreamingDetails`, `maxHeight=1000`); `formato()` of §4.9. Only the
   `LONG` ones go on.
3. Each opens the record the night of D would have opened, with
   `reprocess_day`'s own machinery: country and category from
   `_first_slice` (canonical order, as for any reprocessed day); baseline by
   `baseline.py`, window anchored to the video's publication as always,
   read now (`baseline_computed_at`, `reprocessed_at` record the late read,
   `CLAUDE.md` §3); `format_rule = 'youtube_shape'` plus `duration_s`,
   `shape`, `was_live`; then `_catch_up` over every later day, from the
   snapshots: daily views into `post_daily`, VPI per day, peak, exit. **The
   numerators are the views stored each night: no unit is spent on them.**

Days outside the 7-day window are read from the archive
(`archivio/trend_snapshot/<day>.jsonl.gz`, §3.1), which is an exact copy
checked line by line before every delete: the entries of 27/09 already need
26/09 from there. **Retention is not suspended**: the archive serves the
recovery, and the table stays at 7 days (~7.6 MB a day, measured 04/10/2026:
53 MB for 192,268 rows), which the database size of §3.8 cannot spare.

**Phase 2 — the records opened under the duration-only rule**
(`format_rule = 'duration_180'`), oldest `entered_on` first.

1. The inventory items in each record's window whose format is null (the old
   `SHORT`, nulled by FMT-1 and not yet read by a night) are read once:
   `videos.list`, `formato()`, stored. A night may already have done it for
   its own channels; nothing is read twice.
2. **If no item in the window changed from the old Short to `LONG`, the
   candidates are the same, so the baseline is the same**: the record gets
   `format_rule = 'youtube_shape'` and nothing else changes. Exact, not
   approximate: `baseline_v2()` is a function of the candidate set.
3. Otherwise the candidates changed, and the baseline is computed again
   with `baseline_v2()` on the new set: views of every candidate read now
   (the views of the first computation were never stored per sample),
   `baseline_score`, `baseline_samples`, `baseline_rule`,
   `baseline_span_days`, `baseline_video_ids`, `baseline_computed_at`; then
   every `post_daily` row's `vpi_ratio` and `vpi_level` from its stored
   views, and `vpi_max`, `vpi_max_on`, the level fields. A `not_computable`
   record can become `standard` this way, and the reverse. The values
   replaced are kept first in `fmt2_history` (post id, every replaced
   column, the time): nothing is lost and the change can be audited or
   undone.

**Priority to the daily reading.** One run a day, `pg_cron` at **06:00 UTC**,
calling `POST /api/recover/run`: after the night's reading and its second
attempt, before the quota resets (07:00 UTC in summer, 08:00 in winter). It
does nothing unless the reading of the day that has just closed is finished
with `census_complete`, and no record of that day waits for the morning pass
(`quota_stop`, `read_failed`): the morning pass comes first.

**Budget: what the quota day has left.** The brake counts per run, not per
quota day, and a quota day (midnight to midnight, Pacific time) holds the
morning pass, the night and the second attempt. So every run that spends
units — reading, second attempt, morning pass, recovery — adds a row to a
new table `quota_ledger (at timestamptz, source text, units int)` when it
ends. The recovery's limit is

```
9,900 - (units in quota_ledger with (at at time zone 'America/Los_Angeles')::date = today's Pacific date) - 200
```

(200 for calls no run counts: scripts, measurements). It runs on a
`QuotaCounter` with that limit and stops at it; whatever it did not reach is
done the next day. Each run writes `fmt2_run` (start, end, units, phase, days
or records done, records opened, baselines changed) and its ledger row.

**Estimate**, `03` §11.1, to be replaced by the measured cost: phase 1 ~855
units of shapes plus ~2,100 of baselines (~700 records); phase 2 ~2,800 of
shapes plus ~2,400 of views. About 8,000 units, 4 to 8 days at the
1,000-2,900 units a night has left so far.

**Out of FMT-2** (architect, 04/10/2026). *Night 1*: the records entered
before `INDEX_START_DATE` (6,138, reference only) keep `duration_180`; phase
2 does not read them.

**Phase 3 — the windows the cap has dropped** (owner's go-ahead,
04/10/2026). Phase 2 judges a record with its channel inventory when the
inventory holds the whole window: it reaches the window's start, or holds no
upload published after the record's baseline read (the inventory drops an
old item only when it adds a newer one, so it then holds exactly that read's
candidates; the 150 cap applied then, and is the rule). Measured 04/10 on the
records from 27/09: 5,115 do not reach their window's start, 2,328 of them
with nothing newer than their read. The other **2,787 records (1,196
channels)** go to phase 3, after phase 1 and the rest of phase 2, on
leftover quota only:

1. per channel, `channels.list` (the uploads playlist, never derived), then
   `playlistItems.list` from the newest until it lists, for the channel's
   earliest baseline read, the 150 uploads published by then, or passes
   every window's start, or ends: about ceil((uploads since the read + 150)
   / 50) pages;
2. each record's pool is the 150 most recent uploads published by its own
   read: the candidates of that read. The items the inventory dropped are
   classified with `videos.list` in memory and **never stored in
   `channel_inventory` beyond the 150 cap**;
3. then phase 2's judgement, unchanged.

*Estimate* (architect, 04/10/2026): ~5,300 playlist pages and up to ~1,700
`videos.list` calls. Each run writes its pages and calls
(`fmt2_run.phase3_pages`, `phase3_videos`), reported against it.

*Declared*: an upload deleted from the channel since the record's read is
not listed any more, and nothing shows that it was there, except an item
unknown at FMT-1, which `fmt2_null_items` keeps.

**Left under the old rule** — never marked `youtube_shape`, recorded in
`fmt2_left` with the reason, never read again, counted in every run
(`fmt2_run.records_uncovered` = the rows of `fmt2_left`), the final count
declared in the correction log — only a record whose check cannot be
complete: an item of its window that had to be classified (unknown format,
or dropped by the cap) and that `videos.list` no longer returns (deleted or
not public); an item unknown at FMT-1 that the channel no longer lists
(`fmt2_null_items.epochs`, migration `20261004154702`, still places it in
the windows it belonged to); a channel whose uploads cannot be listed.

**Done when** no v2 record entered on or after `INDEX_START_DATE` has
`format_rule = 'duration_180'` outside `fmt2_left`, and every day of phase 1
is marked done in `fmt2_run`. The job then answers "nothing to
do"; its `pg_cron` entry is removed in the closing commit.

**As built** (`backend/recover_fmt.py`, 04/10/2026). Where the text above
leaves a choice, this is the one made:

- *The first reading under FMT-1* is the first `ingest_run` whose `discards`
  carry `unknown_shape` (only the FMT-1 census writes it). Phase 1 covers the
  days from `INDEX_START_DATE` to the day before it.
- *Phase 1 entries* are computed as `entries_of_day` computes them, from the
  stored snapshots (table, or the archive once the day has left the window),
  each checked against the count its census recorded. A video that already
  has a record opened by a later night under FMT-1 keeps it: counted in the
  run notes. The SHORT entries of a day are read in groups of 500 (shapes),
  then the long-form ones get their baselines in one call and their records;
  `fmt2_run.cursor` (`{day, after}`) holds the last group done, so a stop
  costs at most one group of shapes again. A record opened by phase 1 is the
  only record entered before the first FMT-1 reading with a non-null
  `duration_s`: a run stopped between writing it and replaying its later
  days finishes the replay without reading it again.
- *Phase 2, "changed"*: an item of the window is long-form now and 180 s or
  shorter (the old rule made it a Short). The items read: those whose format
  is unknown, and those that were unknown when FMT-1 started and that a
  night has since found long-form (the night does not keep the duration).
  Which items were unknown then is held in `fmt2_null_items`, captured at
  13:37 UTC on 04/10, after the FMT-1 migration and before any reading under
  FMT-1 (migration `20261004133725`: 6,202 channels, 231,518 ids, 4.9 MB;
  dropped when FMT-2 closes; their publication times added by
  `20261004154702`). A record with no baseline (`quota_stop`,
  `read_failed`) has no candidate set: rule only. A record is judged at
  most once per run.
- *The quota day ends*: the budget belongs to one Pacific quota day, so the
  run also stops 5 minutes before Google's reset (07:00 UTC in summer,
  08:00 in winter). A unit spent after it would count against the day of
  the next reading.
- *The ledger* sources are `reading`, `second attempt`, `reprocess` and
  `recovery`, one row per run, written in the run's `finally`; a ledger that
  cannot be written is noted and never fails a run. The recovery opens its
  row at 0 before its first unit and sets it to the run's total at every
  save, so a process that dies (no `finally`) stays counted to its last
  save; the run of 06/10 died and its 2,722 units were added by hand.
- *Memory*: between days phase 1 keeps only each day's view counts (about
  3 MB); a day's full snapshot rows (about 40 MB parsed) live only while that
  day is worked. The run of 06/10 kept every full day it read and the
  process died loading a seventh while it held six, on a 512 MB instance.

## 5. Scheduling

`cron.job` id 1 (`ingestione-iosa`): from `*/20 * * * *` to
**`59 23 * * *`**. **Switched off on 25/09/2026 at GATE-0** (migration
`v2_gate0_disable_v1_cron`): a single row from the v1 engine would have
entered the new population. T-14 re-enables it with the new schedule.

23:59 UTC = 16:59 Pacific, mid quota-day: no risk on the reset. Fixed UTC
hour year-round.

`render.yaml` unchanged, `IOSA_ENGINE_MODE=off` stays.

`run_engine.py`: `--un-ciclo` remains as the fallback if pg_cron fails. The
continuous loop and `--minuti` go.

**Second attempt** *(owner rule, 29/09/2026)*: at 00:30 UTC it fires
whenever the day just closed is not complete, and never repeats work that
succeeded (`main._second_attempt`):

| the day's row | the second attempt |
|---|---|
| none (Render did not wake) | the reading |
| census complete, processing failed or the run died after the census | `reprocess_day` from the snapshot: the census is never bought again |
| census not complete (failed before it, incomplete, or died before it) | the census again (`run_daily(rerun=True)`); the snapshot is the union of both attempts, both counted against one brake; records already written are not repeated |
| a run started less than 5 minutes ago | left alone |
| census complete and processing finished | 409: nothing to do |

A run "died" when its row has no `finished_at`, no reading is running in the
process, and it started more than 5 minutes ago (a restart kills the
task). Records the brake did not reach wait for the 08:20 morning pass: at
00:30 the quota has not reset.

**`reprocess_day <day>`** *(29/09/2026, INC-1b)*. `backend/reprocess_day.py`,
`POST /api/ingest/reprocess/{day}` (trigger token), or
`chiedi_ripresa_di_un_giorno(day)` from the database (token read from the
Vault). It finishes a day whose census is complete: loads the stored
snapshot as the census (never the charts), fetches only the titles of the
entries to be written (`videos.list` snippet, 1 unit per 50 ids: descriptive
fields, not the measurement), runs the same processing as the night
(`vpi_engine._process`), completes the day's records written without a
baseline (`complete_baselines`: only `quota_stop` and `read_failed`, never a
frozen baseline), and catches later days up for those records from their own
snapshots. It refuses a day whose census is not complete, whose snapshot is
not the one the census counted (`videos_seen`), that is still being read, or
whose later days are not finished complete censuses with intact snapshots.
The run report is rewritten: the original failure kept as "processing failed
at ...", the reprocess line, and the quota of both passes added.

- `ingest_run.census_complete`: written right after the snapshot, before any
  processing. It alone decides the reference (`entries_of_day`,
  `purge_snapshot_day`) and whether exits may be closed
  (`close_exits_of_day`). `outcome` says whether the processing finished.
- Records written or completed by `reprocess_day` carry `reprocessed_at`;
  `baseline_computed_at` is the actual read time of every baseline (per
  batch of 50 channels), night or not.
- A reprocessed record names as `country`/`category` the first of its sets in
  canonical order: the snapshot keeps the sets, not the slice pairs, and
  neither field enters any statistic.

**Morning pass** *(29/09/2026, INC-1d)*: pg_cron job `ripresa-iosa` at
**08:20 UTC**, after the quota reset in every season (midnight Pacific =
07:00 UTC in summer, 08:00 in winter), calls `ripresa_se_serve()`: if
yesterday's census is complete and either its processing failed or records
are waiting without a VPI (`quota_stop`, `read_failed`), it asks the backend
for `reprocess_day` of yesterday. Otherwise nothing is called. The brake is
unchanged; whatever it does not reach waits for the next morning.

**The nightly check** *(02:07 UTC, scheduled task; CHECK-2, owner decision
01/10/2026)*: `tests/check_run.sql`, and the same criteria for any day in
`tests/check_run.py`. While there is a backlog the 08:20 morning pass spends
quota of the same Google day (midnight Pacific) as the next 23:59 UTC
reading, so that reading can stop on Google's 403 well below the 9,900
brake. Such a `quota_stop` is **expected**, and the day can PASS, when the
census is complete, the notes carry Google's 403, and the morning pass units
falling in that quota day plus the run's `quota_total` reach 9,000. The check
fails only on a `quota_stop` not expected, the previous day still waiting,
`read_failed` > 0, an incomplete census or failed run, malformed records,
a Short record, the retention not run clean, or the database or Storage over
its threshold. Measured on 30/09 as the 02:07 check of 01/10 saw it
(`tests/check_run_replay_20260930.sql`): 1,205 `quota_stop`, 5,695 + 4,155 =
9,850 units, PASS.

---

## 6. Frontend

### 6.1 `lib/supabase-server.ts`

- `MIN_VPI_DISPLAY = 1.4` → **0**
- type `Post`: add `entered_on`, `left_on`, `days_charting`, `countries`,
  `categories`, `vpi_max`, `baseline_rule`, `method_version`
- `outlierDi()` / `contaDi()`: from `.eq('country', v)` to
  `.contains('countries', [v])`, plus `.eq('method_version','v2')`
- `vpi_color` and `vpi_level_name` leave the select: the colour comes from
  `livelloDaNumero()`, which already exists

- *(APP-4, 01/10/2026)* every public page reads **`public_records`**, not
  `posts`: the v2 records with two derived columns, `day_n` (an `ACTIVE`
  record's `post_daily` rows so far, counted as `days_charting` is at the
  close; `days_charting` once `CLOSED`) and `claim_open_until`
  (`left_on + CLAIM_DAYS − 1`, `claim_window.open_until`; null while
  charting). A view with `security_invoker`, so the caller's RLS applies and
  a hidden record is not in it. `days_charting` is never defaulted to 1.
  `claim_days()` mirrors `CLAIM_DAYS` (`tests/test_public_records.py`).
  Migration `20261001010327_v2_app4_public_records`

### 6.2 `app/page.tsx`

- `MIN_VPI_DISPLAY = 1.4` → 0
- `status='ACTIVE'` → `method_version='v2'`, with a "charting now / full
  archive" selector
- **line 750**: "Rotating sample across 34 countries and 15 categories" →
  full census, 13 categories *(was "12": corrected 25/09/2026, `01` §1)*
- **line 759**: "Each cycle scans the Most Popular Shorts of three countries and
  one category, rotating across 34 countries and 15 categories" → false
  twice, rewrite
- **line 439**: "within active 15-day window" → remove
- new columns: days charting, peak VPI reached
- **default sort is no longer raw VPI.** The page shows **our own overall
  chart**: the union of the category charts ordered by **views**, with each
  video's VPI beside it. The quantitative figure is YouTube's, the
  qualitative one is ours, and no average hides either. Any VPI-ranked view
  uses `day_index = 1`, per §4.2 of the protocol — sorting the mixed
  population by current VPI ranks by how long we have been measuring

**UI-3 (owner, 01/10/2026): the archive is paginated in the database.**
The page loaded at most 5,000 rows and filtered them in the browser, so past
that cap records vanished from the table, the filter counts and the CSV.
Now (`components/HomeArchive.tsx`, `lib/home-query.ts`):
- view (In Most Popular now / Left Most Popular / All), country, category,
  search, sort, page and page size (25/50/100) are in the URL and in the
  query (`public_records`, `range()`, `count: 'exact'`); the counts beside
  the filters come from `home_facets()` (security invoker, so RLS applies).
  Search matches `search_text` (handle, channel name, title); a video link
  is matched by its id. Sorts: views, first observed, left on, days in Most
  Popular; never VPI, for the reason above;
- first/previous/next/last, numbered pages, jump to page, "1-50 of N", a
  skeleton of the same height as the rows, keyboard and screen-reader
  labels, cards below 768 px;
- the CSV (`/api/export`) is generated by the server over the whole
  filtered set, in blocks of 1,000, without `claim_token`;
- no realtime subscription: the data changes once a day.
- *(UI-6, 01/10/2026)* the default view is **All**: the URL without `view`
  opens All; `?view=charting` and `?view=left` narrow it.
- *(UI-8, owner decision 01/10/2026)* a **Baseline band** filter (the bands
  of the disclosure box and of `BASELINE_BANDS`) and a VPI sort, high to low
  and low to high, allowed **only within one band**: the options are
  disabled until a band is chosen, a one-line hint says "VPI is compared
  only within a baseline band", and a URL cannot force a VPI sort without a
  band. The sort uses the VPI the table shows (`public_records.vpi_shown`:
  current while charting, highest observed after the exit). Also "First
  observed (oldest)". Counts from `archive_facets()`, with per-band counts.
  This amends the "never VPI" sort above, by the owner's decision.
- *(UI-10, owner decision 01/10/2026)* the views column has its own width,
  right-aligned, with space before the actions; "Analysis" and the link to
  YouTube are two icon buttons of the same size (32 px), side by side, each
  with a tooltip and an accessible label. The row height does not change.
Migrations `20261001203056`, `20261001203706` (trigram search index, the
owner's call on size), `20261001203752`; timings in the task log.
*(DB-1, owner decision 01/10/2026)* the trigram index is dropped
(`20261001225000`): the search scans `search_text`, about 30 ms a page at
14,136 records (task log).

### 6.3 `app/leaderboard/page.tsx`

**Rebuilt, not adjusted.** The current page ranks every video by its VPI
regardless of how long it has been measured. That ordering is confounded by
observation duration and cannot be published as a performance ranking
(`01-methodology-protocol.md` §4.2).

- the VPI ranking reads `post_daily` at **`day_index = 1`** and is titled
  "Top VPI — first day observed". No day selector: from day 2 onward the
  ranking would silently restrict itself to the videos that stayed long
  enough to have that reading
- `n` is displayed, and so is the range of `age_at_first_obs_days`
- one line under the title: *"VPI on the first day observed in Most Popular.
  Not age-adjusted."*
- timeframe 24h / 7d / 15d → **today / 7 days / 30 days / all** *(APP-11,
  01/10/2026: "today" → "latest reading", §6.7)*, filtered on
  `entered_on`. Today the filter runs on `created_at`, the video's
  publication date: the label promises one thing and the query does another
- a separate table by **peak VPI**, clearly labelled *"highest values
  observed"* — never as "best-performing videos", since the ordering is
  confounded by how long each video was measured

### 6.4 `app/claim/[token]/page.tsx`

- **line 176**: `createdAt + 15 days` computed in the browser from the
  publication date → `left_on + CLAIM_DAYS`, computed by the backend
  (`claim_window`, `GET /api/claim/{token}/window`). While the record is
  `ACTIVE` there is no window: `{"state": "charting", "start": null}`. Once
  closed: `start = left_on`, `expires_on = left_on + CLAIM_DAYS` (the first
  day the claim is closed), `open_until = expires_on − 1` (the last day it is
  open, the date the page shows). v1 archive records keep the window they
  were issued with, counted from their detection day: they have no
  `left_on`, and every one of them closed under v1
- "MEASUREMENT EXPIRED" and "Measurements stay published for 15 days" become
  false: the measurement no longer expires, the token does. Rewrite

### 6.5 `components/MetodologiaModal.tsx`

The public methodology text. **Rewrite entirely:**

- "observed public view count **within the 15-day window**" → daily series
  from entry to exit from the chart
- "**Content with VPI ≤ 1.0x is excluded from indexing**" → **remove**: this
  is the sentence that documents the censoring
- "15-Day Rolling Audit Window" → replace with the definition of the
  population (observed entry into Most Popular)
- add: baseline frozen at entry and the 7-90 day window, comparison within
  format, 34 countries and 13 categories *(was 12, `01` §1)*, one reading per day at 23:59 UTC,
  scale version and calibration date
- add: **the index start date** (`01` §1), and that everything in the charts
  before it is outside the measurement. *(27/09/2026: one constant,
  `INDEX_START_DATE`, in `backend/vpi_core.py` and
  `frontend/src/lib/index-start.ts`, equal to `01` §1
  (`tests/test_index_start.py`). Every public read of `posts` is floored at
  it; while it is unset nothing is published. The text states that the
  readings of 25 and 26 September 2026 are reference states only.)*
  *(28/09/2026: set to **2026-09-27**, the first run that passed
  `tests/check_run.py`.)*
- add, verbatim, the two sentences that carry the estimand:
  *"VPI is cumulative and age-dependent. It is recalculated daily while the
  video remains in the observed Most Popular chart, and is interpreted together
  with the video's age and its days observed in the chart."*
  *"VPI is not age-adjusted: values observed at different video ages are not
  directly comparable as age-independent measures of performance."*

### 6.6 `lib/segments.ts` and `lib/vpi-scale.ts`

No change now. At recalibration `vpi-scale.ts` changes **together with**
`vpi_core.py`, and `tests/audit_scala.py` already verifies they stay
identical.

### 6.8 `/room` — the Breakout Room *(ROOM-1, owner decision 08/10/2026)*

A static page, `frontend/public/room/index.html` (rewrite `/room` in
`next.config.ts`; linked from the home and the header; in the sitemap), that
reads `GET /api/room/latest` (the 7 most recent readings with
`census_complete`) or `GET /api/room?from=YYYY-MM-DD` (the 7 from that day):
records with format in `MEASURED_FORMATS`, `entry_certain`, not `hidden`,
`entered_on` one of those days and `>= series_floor()`, as
`{"from","to","v":[[video_id, title, ch_index, band_index, vpi_day1,
views_day1, baseline, entered_off, days_charting, left_off, vpi_max,
views_max, countries, live]],"c":[[channel_name, channel_handle]]}`;
`band_index` 0-4 from `baseline_band()`, 5 = no computable baseline; VPIs at
two decimals rounded down; `left_off` -99 while charting. One query
(`room_records()`), cached per state of the window's runs, gzip,
`Cache-Control: public, max-age=3600`. Its copy of the scale is held equal
to `VPI_SCALE` by `tests/test_scale.py`.

### 6.9 Canonical URLs *(SEO-1, 08/10/2026)*

Every indexable page names its own URL as `<link rel="canonical">`, without
a query string (`alternates.canonical`, or `metadatiPagina()` in
`lib/seo.ts`); the home names `/`, so its filtered and paginated addresses
are not duplicates; the static pages (`privacy.html`, `terms.html`,
`room/index.html`) carry the tag in their `<head>`. `/claim/` is disallowed in
`robots.ts` and carries none. Held by `tests/test_seo.py`; checked live by
`tests/check_seo.py` (every sitemap URL 200 and self-canonical, `/?page=2`
-> `/`).

### 6.7 Public app alignment *(owner decisions, 01/10/2026)*

Two status words only, on every page, from `lib/record-status.ts` and
`components/StatusBadge.tsx`: **"In Most Popular - day N"** while the record
is `ACTIVE`, **"Left Most Popular - N days"** once `CLOSED`. Never "hot",
"trending" or "popular" as a qualifier. While charting the value shown is
the current VPI and no award; after the exit, the highest VPI observed,
always with views and days in Most Popular (01 §4.1).

- **HOME-1** — the home is one table with a switch *In Most Popular now* /
  *Left Most Popular* / *All*, ordered by views, with columns dedicated to
  each view. Charting: day N, current VPI and its level, views, first
  observed. Left: highest VPI observed and its level, views, days in Most
  Popular, left on, claim open until. All: status, the VPI of the status,
  views. The status badge is the same on the outliers, country, category and
  creator pages (`OutlierList`). The CSV carries the status, both VPIs, left
  on and claim open until.
  *(UI-7, 01/10/2026)* the two states carry two icons wherever a state
  appears (home table, outliers, country, category, creator, claim): in
  Most Popular, a rising arrow in cyan with "day N"; left, a flag in grey
  with "N days, left <date>". The full label ("In Most Popular - day N",
  "Left Most Popular - N days, left <date>") is the tooltip and the
  screen-reader text; colour is never the only signal.
- **CLAIM-2** — the claim page. While the record is `ACTIVE`: a status block
  "IN MOST POPULAR - DAY N", the current VPI and its level, and *"Measurement
  in progress. The plaque and the claim window open when the video leaves
  Most Popular."* No plaque download, no order. After the exit: "LEFT MOST
  POPULAR - N DAYS", the highest VPI observed with views and days, the
  plaque, *"Claim open until <date>"* (`claim_window.open_until`). No plaque
  when `vpi_max` is null. The backend refuses the order the same way
  (`_plaque_state`: 409 while charting and without a VPI); v1 archive
  records keep their plaque.
- **APP-2** — the plaque image (`/api/trophy/preview`, `generate_trophy.py`)
  of a closed v2 record renders `vpi_max` (the highest VPI observed),
  `views_max`, `days_charting`, `entered_on` (first observed) and `left_on`
  (left Most Popular). Method line: *"median of the same channel's long-form
  videos published 7-90 days before this one"*. No gamma: the formula is
  `VPI = E_act / E_base`. Rendered only for closed records with a VPI (409
  while charting, 404 without a VPI); the archive name is
  `<token>_closed_<left_on>.png`, so a plaque rendered under another state is
  never served; the QR still names the token. v1 archive plaques keep their
  file and their method line. The signatures of the render functions only
  gain optional parameters: the Printify path (`trophy_pipeline`) is
  unchanged.
- **APP-1** — `/insights` leaves the navigation and the sitemap and is not
  indexed. It comes back rebuilt on the per-band × format cells (n and
  median, long-form only), never on pooled figures.
- **APP-5** — copy. Home footer and search line: long-form, "first
  observed". Creator pages: "long-form videos first observed in Most
  Popular", no "best" or "outperforming". Country and category pages:
  "Ordered by views, VPI beside each video", no "strongest" or "top
  measurement". The outliers index: "videos charting now".
- **APP-6** — a disclosure box (`components/DisclosureBox.tsx`) on Top VPI,
  the home page and the methodology modal: the day-1 median VPI per baseline
  band with its n, long-form only, fed live from the backend cells
  (`GET /api/analytics/day1-bands?format=LONG` → `_cells(_day1_rows())`, plus
  the records without a VPI by reason). It says why the high levels come from
  small channels (01 §4.2, 04), with the figures beside it, never smoothed.
- **APP-7** — a record without a VPI says why, from `baseline_rule`: *"No VPI
  (baseline not computable)"* for `not_computable`, *"No VPI yet (baseline
  still to be read)"* for `quota_stop` and `read_failed`; never *"No level
  (VPI < 1.5x)"*, which is only for a VPI below the first threshold. Beside
  every n: *"+ M without a computable baseline"* (`without_vpi` in
  `/api/analytics/top10` and `/day1-bands`). No claim date for a closed
  record without a VPI: there is no plaque.
  *(UI-9, owner decision 01/10/2026: in the tables the level column shows
  only level badges, Lvl 1-10. A record without a computable baseline shows
  "n/c", muted, tooltip "No VPI: the channel has fewer than 5 long-form
  videos in the baseline window" (`MIN_BASELINE_SAMPLES`); one waiting for
  its baseline, "pending"; a VPI under 1.5x, the value alone, tooltip
  "Below level 1". No "No VPI ..." or "No level ..." badge. The VPI value is
  the row's main figure, in a larger font. `components/VpiCell.tsx`.)*
- **APP-8** — creator pages list every record of the channel, charting and
  closed, highest VPI observed first, records without a VPI last
  (`recordDelCreator`). A page no longer 404s when its videos leave Most
  Popular; the sitemap counts closed records too.
- **APP-9** — `public/privacy.html` and `public/terms.html`, dated 1 October
  2026: no 15-day expiry (records do not expire; on request they are hidden
  from public pages), no Shorts (the baseline is the same channel's
  long-form videos published 7-90 days before), no TikTok.
- **APP-10** — the v1 social cards (`public/social/iosa-card-1..5.png`) are
  removed from the site; they stay in the git history.
- **APP-11** — Top VPI (`/leaderboard`): the timeframe "Today" becomes
  **"Latest reading"** (`timeframe=latest`: the records first observed on
  the day of the latest reading, `since` in the response; "today" was empty
  until the 23:59 UTC reading). No Shorts option: only the measured format
  is offered (`MEASURED_FORMATS`), and no ranking ever pools the two.
- **UI-4** — one header and one footer for every page (`SiteHeader`,
  `SiteFooter`, mounted by the root layout); no page draws its own. The
  logo is one image of the whole mark (the spike "I", "OSA", "Institute for
  Open Social Analytics"), `components/Logo.tsx`, from `res/IOSA Logo
  Trasp.png` (no vector source exists): trimmed, PNG and WebP at 1x
  (142×96) and 2x (284×192) in `public/brand`, explicit width and height,
  alt "IOSA - Institute for Open Social Analytics". No spike drawn beside
  text anywhere (it read "IIOSA"). The site is dark only (`globals.css`).
- **UI-1** — the formula stays as it is, "VPI = E_act / E_base" (owner
  decision). Only the baseline is described as measured: "median views of
  the same channel's long-form videos published 7-90 days before it" (the
  shared footer, the structured data, the FAQ of the home and of insights),
  never "recent videos of the same format".
- **UI-2** — the home says "Last reading: <day>, 23:59 UTC", where <day> is
  the latest `ingest_run` day with a complete census
  (`last_complete_reading()`, security definer, returns that date only).
  No "NODE STATUS: ACTIVE", no LIVE pulse.
- **UI-5** — the navigation calls the day-1 ranking "Top VPI", the title of
  its page; never "Top 10".
- **UI-11** *(owner decision, 02/10/2026)* — a VPI written for people is
  rounded **down** at the precision it is shown with, so the number never
  reaches a level threshold the record has not reached: 1.48 is "+1.4x",
  4.96 "+4.9x", 2,496 "+2.4Kx" (compact) or "+2,496x" (print). The level is
  still assigned on the full value (01 §4.3). One rule in two places that a
  test holds to the same strings: `frontend/src/lib/vpi-format.mjs`
  (`formatVPI`, `formatVPIFull`, re-exported by `lib/format.ts`) and
  `backend/vpi_format.py` (`format_vpi`, `format_vpi_full`: the plaque and
  checkout strings of `main.py`, the weekly digest). The floor works on the
  shortest decimal of the number, in string arithmetic. The CSV export and
  the API's numeric fields keep the full value.
- **UI-12** *(owner decision, 02/10/2026)* — the "ORDERED BY" box of the
  home shows the sort in use, with the Sort menu's label (`ORDINI`, reported
  by `HomeArchive` through `onOrdine`); a dash until the archive has read
  its state. The country and category pages have no sort control: they are
  ordered by views (`outlierDi`) and their subtitle says so.
- **FAQ-1** *(owner decision, 02/10/2026)* — the home FAQ states YouTube's
  change of view counting (from 24 August 2026 a long-form view counts as
  soon as playback starts; earlier views not recounted) and what it does to
  VPI: for videos published before 22 November 2026 (24 August +
  `BASELINE_MAX_AGE_DAYS`) the baseline includes videos counted mostly under
  the old rule, which tends to lower the baseline and raise VPI, not
  measured; baselines stay frozen. No change to the method or to the code
  that computes VPI.

---

## 7. Tests

| File | Action |
|---|---|
| `tests/test_vpi_core.py` | drop the `MIN_VPI_FOR_INGESTION` cases; add the 7-90 window, even sampling, `baseline_rule` |
| `tests/test_formati_motore.py` | rewrite: it mocks the old cycle's calls |
| `tests/audit_scala.py` | unchanged |
| **`tests/test_census.py`** | new: pagination, 403 → partial, 404 → slice skipped, dedup across slices |
| **`tests/test_entries.py`** | new: entries, exits, re-entries, day 0 with no yesterday, **missed day** |
| **`tests/test_baseline.py`** | new: blocks of 50, `UC`→`UU`, pagination up to 3, date filter before `videos.list`, even sampling, `not_computable`, exact quota count |

---

## 8. Release sequence

**Phase A — preparation**
1. Migrations: `trend_snapshot`, `post_daily`, `ingest_run`, new columns,
   `entries_of_day()`, removal of dead columns
2. `update posts set method_version='v1'` on the 28,917 existing records
3. TikTok branch and `weekly_digest.py` to `archive/`
4. `census.py`, `baseline.py`, quota counter, brake
5. Rewrite of `fetch_and_ingest_real_youtube_content`
6. New tests, green
7. **Dry run** on 3 countries with `QUOTA_MAX_DAILY=2000`, to verify the
   counter matches actual consumption as reported in the Google Cloud console

**Phase B — day 0**
8. `cron.job` to `59 23 * * *`, Render reactivated
9. First run in **snapshot-only** mode. Expected spend: 1,350 units.
   **Correction, 25/09/2026:** snapshot-only is automatic, not an
   environment flag to set on Render and then remember to unset. A reading
   with no `ingest_run` of outcome `ok` on an earlier day has no reference,
   so it is day 0 (`vpi_engine.has_complete_reading_before`). A partial day 0
   is no reference, so the next night is day 0 again. `SNAPSHOT_ONLY=true`
   still forces it.

**Phase C — day 1 and the gate**
10. Second full run, first v2 records
11. **Audit** from `ingest_run`:
    - `quota_total ≤ 9,900` → proceed
    - over → `BASELINE_SAMPLES_MAX = 10`, re-measure
    - still over → **reduce countries**, and only that
12. Frontend and public copy **only after** the audit passes

**Phase D — accumulation**
13. ~3 weeks of collection, no statistics published
14. Spillover verification (baseline at entry vs at exit)
15. Scale recalibration, versioned
16. Regeneration of public material and a correction note

---

## 9. Risks

| Risk | Effect | Mitigation |
|---|---|---|
| Quota overrun | entries without a VPI | brake at 9,900 (was 9,500), `quota_stop` records, completed by `reprocess_day` at the 08:20 UTC morning pass |
| **Missing snapshot day** | **every video looks new: spend explodes and entry dates are corrupted** | `entries_of_day()` compares against the most recent complete reading and writes `gap_days`; records created after a gap carry `entry_certain = false` and are excluded from entry-date statistics |
| Render asleep | run skipped | `timeout_milliseconds: 90000` already present + second attempt at 00:30 UTC |
| Double run | quota doubled | unique on `ingest_run.day` + 409 |
| Database full | writes rejected | see 3.7 |

---

## 10. Definition of done

- yesterday's `ingest_run` with `outcome='ok'` and `quota_total ≤ 9,900`
- every v2 record has `entered_on` set and `baseline_computed_at` equal to
  `entered_on`
- records with a VPI below 1 exist, and so do records with
  `baseline_not_computable`
- `post_daily` has one row per day for every `ACTIVE` post
- public pages no longer mention the 15-day window, the 15 categories, or
  the exclusion below 1.0x
- `tests/audit_scala.py` green
- the Printify / plaque flow works exactly as before
