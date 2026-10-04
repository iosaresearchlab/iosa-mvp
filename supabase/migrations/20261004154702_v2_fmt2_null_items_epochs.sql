-- FMT-2 (architect, 04/10/2026, point 3): the publication time of each item
-- of fmt2_null_items, from channel_inventory, still untouched by any reading
-- under FMT-1 (the last reading started 2026-10-03 23:59 UTC). With it, an
-- unknown item that a night later removes (deleted or no longer public) is
-- still placed in the windows it belonged to: a record whose window held it
-- cannot be classified, and stays under the old rule, counted.
--
-- Measured right after: 6,202 rows, 231,518 ids, 231,518 epochs, 0 null;
-- table 10,862,592 bytes (dropped when FMT-2 closes).
--
-- Applied to project jodgdhkfkgvbyirvfcds on 2026-10-04 as migration
-- 20261004154702 "v2_fmt2_null_items_epochs"; below this header, the exact
-- SQL applied.
--
-- Rollback: alter table public.fmt2_null_items drop column epochs.

alter table public.fmt2_null_items add column epochs bigint[];

update public.fmt2_null_items n
   set epochs = (select array_agg((ci.items->x.id->>0)::bigint order by x.ord)
                   from unnest(n.ids) with ordinality as x(id, ord))
  from public.channel_inventory ci
 where ci.channel_id = n.channel_id;
