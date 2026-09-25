-- The v1 records leave posts (decision by Migert, 25/09/2026). posts is the
-- table the site and the statistics read, and from day 1 the v2 series
-- writes into it: two rules on one scale. Nothing is deleted, nothing is
-- recomputed. Every v1 row moves, unchanged, to posts_v1, which no page and
-- no statistic reads.
--
-- The original post id is kept as posts_v1.id. The rows that referenced a
-- v1 post (outreach, claim_visite, claim_eventi: ON DELETE SET NULL) are
-- snapshotted in posts_v1_links (source table, source row id, post id)
-- before the move, so every link blanked by the foreign key is
-- reconstructable. outreach and claim_visite also keep claim_token.
--
-- A v1 claim token still resolves (08 T-20): claim_record_v1(token) returns
-- the one archived record with that token, and nothing else. The table
-- itself is not readable by the API roles, so the archive cannot be listed.
--
-- The move is checked inside the migration: same count and same md5 of the
-- rows (as jsonb, ordered by id) in posts before and in posts_v1 after, and
-- nothing that would cascade (claims, post_daily) points at a v1 row. Any
-- mismatch aborts the whole migration.
--
-- Applied to project jodgdhkfkgvbyirvfcds on 2026-09-25 as migration
-- 20260925195747 "v2_archive_v1_records". Below this header, the exact SQL
-- applied. Measured: 28,917 rows, md5 78c8c5fd858a42734838743fba72044d
-- before (posts) and after (posts_v1); links kept: outreach 226,
-- claim_visite 5, claim_eventi 0.
-- Rollback: insert into posts select <posts columns> from posts_v1; then
-- restore post_id from posts_v1_links; drop the three objects.

create table public.posts_v1 (like public.posts including all);
alter table public.posts_v1 add column archived_at timestamptz not null default now();
alter table public.posts_v1 enable row level security;
revoke all on public.posts_v1 from anon, authenticated;
comment on table public.posts_v1 is
  'v1 records archived out of posts on 2026-09-25. Not read by the site or the statistics. id = original posts.id.';

create table public.posts_v1_links (
  source_table text not null,
  source_id    uuid not null,
  post_id      uuid not null,
  claim_token  text,
  primary key (source_table, source_id)
);
alter table public.posts_v1_links enable row level security;
revoke all on public.posts_v1_links from anon, authenticated;
comment on table public.posts_v1_links is
  'Rows that referenced a v1 post before the 2026-09-25 archive (their post_id was set null by the foreign key).';

do $m$
declare
  n_before bigint; h_before text; n_after bigint; h_after text; n_links bigint;
begin
  select count(*), md5(string_agg(to_jsonb(p)::text, '|' order by id))
    into n_before, h_before from public.posts p where method_version = 'v1';

  if exists (select 1 from public.claims c join public.posts p on p.id = c.post_id
             where p.method_version = 'v1')
     or exists (select 1 from public.post_daily d join public.posts p on p.id = d.post_id
                where p.method_version = 'v1') then
    raise exception 'a cascading row points at a v1 record: nothing moved';
  end if;

  insert into public.posts_v1_links
    select 'outreach', o.id, o.post_id, o.claim_token from public.outreach o
      join public.posts p on p.id = o.post_id where p.method_version = 'v1'
    union all
    select 'claim_visite', v.id, v.post_id, v.claim_token from public.claim_visite v
      join public.posts p on p.id = v.post_id where p.method_version = 'v1'
    union all
    select 'claim_eventi', e.id, e.post_id, e.claim_token from public.claim_eventi e
      join public.posts p on p.id = e.post_id where p.method_version = 'v1';
  get diagnostics n_links = row_count;

  insert into public.posts_v1 select p.*, now() from public.posts p where method_version = 'v1';

  select count(*), md5(string_agg((to_jsonb(v) - 'archived_at')::text, '|' order by id))
    into n_after, h_after from public.posts_v1 v;
  if n_after <> n_before or h_after is distinct from h_before then
    raise exception 'archive mismatch: % rows % before, % rows % after',
      n_before, h_before, n_after, h_after;
  end if;

  delete from public.posts where method_version = 'v1';

  raise notice 'archived % v1 records, md5 %, % links kept', n_after, h_after, n_links;
end
$m$;

create function public.claim_record_v1(p_token text)
returns setof public.posts_v1
language sql stable security definer
set search_path = public
as $f$
  select * from public.posts_v1 where claim_token = p_token and p_token is not null
$f$;
revoke all on function public.claim_record_v1(text) from public;
grant execute on function public.claim_record_v1(text) to anon, authenticated, service_role;
