-- FIX-1c (20/10/2026): the creator page's read is indexed.
-- On 20/10 the API edge log showed ~10 HTTP 500s an hour on public_records,
-- every day: statement timeouts (anon, 3 s), almost all of them the creator
-- page's read (author_handle = ..., entered_on >= series start, order by
-- vpi_max), a sequential scan of posts (52,877 v2 rows; 40 ms alone, past
-- 3 s when crawlers walk the 7,091 sitemap URLs). The page took the failed
-- read for "no records" and served a 404 that ISR kept for 6 hours.
-- With this partial index the same read is an index scan: 7.8 ms
-- (explain analyze as anon, 20/10). Size 1,696 kB.
--
-- Applied to project jodgdhkfkgvbyirvfcds on 2026-10-20 at 15:31 UTC as
-- migration 20261020153158 "v2_fix1c_creator_index".
--
-- Rollback: drop index public.posts_v2_author_idx.

create index if not exists posts_v2_author_idx on public.posts (author_handle, entered_on)
  where method_version = 'v2';
