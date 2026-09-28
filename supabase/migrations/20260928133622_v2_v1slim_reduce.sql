-- V1-SLIM: posts_v1 reduced to the columns the v1 claim reads (owner
-- decision 28/09/2026). The v1 claim pages must keep working: 226 contacts in
-- outreach hold those tokens.
--
-- Before this migration, every column of all 28,917 rows and all 231 rows of
-- posts_v1_links were exported to Supabase Storage (private bucket
-- archivio), gzip, one to_jsonb(row)::text line per row, ordered by key:
--   posts_v1/posts_v1.jsonl.gz        28,917 rows, 5,784,926 bytes,
--                                     md5 of the lines 1620463f3669b26a7fac5091793493a5
--   posts_v1/posts_v1_links.jsonl.gz     231 rows,    14,980 bytes,
--                                     md5 of the lines 6485ee64739551ff8bdeb7f13a47ccf4
-- Each file was read back and its md5 equals that of the table, computed in
-- the database (string_agg(to_jsonb(row)::text, '|' order by key)). The SEC-2
-- checksum of 25/09 (78c8c5fd858a42734838743fba72044d, every column but
-- archived_at, order by id) still held on the table right before. The helper
-- v1_archive_export() (migration v2_v1slim_export) is dropped here.
--
-- Columns kept: exactly those read from a v1 record by the code, derived
-- from it on 28/09/2026 -
--   backend/main.py  _claim_lookup -> /api/trophy/preview: author_handle,
--     content_text, claim_token, vpi_level_name, vpi_ratio, engagement_score,
--     baseline_score, created_at, detected_at; claim_window: entered_on,
--     detected_at, created_at; checkout and Stripe webhook: author_handle,
--     vpi_ratio, vpi_level_name, content_text, created_at, engagement_score,
--     baseline_score, method_version, id;
--   frontend/src/app/claim/[token]/page.tsx: id, platform, author_handle,
--     content_text, created_at, detected_at, entered_on, days_charting,
--     engagement_score, baseline_score, vpi_ratio, vpi_max, views_max.
-- The union, 16 columns: id, claim_token, platform, author_handle,
-- content_text, engagement_score, baseline_score, vpi_ratio, vpi_level_name,
-- vpi_max, views_max, days_charting, created_at, detected_at, entered_on,
-- method_version. The other 31 are dropped (in the archive file).
--
-- The table is rebuilt rather than altered so the space is returned at once
-- (dropped columns are not reclaimed until a rewrite). The migration checks
-- that the 16 kept columns are identical, row for row, before and after, and
-- aborts otherwise. Access unchanged: RLS on, no policy, no grant to anon or
-- authenticated; claim_record_v1(token) returns the one row with that token.
-- posts_v1_links is kept as it is.
--
-- Applied to project jodgdhkfkgvbyirvfcds on 2026-09-28 as migration
-- 20260928133622 "v2_v1slim_reduce"; below this header, the exact SQL applied.
-- Measured after: 28,917 rows, kept columns md5 015fcc49b5fbe132cbe076aae213d775
-- = before; posts_v1 17,883,136 -> 8,937,472 bytes; database 80,981,139 ->
-- 72,051,859 bytes; outreach 226 rows, untouched.
--
-- Rollback: create the 47-column table from posts_v1/posts_v1.jsonl.gz
-- (jsonb_populate_record per line).

do $m$
declare
  n bigint; h_all text; h_before text; h_after text; n_after bigint;
begin
  select count(*), md5(string_agg(to_jsonb(v)::text, '|' order by v.id::text))
    into n, h_all from public.posts_v1 v;
  -- production's state at export time; a test database holds other rows
  if n = 28917 and h_all is distinct from '1620463f3669b26a7fac5091793493a5' then
    raise exception 'posts_v1 changed since the export (%): nothing reduced', h_all;
  end if;

  select md5(string_agg(jsonb_build_object(
      'id', id, 'claim_token', claim_token, 'platform', platform,
      'author_handle', author_handle, 'content_text', content_text,
      'engagement_score', engagement_score, 'baseline_score', baseline_score,
      'vpi_ratio', vpi_ratio, 'vpi_level_name', vpi_level_name, 'vpi_max', vpi_max,
      'views_max', views_max, 'days_charting', days_charting, 'created_at', created_at,
      'detected_at', detected_at, 'entered_on', entered_on,
      'method_version', method_version)::text, '|' order by id::text))
    into h_before from public.posts_v1;

  drop function public.claim_record_v1(text);
  create table public.posts_v1_slim as
    select id, claim_token, platform, author_handle, content_text, engagement_score,
           baseline_score, vpi_ratio, vpi_level_name, vpi_max, views_max, days_charting,
           created_at, detected_at, entered_on, method_version
    from public.posts_v1;
  drop table public.posts_v1;
  alter table public.posts_v1_slim rename to posts_v1;

  select count(*), md5(string_agg(to_jsonb(v)::text, '|' order by v.id::text))
    into n_after, h_after from public.posts_v1 v;
  if n_after <> n or h_after is distinct from h_before then
    raise exception 'kept columns differ after the rebuild: % rows % before, % rows % after',
      n, h_before, n_after, h_after;
  end if;
  raise notice 'posts_v1 reduced: % rows, kept columns md5 %', n_after, h_after;
end
$m$;

drop function public.v1_archive_export(text);

alter table public.posts_v1 add primary key (id);
alter table public.posts_v1 add constraint posts_v1_claim_token_key unique (claim_token);
alter table public.posts_v1 enable row level security;
revoke all on public.posts_v1 from anon, authenticated;
comment on table public.posts_v1 is
  'v1 records archived out of posts on 2026-09-25, reduced on 2026-09-28 to the 16 columns the v1 claim page and plaque read. Every column is in Storage, archivio/posts_v1/posts_v1.jsonl.gz. id = original posts.id.';

create function public.claim_record_v1(p_token text)
returns setof public.posts_v1
language sql stable security definer
set search_path = public
as $f$
  select * from public.posts_v1 where claim_token = p_token and p_token is not null
$f$;
revoke all on function public.claim_record_v1(text) from public;
grant execute on function public.claim_record_v1(text) to anon, authenticated, service_role;
