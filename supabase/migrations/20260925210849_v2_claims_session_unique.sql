-- One Stripe checkout session, one order. The webhook reserves the session
-- in claims before placing the Printify order; a repeated delivery of the
-- same event hits this index and is refused (backend/main.py,
-- _reserve_order). Before this, the guard read printify_product_id from
-- posts, which the webhook wrote with the anon key: posts has no UPDATE
-- policy, so the write was silently lost and the guard never fired.
-- Applied to project jodgdhkfkgvbyirvfcds on 2026-09-25 as migration
-- 20260925210849 "v2_claims_session_unique"; the SQL below is exactly what ran.
-- Rollback: drop index public.claims_stripe_session_id_key;
create unique index claims_stripe_session_id_key
  on public.claims (stripe_session_id) where stripe_session_id is not null;
