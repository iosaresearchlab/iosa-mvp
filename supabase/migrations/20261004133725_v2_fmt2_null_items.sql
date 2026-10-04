-- FMT-2 (02 section 4.10, phase 2): which inventory items were unknown when
-- FMT-1 started. Phase 2 decides whether a record opened under the
-- duration-only rule changes by whether an item of its window went from the
-- old Short to long-form, i.e. is long-form now and 180 s or shorter. Items
-- nulled by FMT-1 and read again by a night before the recovery reaches them
-- carry their new format but no duration: without this list they could not
-- be told from an item that was long-form all along, and phase 2 would have
-- to read every long-form item of every window again.
--
-- Captured at 13:37 UTC on 04/10/2026, after migration 20261004132227 and
-- before any reading under FMT-1: per channel of a duration_180 record, the
-- ids of the items whose format is null and whose publication falls in the
-- envelope of that channel's record windows ([earliest publication - 90 days,
-- latest publication - 7 days]). Measured: 6,202 channels, 231,518 ids,
-- 4,890,624 bytes. Dropped when FMT-2 closes.
--
-- Applied to project jodgdhkfkgvbyirvfcds on 2026-10-04 as migration
-- 20261004133725 "v2_fmt2_null_items"; below this header, the exact SQL
-- applied.
--
-- Rollback: drop table public.fmt2_null_items.

create table public.fmt2_null_items (
  channel_id text primary key,
  ids        text[] not null,
  taken_at   timestamptz not null default now()
);
alter table public.fmt2_null_items enable row level security;
-- no policy: service role only

insert into public.fmt2_null_items (channel_id, ids)
with w as (
  select channel_id, min(created_at) - interval '90 days' lo, max(created_at) - interval '7 days' hi
  from public.posts
  where method_version = 'v2' and format_rule = 'duration_180'
  group by channel_id
)
select ci.channel_id, array_agg(e.k order by e.k)
from w join public.channel_inventory ci on ci.channel_id = w.channel_id,
     jsonb_each(ci.items) e(k, v)
where e.v->>1 is null
  and to_timestamp((e.v->>0)::bigint) between w.lo and w.hi
group by ci.channel_id;
