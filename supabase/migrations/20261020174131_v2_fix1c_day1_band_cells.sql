-- FIX-1c (20/10/2026): the day-1 band cells are aggregated in the database.
-- On 19/10 at 05:49 UTC the backend restarted 7 s after paging ~28,000 day-1
-- rows of post_daily with every post column into memory (Render log): the
-- site's disclosure box (/api/analytics/day1-bands?format=LONG) rebuilt them
-- on every cache miss (5 minutes). This function returns one row per
-- baseline band instead: n, median day-1 VPI, and the records without VPI by
-- reason. Same filters as main._day1_rows (day_index = 1, v2, not hidden,
-- entry certain, entered on or after the series start, one format); the band
-- edges come from the caller (main.BASELINE_BANDS), so the bands are defined
-- in one place. Security definer: the anonymous role's row level security on
-- post_daily costs 5.6 s on this join (explain analyze, 20/10); the function
-- applies the same `not hidden` filter itself and returns only aggregates.
-- Measured 20/10: 172 ms for LONG (46,739 records) as the owner; over the API
-- as anon 2.3-3.7 s at first (its sort spilled 1.5 MB to disk), 0.38-0.78 s
-- with work_mem 16MB (set at 17:4x UTC with alter function, same day).
--
-- Applied to project jodgdhkfkgvbyirvfcds on 2026-10-20 at 17:41 UTC as
-- migration 20261020174131 "v2_fix1c_day1_band_cells".
--
-- Rollback: drop function public.day1_band_cells(date, text, numeric[]).

create or replace function public.day1_band_cells(p_floor date, p_format text, p_edges numeric[])
returns table (band_idx int, n int, median_vpi double precision, not_computable int, pending int)
language sql
stable
security definer
set search_path = public
set work_mem = '16MB'
as $f$
  select width_bucket(p.baseline_score, p_edges)                                  as band_idx,
         count(d.vpi_ratio)::int                                                  as n,
         percentile_cont(0.5) within group (order by d.vpi_ratio)                 as median_vpi,
         count(*) filter (where d.vpi_ratio is null
                            and coalesce(p.baseline_rule, '') not in ('quota_stop', 'read_failed'))::int as not_computable,
         count(*) filter (where d.vpi_ratio is null
                            and p.baseline_rule in ('quota_stop', 'read_failed'))::int as pending
    from post_daily d
    join posts p on p.id = d.post_id
   where d.day_index = 1
     and p.method_version = 'v2'
     and p.hidden = false
     and p.entry_certain
     and p.entered_on >= p_floor
     and p.format = p_format
   group by 1
$f$;
revoke all on function public.day1_band_cells(date, text, numeric[]) from public;
grant execute on function public.day1_band_cells(date, text, numeric[]) to anon, authenticated, service_role;
