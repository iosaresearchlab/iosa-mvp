-- GATE-0 decisions (Migert, 25/09/2026): legacy writers and record states.
-- Source: docs/02-technical-specification.md section 3.2.
-- Applied to project jodgdhkfkgvbyirvfcds on 2026-09-25 as migration
-- 20260925132338 "v2_gate0_posts_integrity". Below this header, the exact SQL
-- applied.
-- Rollback:
--   alter table public.posts drop constraint posts_baseline_state;
--   alter table public.posts alter column method_version set default 'v2';
--   (baseline_score stays nullable only if no row has a null in it)

-- A legacy writer can only produce rows that public queries exclude.
-- The v2 pipeline writes method_version = 'v2' explicitly.
alter table public.posts alter column method_version set default 'v1';

-- A not_computable record has no baseline and no VPI, and is never discarded.
alter table public.posts alter column baseline_score drop not null;

-- The only two v2 states. coalesce(..., false): a CHECK that evaluates to
-- NULL passes, so without it a v2 row with no baseline_rule would get through.
alter table public.posts add constraint posts_baseline_state check (
  coalesce(method_version = 'v1', false)
  or coalesce(baseline_rule = 'standard'
              and baseline_score is not null and vpi_ratio is not null, false)
  or coalesce(baseline_rule = 'not_computable'
              and baseline_score is null and vpi_ratio is null, false)
);
