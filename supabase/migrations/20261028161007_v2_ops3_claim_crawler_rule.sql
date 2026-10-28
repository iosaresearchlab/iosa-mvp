-- OPS-3 (26/10/2026): a server-side rule joins the claim page's `automatico`
-- classification: a burst of desktop visits without a referrer on many claim
-- pages is not a person.
--
-- Measured (02 section 6.12): from 25/10 16:55 UTC a crawler opened the claim
-- pages one by one, 762 rows on 761 tokens by 21:34 UTC and still a few an
-- hour on 26/10, every row desktop, no referrer, `automatico` false. Its
-- requests (Supabase edge logs, 25/10 16:50-21:40 UTC): 755 POSTs from 745
-- different IP addresses in 61 networks and 6 countries, one user agent
-- (Chrome 155 on Linux, the current release), webdriver not set: a rotating
-- proxy, so "the same client" cannot be told by its address, and its user
-- agent is the one every Linux Chrome user sends. What sets it apart is the
-- count: before 25/10 (85 visits since 20/09) no 24 hours held more than 9
-- desktop visits without a referrer on other claim pages, all of them
-- already marked automatic, and one held a person's.
--
-- The rule: a visit with no referrer on a desktop screen is marked
-- `automatico = true` when the 24 hours before it already hold at least
-- CRAWL_TOKENS (20) such visits on other claim tokens. A phone visit or a
-- visit with a referrer is never touched; a value the page already set to
-- true stays true. The first 20 visits of a burst pass as they are, and a
-- person who opens a claim page on a desktop without a referrer during a
-- burst is marked automatic too: declared, both. The trigger reads the table
-- (security definer: the public role may insert, never read) and stores
-- nothing beyond the row; no address, no user agent. claim_eventi is not
-- touched: the crawler makes no gesture.
--
-- Applied to project jodgdhkfkgvbyirvfcds on 2026-10-28 at 16:10 UTC as
-- migration 20261028161007 "v2_ops3_claim_crawler_rule".
--
-- Rollback: drop trigger claim_visite_burst on public.claim_visite;
--           drop function public.claim_visite_burst().

create or replace function public.claim_visite_burst()
returns trigger
language plpgsql
security definer
set search_path = public
as $function$
begin
  if new.provenienza is null and new.schermo = 'desktop' and new.automatico is not true
     and (select count(distinct v.claim_token) from public.claim_visite v
           where v.provenienza is null and v.schermo = 'desktop'
             and v.vista_il > now() - interval '24 hours'
             and v.claim_token <> new.claim_token) >= 20 then
    new.automatico := true;
  end if;
  return new;
end
$function$;

revoke execute on function public.claim_visite_burst() from public, anon, authenticated;

create index if not exists claim_visite_noref_desktop_idx on public.claim_visite (vista_il)
  where provenienza is null and schermo = 'desktop';

drop trigger if exists claim_visite_burst on public.claim_visite;
create trigger claim_visite_burst before insert on public.claim_visite
  for each row execute function public.claim_visite_burst();
