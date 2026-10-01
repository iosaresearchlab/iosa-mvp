-- UI-3 (01/10/2026): the home archive is paginated, filtered and counted in
-- the database. Before, the page loaded at most 5,000 rows and filtered them
-- in the browser: records past that cap vanished silently, and with them the
-- filter counts and the CSV export.
--
-- 1. Indexes for the orders a page can ask for (v2 records only), so a page
--    reads the rows in order instead of sorting the whole table.
-- 2. home_facets(): the counts beside the filters - records per view
--    (status), per country, per category - for the records that match the
--    other filters. Security invoker: the caller's RLS applies, a hidden
--    record (OPTOUT-1) is never counted. Granted to anon and authenticated.
--
-- Applied to project jodgdhkfkgvbyirvfcds on 2026-10-01 as migration
-- 20261001203056 "v2_ui3_home_archive"; below this header, the exact SQL
-- applied. home_facets was redefined by 20261001203752 (search_text).
-- Timings measured after, as anon (EXPLAIN ANALYZE): see docs/task-log.md UI-3.
--
-- Rollback: drop function public.home_facets(date, text, text, text, text, text);
-- drop index public.posts_v2_status_views_idx, public.posts_v2_views_idx,
-- public.posts_v2_status_entered_idx, public.posts_v2_left_idx;

-- the views a page can ask for, in order, without sorting the whole table
create index if not exists posts_v2_status_views_idx
  on public.posts (status, engagement_score desc nulls last, id) where method_version = 'v2';
create index if not exists posts_v2_views_idx
  on public.posts (engagement_score desc nulls last, id) where method_version = 'v2';
create index if not exists posts_v2_status_entered_idx
  on public.posts (status, entered_on desc, id) where method_version = 'v2';
create index if not exists posts_v2_left_idx
  on public.posts (left_on desc nulls last, id) where method_version = 'v2';

-- Facet counts for the home archive: the countries, categories and views of
-- the records that match the other filters. Security invoker: the caller's
-- RLS applies, so a hidden record is never counted.
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
       and (p_q is null or author_handle ilike '%' || p_q || '%'
            or author_name ilike '%' || p_q || '%'
            or content_text ilike '%' || p_q || '%'
            or post_url ilike '%' || p_q || '%')),
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
grant execute on function public.home_facets(date, text, text, text, text, text) to anon, authenticated;
