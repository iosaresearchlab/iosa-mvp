-- GATE-2 decisions (Migert, 25/09/2026): the channel inventory, and
-- quota_stop records.
-- Sources: docs/02-technical-specification.md sections 3.1.2, 3.2, 4.4, 4.6;
-- docs/01-methodology-protocol.md section 2.
-- Applied to project jodgdhkfkgvbyirvfcds on 2026-09-25 as migration
-- 20260925184321 "v2_gate2_inventory_quota_stop". Below this header, the
-- exact SQL applied. posts before = after: 28,917 rows, md5 of every column
-- b0335510f2e7f258563b7119e60edd64.
-- Rollback:
--   drop table public.channel_inventory;
--   re-create posts_baseline_state as in 20260925144956 (only if no row
--   carries baseline_rule = 'quota_stop').

-- 02 §3.1.2: ids, publishedAt and durations never change; views are never
-- kept here. At most the 150 most recent uploads per channel.
create table public.channel_inventory (
  channel_id      text primary key,
  items           jsonb not null,
  covered_back_to timestamptz,
  capped          boolean not null default false,
  ended           boolean not null default false,
  refreshed_on    date
);
alter table public.channel_inventory enable row level security;
-- no policy: only the service role reads and writes here

-- 01 §2: entries the quota brake did not reach have no baseline and no VPI.
alter table public.posts drop constraint posts_baseline_state;
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
