-- OPTOUT-1 (owner decision 01/10/2026): a removal request hides the record
-- from every public page and from the public API. It never deletes it: the
-- record stays in posts, the engine keeps measuring it, its series stays in
-- post_daily (01 section 3, 02 section 3.2).
--
--   posts.hidden     the flag; false for every record when added
--   posts.hidden_on  the day the request was honoured
--
-- The site reads posts with the public key, so the guarantee is RLS: anon
-- and authenticated never see a hidden record nor its daily series. The
-- service role bypasses RLS. The backend's public endpoints also filter
-- hidden = false, whatever key they run with (backend/main.py).
--
-- To honour a request (service role, SQL editor):
--   update posts set hidden = true, hidden_on = current_date
--    where external_post_id in ('<video id>', ...);
--
-- Applied to project jodgdhkfkgvbyirvfcds on 2026-10-01 as migration
-- 20261001010027 "v2_optout1_hidden"; below this header, the exact SQL
-- applied. Checked after: anon sees 14,136 of 14,136 records (none hidden);
-- inside a rolled-back transaction with one record hidden, anon sees 14,135
-- and 5 fewer post_daily rows.
--
-- Rollback: drop the two policies, recreate "Allow public read on posts"
-- and "public read" with using (true); drop the two columns.

alter table public.posts
  add column if not exists hidden    boolean not null default false,
  add column if not exists hidden_on date;

comment on column public.posts.hidden is
  'OPTOUT-1: removal request. Hidden from every public page and from the public API; the record is never deleted (01 section 3).';

alter table public.posts enable row level security;   -- already on in production

-- Public reads (anon, authenticated) never see a hidden record. The service
-- role bypasses RLS: the engine keeps measuring the record as before.
drop policy if exists "Allow public read on posts" on public.posts;
create policy "public read, not hidden" on public.posts
  for select to public using (not hidden);

-- Nor its daily series.
drop policy if exists "public read" on public.post_daily;
create policy "public read, record not hidden" on public.post_daily
  for select to public using (
    exists (select 1 from public.posts p where p.id = post_daily.post_id and not p.hidden));
