-- FMT-1 (owner decision 04/10/2026): a Short is what YouTube calls a Short,
-- a square or vertical video up to 180 s (60 s for uploads before
-- 15/10/2024); everything else is long-form (01 section 1.1). The shape comes
-- from player.embedWidth / embedHeight, read in the same videos.list calls
-- (02 section 4.9).
--
-- What it does:
--   trend_snapshot   format may be UNKNOWN (shape not returned: kept in the
--                    snapshot, never measured); new columns duration_s,
--                    shape, live, written by the census;
--   posts            new columns duration_s, shape, was_live, format_rule;
--                    every v2 record opened before this rule is marked
--                    format_rule = 'duration_180' (FMT-2 brings them under
--                    the new rule);
--   channel_inventory  an item whose stored format is SHORT under the old
--                    rule is not known under the new one: its format becomes
--                    null, so the next run that needs it reads it again,
--                    exactly like an item never read. Nothing else changes.
--
-- Applied to project jodgdhkfkgvbyirvfcds on 2026-10-04 as migration
-- 20261004132227 "v2_fmt1_youtube_shape"; below this header, the exact SQL
-- applied.
--
-- Measured around it (02 section 3.8): database 157,740,179 -> 187,468,947
-- bytes; channel_inventory 27,942,912 -> 44,318,720; posts 39,272,448 ->
-- 52,625,408 (the old row versions of the two UPDATEs, reused by later
-- writes after autovacuum). 6,575 inventory rows rewritten, 311,932 items
-- SHORT -> null; 20,135 v2 records -> 'duration_180'.
--
-- Rollback: redeploy the previous commit. The migration only adds columns
-- and widens a check; the inventory items it set to null are read again by
-- the old code as unknown, which is correct under either rule.

alter table public.trend_snapshot drop constraint trend_snapshot_format_check;
alter table public.trend_snapshot add constraint trend_snapshot_format_check
  check (format in ('SHORT','LONG','UNKNOWN'));
alter table public.trend_snapshot
  add column duration_s int,
  add column shape text check (shape in ('vertical','square','wide')),
  add column live  boolean;

alter table public.posts
  add column duration_s  int,
  add column shape       text check (shape in ('vertical','square','wide')),
  add column was_live    boolean,
  add column format_rule text;
update public.posts set format_rule = 'duration_180'
 where method_version = 'v2' and format_rule is null;

-- channel_inventory: a Short by the old rule is not known under the new
-- one. Its format becomes null (unknown): the next run that needs it reads
-- it again, exactly like an item never read.
update public.channel_inventory ci
   set items = (select jsonb_object_agg(k, case when v->>1 = 'SHORT'
                                               then jsonb_build_array(v->0, null)
                                               else v end)
                  from jsonb_each(ci.items) as e(k, v))
 where ci.items::text like '%"SHORT"%';
