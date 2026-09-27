-- Owner decision, 27/09/2026 (docs/01 section 1, docs/02 section 4.6).
--  1. Census completeness and baseline completeness are two states.
--     ingest_run.outcome is the census alone; baselines_complete is new.
--  2. The run report carries the itemCount calls and the share of entering
--     channels already in channel_inventory.
--  3. read_failed: an entry whose reads failed after the retries is a record
--     without a baseline, like quota_stop, now that the day stays the
--     reference (before, it was not written and came back the next day).
--  4. Night 1 (2026-09-26) re-labelled under the corrected rule.
-- Applied to project jodgdhkfkgvbyirvfcds on 2026-09-27 as migration
-- 20260927145643 "v2_perimeter_long_census_state"; the SQL below is exactly
-- what ran. Measured after: 2026-09-26 outcome ok, baselines_complete false.
-- Rollback: drop the six columns; restore posts_baseline_state as in
-- 20260925211441 (only if no read_failed row exists); set day 2026-09-26
-- outcome back to 'partial'.
alter table public.ingest_run
  add column baselines_complete boolean,
  add column quota_playlists int,
  add column entering_channels int,
  add column entering_channels_in_inventory int,
  add column entering_long_channels int,
  add column entering_long_in_inventory int;

alter table public.posts drop constraint posts_baseline_state;
alter table public.posts add constraint posts_baseline_state check (
  coalesce(method_version = 'v1', false)
  or coalesce(baseline_rule = 'standard'
              and baseline_score is not null and vpi_ratio is not null
              and ((vpi_level is not null and vpi_level_name is not null and vpi_color is not null)
                   or (vpi_level is null and vpi_level_name is null and vpi_color is null)), false)
  or coalesce(baseline_rule in ('not_computable', 'quota_stop', 'read_failed')
              and baseline_score is null and vpi_ratio is null
              and vpi_level is null and vpi_level_name is null
              and vpi_color is null, false)
);

-- Night 1 under the corrected rule: its census was complete (413 slices with
-- data, 29 returning 404, 0 errors), so it is the reference; its baselines
-- were not (quota brake). Nothing else in the row changes.
update public.ingest_run
   set outcome = 'ok', baselines_complete = false,
       notes = notes || '; outcome corrected 27/09/2026 from partial to ok: census complete, baselines stopped by the brake (02 section 4.6)'
 where day = '2026-09-26' and outcome = 'partial' and slices_error = 0
   and slices_ok + slices_404 = 442;
