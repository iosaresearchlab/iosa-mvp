-- APP-12: why claim_visite has no row after 24/09/2026 while Vercel counts
-- claim page views.
--
-- The claim page records a visit from the browser, with the public key:
-- insert into claim_visite (claim_token, post_id, ...) with the id of the
-- record the token resolved. Since 25/09 the v1 records live in posts_v1
-- (02 section 3.6), and the outreach tokens are v1 tokens: the page sends a
-- v1 id, which is not in posts, and the foreign key claim_visite.post_id ->
-- posts(id) refuses the row (23503). Reproduced on production as anon, in a
-- rolled-back transaction, with the record of iosa_LtdFPTUvgWIGxs0p:
-- "violates foreign key constraint claim_visite_post_id_fkey". The page
-- swallowed the error. The 5 rows in the table are all from 24/09, all on v1
-- tokens, their post_id nulled by the same move (ON DELETE SET NULL). No v2
-- token has had a visit. claim_eventi has the same foreign key and 0 rows.
--
-- Fix: post_id names the record in posts or in posts_v1, so it carries no
-- foreign key to posts. The 5 nulled visits get their id back from their
-- token (posts_v1_links holds the same link). The visits lost between 25/09
-- and today cannot be recovered: the browser never wrote them.
--
-- Applied to project jodgdhkfkgvbyirvfcds on 2026-10-01 as migration
-- 20261001010218 "v2_app12_claim_visits"; below this header, the exact SQL
-- applied. Checked after: 0 visits with a null post_id; an anon insert with a
-- post_id in neither table is accepted (rolled back).
--
-- Rollback: alter table ... add constraint ..._post_id_fkey foreign key
-- (post_id) references posts(id) on delete set null (would refuse v1 visits
-- again).

alter table public.claim_visite drop constraint if exists claim_visite_post_id_fkey;
alter table public.claim_eventi drop constraint if exists claim_eventi_post_id_fkey;

comment on column public.claim_visite.post_id is
  'APP-12: id of the record the claim token names, in posts (v2) or posts_v1 (v1 archive). No foreign key: a v1 id is not in posts.';
comment on column public.claim_eventi.post_id is
  'APP-12: id of the record the claim token names, in posts (v2) or posts_v1 (v1 archive). No foreign key: a v1 id is not in posts.';

-- The visits and events nulled when the v1 records left posts (25/09) get
-- their id back from the token: one archived record per token.
update public.claim_visite v set post_id = a.id
  from public.posts_v1 a where v.post_id is null and a.claim_token = v.claim_token;
update public.claim_eventi e set post_id = a.id
  from public.posts_v1 a where e.post_id is null and a.claim_token = e.claim_token;
