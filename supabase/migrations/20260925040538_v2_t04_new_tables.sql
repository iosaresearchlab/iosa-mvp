-- T-04 (docs/08-implementation-plan.md): new tables for the v2 index.
-- Source: docs/02-technical-specification.md sections 3.1, 3.3, 3.4.
-- Applied to project jodgdhkfkgvbyirvfcds on 2026-09-25 as migration
-- 20260925040538 "v2_t04_new_tables". This file is the exact SQL applied.
-- Rollback: drop table public.post_daily, public.trend_snapshot, public.ingest_run;

-- 3.1 trend_snapshot: reference point for "absent from the previous reading".
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

-- 3.3 post_daily: the daily series. day_index 1 = first day observed.
create table public.post_daily (
  post_id   uuid not null references public.posts(id) on delete cascade,
  day       date not null,
  day_index int not null,
  views     numeric not null,
  vpi_ratio numeric,
  vpi_level int,
  primary key (post_id, day)
);
create index post_daily_day_idx   on public.post_daily (day);
create index post_daily_index_idx on public.post_daily (day_index, vpi_ratio desc);
alter table public.post_daily enable row level security;
create policy "public read" on public.post_daily for select using (true);

-- 3.4 ingest_run: one report per daily run.
create table public.ingest_run (
  id                uuid primary key default gen_random_uuid(),
  day               date not null unique,
  started_at        timestamptz not null,
  finished_at       timestamptz,
  outcome           text,
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
alter table public.ingest_run enable row level security;
-- no policy: written and read by the backend with the service role
