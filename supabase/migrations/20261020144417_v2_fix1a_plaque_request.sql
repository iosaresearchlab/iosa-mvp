-- FIX-1a (owner, 20/10/2026): the archived plaque PNG is rendered by the
-- plaques workflow only for plaques someone needs: tokens of creators we
-- contact, claim pages visited, purchases. plaque_request holds the tokens
-- asked for (the claim page's live plaque, checkout, a paid order waiting for
-- its print file, the social tasks); plaques_needed() adds every claim page
-- visited by a person (claim_visite, automatico not true). The workflow
-- renders those not in the archive yet. Service role only.
--
-- Applied to project jodgdhkfkgvbyirvfcds on 2026-10-20 at 14:44 UTC as
-- migration 20261020144417 "v2_fix1a_plaque_request"; then the three plaques
-- pending since 17/10 (Skurry, Lawlieet, Kapil) inserted as 'social'.
-- plaques_needed() answered 32 tokens.
--
-- Rollback: drop function public.plaques_needed(); drop table public.plaque_request.

create table public.plaque_request (
  claim_token  text primary key,
  source       text not null,
  requested_at timestamptz not null default now()
);
alter table public.plaque_request enable row level security;
revoke all on public.plaque_request from anon, authenticated;
grant select, insert, update on public.plaque_request to service_role;

create function public.plaques_needed()
returns setof text
language sql
stable
set search_path = public
as $f$
  select claim_token from plaque_request
  union
  select claim_token from claim_visite
   where claim_token is not null and automatico is not true
$f$;
revoke all on function public.plaques_needed() from public, anon, authenticated;
grant execute on function public.plaques_needed() to service_role;
