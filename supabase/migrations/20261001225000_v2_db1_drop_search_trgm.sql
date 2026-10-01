-- DB-1 (owner decision 01/10/2026: "drop"): the trigram index on the home
-- search added in UI-3 (20261001203706) is dropped to save its 7,584 kB
-- (~540 bytes a record) against the database size limit (02 section 3.8).
-- The search keeps working by scanning public_records.search_text.
--
-- Run by the owner in the Supabase SQL editor on project jodgdhkfkgvbyirvfcds
-- on 2026-10-01 (UTC); this file records the exact SQL. The trigram extension
-- itself stays installed (it takes no space; not part of the decision).
--
-- Search timing as anon after the drop, EXPLAIN ANALYZE, median of 5, 14,136
-- v2 records, "trailer" (12 matches): page 29.8 ms, count 29.7 ms, facets
-- 32.0 ms, facets with country 31.8 ms. With the index (UI-3): page 243.4 ms,
-- count 30.2 ms.
--
-- Rollback: re-run 20261001203706_v2_ui3_search_trgm.sql.

drop index if exists public.posts_v2_search_trgm_idx;
