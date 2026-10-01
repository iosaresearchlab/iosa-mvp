-- UI-3 (01/10/2026): a trigram index for the home search, so the search does
-- not scan the table as it grows. Measured right after: 7,584 kB for 14,136
-- v2 records (~540 bytes a record: ~1 MB a day at ~2,000 records a day,
-- ~380 MB a year against the 500 MB free tier). Kept or dropped by the owner
-- (02 section 3.8: the size is his call); the search works either way, it
-- matches public_records.search_text, the indexed expression.
--
-- Applied to project jodgdhkfkgvbyirvfcds on 2026-10-01 as migration
-- 20261001203706 "v2_ui3_search_trgm"; below this header, the exact SQL applied.
--
-- Rollback: drop index public.posts_v2_search_trgm_idx; drop extension pg_trgm;

create extension if not exists pg_trgm with schema extensions;
create index if not exists posts_v2_search_trgm_idx on public.posts
  using gin ((coalesce(author_handle, '') || ' ' || coalesce(author_name, '') || ' ' || coalesce(content_text, '')) extensions.gin_trgm_ops)
  where method_version = 'v2';
