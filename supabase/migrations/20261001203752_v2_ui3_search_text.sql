-- UI-3 (01/10/2026): public_records.search_text, the text the home search
-- matches (handle, channel name, title), and home_facets on the same
-- expression, so the table and its filter counts always agree. A video link
-- is matched by its id (external_post_id), not by text.
--
-- Applied to project jodgdhkfkgvbyirvfcds on 2026-10-01 as migration
-- 20261001203752 "v2_ui3_search_text"; below this header, the exact SQL applied.
--
-- Rollback: recreate public_records without search_text (20261001010327) and
-- home_facets as in 20261001203056.

-- search_text: the text the home search matches, one expression for the
-- view, home_facets and the trigram index posts_v2_search_trgm_idx (if kept)
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
  (coalesce(p.author_handle, '') || ' ' || coalesce(p.author_name, '') || ' ' || coalesce(p.content_text, '')) as search_text
from public.posts p
where p.method_version = 'v2';

create or replace function public.home_facets(
  p_floor date, p_status text default null, p_country text default null,
  p_category text default null, p_q text default null, p_video text default null)
returns table(kind text, value text, n bigint)
language sql stable security invoker
set search_path = public
as $f$
  with matching as (
    select status, countries, categories from public.posts
     where method_version = 'v2' and entered_on >= p_floor
       and (p_video is null or external_post_id = p_video)
       and (p_q is null or (coalesce(author_handle, '') || ' ' || coalesce(author_name, '') || ' '
                            || coalesce(content_text, '')) ilike '%' || p_q || '%')),
  in_view as (select * from matching where p_status is null or status = p_status)
  select 'status', status, count(*) from matching
   where (p_country is null or p_country = any(countries))
     and (p_category is null or p_category = any(categories))
   group by status
  union all
  select 'country', c, count(*) from in_view, unnest(countries) c
   where p_category is null or p_category = any(categories) group by c
  union all
  select 'category', k, count(*) from in_view, unnest(categories) k
   where p_country is null or p_country = any(countries) group by k
$f$;
