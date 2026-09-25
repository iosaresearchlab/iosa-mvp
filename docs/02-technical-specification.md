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
| `is_real_youtube_short()` | **Removed.** The only non-API call in the pipeline; classification is by duration |
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

### 3.1 New table `trend_snapshot` — a working buffer, plus the day-0 archive

**A working buffer: it is the reference point for "absent yesterday".** The
research data lives in the series and the records, which are never deleted.
The one exception is **day 0**: its rows are written with `permanent = true`
and are never deleted. They are the reference state of the population at the
start of the index (`01` §4) — a scientific record, never part of the
metrics.

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
  permanent     boolean not null default false,  -- true only for day 0
  primary key (day, video_id)
);
create index trend_snapshot_day_idx on public.trend_snapshot (day);
alter table public.trend_snapshot enable row level security;
-- no policy: only the service role writes here
```

Retention **7 days** (1 would suffice; 7 gives slack if a reading is
missed), day 0 excluded:

```sql
delete from trend_snapshot where day < current_date - 7 and permanent = false;
```

### 3.1.1 No day-0 exclusion list *(removed 25/09/2026, GATE-1)*

A `day0_pending` table was added at T-06 and dropped at GATE-1. Once the
reference for every day became the last complete reading (§3.5), it excluded
nothing: a day-0 video still charting is in the reference snapshot and is
excluded by the ordinary test; one that leaves and returns is an entry we
genuinely observed. The permanent day-0 snapshot stays — that is the archive,
not a mechanism.

**Day 0 must still be complete.** An incomplete day 0 is not a reference, so
it cannot produce false entries: day 1 would simply find no reference and
record nothing. But the day-0 snapshot is the permanent record of the
population at the start, and an incomplete one is a hole in it. On a partial
day 0: delete that day's snapshot rows and re-run day 0 before day 1.

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
  or coalesce(baseline_rule = 'not_computable'
              and baseline_score is null and vpi_ratio is null
              and vpi_level is null and vpi_level_name is null
              and vpi_color is null, false)
);
```

*(Extended at GATE-1, 25/09/2026: the level, its name and its colour follow
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

They stay readable and keep serving claim tokens already sent. Every public
v2 query filters `method_version = 'v2'`.

### 3.7 Storage optimisation

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
    One call per page, part=snippet,contentDetails,statistics,
    maxResults=50, following nextPageToken to exhaustion.
    On 403 everything stops and outcome='partial'.
    """

def save_snapshot(day, videos) -> int
def entries(day) -> list[dict]     # calls entries_of_day()
def close_exits(day, run_complete: bool) -> int
```

**`close_exits()` never runs after a partial run.** Absence is not observable
in an unfinished read: the videos stay open and that day is simply not an
observation for them. `run_complete` is false as soon as the census stopped
early (403) or the quota brake fired; the function then returns 0 without
touching the database.

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

1. **`channels.list` in blocks of 50** — `part=snippet,statistics`:
   subscribers and `customUrl`. **1 unit per 50 channels.** The uploads
   playlist is **not requested**: it is `UC…` → `UU…`. *Verified.*
2. **`playlistItems.list`, one per channel, with pagination** —
   `part=contentDetails`, `maxResults=50`. Not batchable (*verified:
   HTTP 400*). Paginate until the oldest window of that channel's measured
   videos is covered or 3 pages are reached. The response carries
   `videoPublishedAt`: **filter the window here, before spending the next
   call.**
3. **`videos.list` in blocks of 50** — for the ids inside the window, to
   read duration and views. Then, per measured video: keep the samples of
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

**No cache table.** The baseline is computed once and frozen: the cache is
only needed *within a run*, so a channel with two new videos is not paid for
twice. An in-memory dictionary is enough. The file-backed `TTLCache` goes.

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

**Brake**: `QUOTA_MAX_DAILY` (default **9,500**). On reaching the ceiling the
run stops cleanly, writes what it has, marks `outcome='partial'` and records
how many channels were left without a baseline. It never hits the 403.
Leftover videos are picked up the next day with `baseline_delayed = true`,
because that is no longer a measurement at entry and must be declared.

### 4.7 Other scripts

- `refresh_showcase.py` — align to the new meaning of `ACTIVE` and to the
  `method_version='v2'` filter
- `aggiorna_token_outreach.py` — detach "token expired" from `status` and
  tie it to `entered_on + CLAIM_DAYS`
- `printify_service.py`, `trophy_pipeline.py`, `generate_trophy.py`,
  `archivio_targhe.py`, `scalda_targhe.py` — **unchanged**

---

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

**Second attempt**: at 00:30 UTC, only if no `ingest_run` exists for the day
just closed. Covers the case where Render does not wake in time.

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

### 6.2 `app/page.tsx`

- `MIN_VPI_DISPLAY = 1.4` → 0
- `status='ACTIVE'` → `method_version='v2'`, with a "charting now / full
  archive" selector
- **line 750**: "Rotating sample across 34 countries and 15 categories" →
  full census, 12 categories
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
- timeframe 24h / 7d / 15d → **today / 7 days / 30 days / all**, filtered on
  `entered_on`. Today the filter runs on `created_at`, the video's
  publication date: the label promises one thing and the query does another
- a separate table by **peak VPI**, clearly labelled *"highest values
  observed"* — never as "best-performing videos", since the ordering is
  confounded by how long each video was measured

### 6.4 `app/claim/[token]/page.tsx`

- **line 176**: `createdAt + 15 days` computed in the browser from the
  publication date → `entered_on + CLAIM_DAYS`, computed by the backend
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
  format, 34 countries and 12 categories, one reading per day at 23:59 UTC,
  scale version and calibration date
- add: **the index start date** (`01` §1), and that everything in the charts
  before it is outside the measurement
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
9. First run in **snapshot-only** mode (`SNAPSHOT_ONLY=true`). Expected
   spend: 1,350 units

**Phase C — day 1 and the gate**
10. Second full run, first v2 records
11. **Audit** from `ingest_run`:
    - `quota_total ≤ 9,500` → proceed
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
| Quota overrun on day 1 | partial run | brake at 9,500, `partial` outcome, resume with a flag |
| **Missing snapshot day** | **every video looks new: spend explodes and entry dates are corrupted** | `entries_of_day()` compares against the most recent complete reading and writes `gap_days`; records created after a gap carry `entry_certain = false` and are excluded from entry-date statistics |
| Render asleep | run skipped | `timeout_milliseconds: 90000` already present + second attempt at 00:30 UTC |
| Double run | quota doubled | unique on `ingest_run.day` + 409 |
| Database full | writes rejected | see 3.7 |

---

## 10. Definition of done

- yesterday's `ingest_run` with `outcome='ok'` and `quota_total ≤ 9,500`
- every v2 record has `entered_on` set and `baseline_computed_at` equal to
  `entered_on`
- records with a VPI below 1 exist, and so do records with
  `baseline_not_computable`
- `post_daily` has one row per day for every `ACTIVE` post
- public pages no longer mention the 15-day window, the 15 categories, or
  the exclusion below 1.0x
- `tests/audit_scala.py` green
- the Printify / plaque flow works exactly as before
