-- The owner's scale (docs/01 section 4.3, 25/09/2026): below 1.5x a record
-- has a VPI and no level. A standard record therefore needs its baseline and
-- its VPI, and carries its three level fields all together or not at all.
-- The threshold itself is not written here: the owner may change it at any
-- time, and the code (vpi_core.VPI_SCALE) is where it lives.
-- Applied to project jodgdhkfkgvbyirvfcds on 2026-09-25 as migration
-- 20260925211441 "v2_scale_no_level"; the SQL below is exactly what ran.
-- Rollback: re-create posts_baseline_state as in 20260925184321 (only if no
-- standard row has null level fields).
alter table public.posts drop constraint posts_baseline_state;
alter table public.posts add constraint posts_baseline_state check (
  coalesce(method_version = 'v1', false)
  or coalesce(baseline_rule = 'standard'
              and baseline_score is not null and vpi_ratio is not null
              and ((vpi_level is not null and vpi_level_name is not null and vpi_color is not null)
                   or (vpi_level is null and vpi_level_name is null and vpi_color is null)), false)
  or coalesce(baseline_rule in ('not_computable', 'quota_stop')
              and baseline_score is null and vpi_ratio is null
              and vpi_level is null and vpi_level_name is null
              and vpi_color is null, false)
);
