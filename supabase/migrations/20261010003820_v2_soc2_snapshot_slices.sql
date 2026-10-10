-- SOC-2 (owner's go-ahead 08/10/2026, confirmed 10/10): the exact chart
-- slices of each video in the snapshot. countries[] and categories[] are two
-- separate sets per video: for a video in more than one category they cannot
-- say which country went with which category. slices holds the exact
-- 'country:category' pairs that returned the video (census._merge, written
-- by census.save_snapshot from the first reading after the deploy; earlier
-- rows keep null). Working data like the rest of trend_snapshot: 7-day
-- retention, archived to Storage by snapshot_export (to_jsonb of the row, so
-- the new column is archived with no change).
--
-- Applied to project jodgdhkfkgvbyirvfcds on 2026-10-10 at 00:38 UTC, after the
-- reading of 09/10 had finished (00:30:35), as migration 20261010003820
-- "v2_soc2_snapshot_slices" (database 220,662,931 bytes before and after: a
-- nullable column with no default writes nothing). Bytes per day, estimated
-- on the 27,597 rows of 09/10 from countries x categories: 1.26-1.32 MB.
--
-- Rollback: alter table public.trend_snapshot drop column slices.

alter table public.trend_snapshot add column slices text[];
