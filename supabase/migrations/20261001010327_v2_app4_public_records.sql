-- APP-4 (owner, 01/10/2026): day N for a record still in Most Popular, and
-- the claim date beside every closed record, on every public page.
--
-- days_charting is written only at the close (count of the record's
-- post_daily rows, 02 section 3.3); the pages showed "day 1" for every ACTIVE
-- record because they defaulted it to 1. public_records gives each v2 record
--   day_n             ACTIVE: its post_daily rows so far, counted exactly as
--                     days_charting is at the close; CLOSED: days_charting
--   claim_open_until  CLOSED: left_on + CLAIM_DAYS - 1, the last day the
--                     plaque can be claimed (claim_window.open_until,
--                     CLAIM-1); null while charting
-- security_invoker: the caller's RLS applies, so a hidden record (OPTOUT-1)
-- is not in it for the public roles. CLAIM_DAYS lives in backend/main.py;
-- claim_days() mirrors it and tests/test_public_records.py compares them.
--
-- Applied to project jodgdhkfkgvbyirvfcds on 2026-10-01 as migration
-- 20261001010327 "v2_app4_public_records"; below this header, the exact SQL
-- applied. Checked after: no ACTIVE record without day_n, no CLOSED one
-- without claim_open_until; day_n 1-4 on the published series; the home
-- query (5,000 rows by views) as anon 156 ms.
--
-- Rollback: drop view public.public_records; drop function public.claim_days().

create or replace function public.claim_days() returns int
  language sql immutable as 'select 15';
comment on function public.claim_days() is
  'Mirror of CLAIM_DAYS in backend/main.py (the source); tests/test_public_records.py compares them.';

create or replace view public.public_records with (security_invoker = true) as
select
  p.id, p.external_post_id, p.platform, p.format, p.author_handle, p.author_name,
  p.channel_id, p.channel_handle, p.content_text, p.post_url, p.country, p.category,
  p.countries, p.categories, p.subscribers, p.engagement_score, p.baseline_score,
  p.baseline_rule, p.vpi_ratio, p.vpi_level, p.vpi_level_name, p.vpi_max, p.vpi_max_on,
  p.views_max, p.views_final, p.days_charting, p.entered_on, p.left_on, p.status,
  p.claim_token, p.created_at, p.detected_at, p.entry_certain, p.age_at_first_obs_days,
  p.method_version,
  -- day N: the days the video has been observed in Most Popular, counted the
  -- way days_charting is written at the close (rows of its daily series)
  case when p.status = 'ACTIVE'
       then (select count(*)::int from public.post_daily d where d.post_id = p.id)
       else p.days_charting end as day_n,
  -- the last day the plaque can be claimed: left_on + CLAIM_DAYS - 1
  -- (backend claim_window.open_until); none while the record is charting
  case when p.status = 'CLOSED' and p.left_on is not null
       then p.left_on + public.claim_days() - 1 end as claim_open_until
from public.posts p
where p.method_version = 'v2';

grant select on public.public_records to anon, authenticated;
