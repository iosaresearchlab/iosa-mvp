-- claims is private. The policy "Allow public read on claims" (granted to
-- PUBLIC) would publish every purchase's customer_email, shipping_name,
-- shipping_address and stripe_session_id to anyone holding the anon key.
-- The table was empty when this was applied: nothing had been exposed.
-- Nothing in the browser reads claims; the purchase flow goes through the
-- backend. Decision by Migert, 25/09/2026.
-- Applied to project jodgdhkfkgvbyirvfcds on 2026-09-25 as migration
-- 20260925195429 "v2_claims_private". Below this header, the exact SQL applied.
-- Rollback (would reopen the hole): create policy "Allow public read on claims"
--   on public.claims for select to public using (true);
--   grant all on public.claims to anon, authenticated;
drop policy if exists "Allow public read on claims" on public.claims;
revoke all on public.claims from anon, authenticated;
