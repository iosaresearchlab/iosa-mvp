-- T-05 (docs/08-implementation-plan.md): new columns on posts.
-- Source: docs/02-technical-specification.md section 3.2.
-- Applied to project jodgdhkfkgvbyirvfcds on 2026-09-25 as migration
-- 20260925040845 "v2_t05_posts_new_columns". This file is the exact SQL applied.
-- Rollback: drop the added columns and indexes; the "not null" removal stays
-- (harmless).
-- Note: method_version defaults to 'v2', so the 28,917 existing rows read
-- 'v2' until T-06 sets them to 'v1'.

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
