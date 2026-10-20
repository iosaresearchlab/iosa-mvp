-- FIX-1b (20/10/2026): the active records' probe of close_exits_of_day is
-- indexed. On 19/10 at 00:37:56 UTC close_exits_of_day(2026-10-18) was
-- cancelled by the 8 s statement timeout of the API roles (57014), during a
-- night when the site's public_records reads were timing out too.
-- Measured on 20/10 with explain (analyze, buffers) of its select on day
-- 2026-10-19 (7,524 active records, 26,498 snapshot rows): the active filter
-- read posts through posts_format_idx (format, status) with status as a
-- non-leading key, 1,476 ms of the 1,651 ms; with this partial index 40 ms
-- of 73 ms.
--
-- Applied to project jodgdhkfkgvbyirvfcds on 2026-10-20 at 14:25 UTC as
-- migration 20261020142541 "v2_fix1b_active_records_index".
--
-- Rollback: drop index public.posts_v2_active_entered_idx.

create index if not exists posts_v2_active_entered_idx on public.posts (entered_on)
  include (external_post_id) where method_version = 'v2' and status = 'ACTIVE';
