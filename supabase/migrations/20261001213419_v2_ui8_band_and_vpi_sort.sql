-- UI-8 (owner, 01/10/2026): a baseline-band filter on the home archive, and
-- VPI sorts only within one band (VPI is compared only within a baseline
-- band; across bands it is not comparable, 01 section 4.2).
--
--   public_records.vpi_shown  the VPI the table shows: current (vpi_ratio)
--                             while charting, highest observed (vpi_max)
--                             after the exit - what a VPI sort orders by
--   archive_facets(...)       home_facets plus the band: the counts per view,
--                             country, category and baseline band for the
--                             records that match the other filters. A new
--                             name, not an overload: home_facets stays as it
--                             was (unused by the site from this commit) until
--                             the owner approves dropping it.
-- Bands: the edges of backend/main.py BASELINE_BANDS (100, 1k, 10k, 100k).
--
-- Applied to project jodgdhkfkgvbyirvfcds on 2026-10-01 as migration
-- 20261001213419 "v2_ui8_band_and_vpi_sort"; below this header, the exact
-- SQL applied.
--
-- Rollback: recreate public_records without vpi_shown (20261001203752);
-- drop function public.archive_facets(date, text, text, text, text, text, numeric, numeric).

create or replace view public.public_records with (security_invoker = true) as
select
  p.id, p.external_post_id, p.platform, p.format, p.author_handle, p.author_name,
  p.channel_id, p.channel_handle, p.content_text, p.post_url, p.country, p.category,
  p.countries, p.categories, p.subscribers, p.engagement_score, p.baseline_score,
  p.baseline_rule, p.vpi_ratio, p.vpi_level, p.vpi_level_name, p.vpi_max, p.vpi_max_on,
  p.views_max, p.views_final, p.days_charting, p.entered_on, p.left_on, p.status,
  p.claim_token, p.created_at, p.detected_at, p.entry_certain, p.age_at_first_obs_days,
  p.method_version,
  case when p.status = 'ACTIVE'
       then (select count(*)::int from public.post_daily d where d.post_id = p.id)
       else p.days_charting end as day_n,
  case when p.status = 'CLOSED' and p.left_on is not null
       then p.left_on + public.claim_days() - 1 end as claim_open_until,
  (coalesce(p.author_handle, '') || ' ' || coalesce(p.author_name, '') || ' ' || coalesce(p.content_text, '')) as search_text,
  -- the VPI the table shows: current while charting, highest observed after
  case when p.status = 'ACTIVE' then p.vpi_ratio else p.vpi_max end as vpi_shown
from public.posts p
where p.method_version = 'v2';

create or replace function public.archive_facets(
  p_floor date, p_status text, p_country text, p_category text, p_q text, p_video text,
  p_band_lo numeric, p_band_hi numeric)
returns table(kind text, value text, n bigint)
language sql stable security invoker
set search_path = public
as $f$
  with matching as (
    select status, countries, categories, baseline_score from public.posts
     where method_version = 'v2' and entered_on >= p_floor
       and (p_video is null or external_post_id = p_video)
       and (p_q is null or (coalesce(author_handle, '') || ' ' || coalesce(author_name, '') || ' '
                            || coalesce(content_text, '')) ilike '%' || p_q || '%')),
  in_band as (select * from matching
               where p_band_lo is null or (baseline_score >= p_band_lo
                                           and (p_band_hi is null or baseline_score < p_band_hi))),
  in_view as (select * from in_band where p_status is null or status = p_status)
  select 'status', status, count(*) from in_band
   where (p_country is null or p_country = any(countries))
     and (p_category is null or p_category = any(categories))
   group by status
  union all
  select 'country', c, count(*) from in_view, unnest(countries) c
   where p_category is null or p_category = any(categories) group by c
  union all
  select 'category', k, count(*) from in_view, unnest(categories) k
   where p_country is null or p_country = any(countries) group by k
  union all
  select 'band', b, count(*) from (
    select case when baseline_score < 100 then '<100' when baseline_score < 1000 then '100-1k'
                when baseline_score < 10000 then '1k-10k' when baseline_score < 100000 then '10k-100k'
                else '>=100k' end as b
      from matching
     where baseline_score is not null
       and (p_status is null or status = p_status)
       and (p_country is null or p_country = any(countries))
       and (p_category is null or p_category = any(categories))) x
   group by b
$f$;
grant execute on function public.archive_facets(date, text, text, text, text, text, numeric, numeric) to anon, authenticated;
