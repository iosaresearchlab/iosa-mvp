-- ROOM-1 (owner decision 08/10/2026; 02 section 6): the records of one week
-- for the Breakout Room (/room, GET /api/room/latest and /api/room?from=).
-- Read-only. One call answers the whole window as one JSON array, so the
-- query runs once instead of once per 1,000-row page. p_days (the window's
-- reading days) and p_formats are JSON arrays, as the other RPCs take them.
--
-- Filters, exactly as the endpoint documents them: format in the measured
-- formats, entry_certain true, hidden not true, entered_on one of the window's
-- reading days and >= the series floor. The day-1 row is joined by post_id
-- and day_index = 1: post_daily_pkey (post_id, day) backs the post_id side,
-- post_daily_index_idx (day_index, vpi_ratio desc) the day_index side (02
-- section 4.8). Measured 08/10/2026 on the window 01/10-07/10 (14,028
-- records): the query 66 ms warm, 2.5 s cold; the function with its JSON
-- (7,031,025 bytes) 263 ms. Far from the API role's statement timeout. No new index: the database size is a live constraint (02 section
-- 3.8).
--
-- Band, level, rounding and the response shape are computed in Python
-- (backend/main.py), from the band function and the scale the rest of the
-- backend uses.
--
-- Applied to project jodgdhkfkgvbyirvfcds on 2026-10-08 as migration
-- 20261008201102 "v2_room1_room_records" (database 214,543,507 bytes before
-- and after); below this header, the exact SQL applied.
--
-- Rollback: drop function public.room_records(jsonb, jsonb, date).

create function public.room_records(p_days jsonb, p_formats jsonb, p_floor date)
returns json
language sql
stable
set search_path = public
as $f$
  select coalesce(json_agg(json_build_object(
           'video_id', p.external_post_id,
           'title', p.content_text,
           'channel_id', p.channel_id,
           'channel_name', p.author_name,
           'channel_handle', p.channel_handle,
           'baseline_score', p.baseline_score,
           'baseline_rule', p.baseline_rule,
           'entered_on', p.entered_on,
           'left_on', p.left_on,
           'days_charting', p.days_charting,
           'countries', p.countries,
           'was_live', p.was_live,
           'vpi_max', p.vpi_max,
           'views_max', p.views_max,
           'vpi_day1', d.vpi_ratio,
           'views_day1', d.views)
         order by p.entered_on, p.external_post_id), '[]'::json)
    from posts p
    left join post_daily d on d.post_id = p.id and d.day_index = 1
   where p.format = any(array(select jsonb_array_elements_text(p_formats)))
     and p.entry_certain is true
     and p.hidden is not true
     and p.entered_on = any(array(select jsonb_array_elements_text(p_days)::date))
     and p.entered_on >= p_floor
$f$;

revoke all on function public.room_records(jsonb, jsonb, date) from public, anon, authenticated;
grant execute on function public.room_records(jsonb, jsonb, date) to service_role;
