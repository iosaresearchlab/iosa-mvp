-- OPS-3 (26/10/2026): the claim-page crawler of 25/10, identified from the
-- stored rows. Read-only: one select, no write; the raw rows stay as they are.
--
-- The owner's window: 25/10/2026 17:55-22:34 Rome = 16:55-21:34 UTC, 762 rows
-- on 761 tokens, desktop, no referrer, automatico false (02 section 6.12).
-- The rule applied here is the one of migration 20261028161007 read over the
-- whole stored history in both directions: a desktop visit without a referrer
-- belongs to a burst when the 24 hours before it OR the 24 hours after it hold
-- at least 20 such visits on other claim tokens. (The trigger sees only the 24
-- hours before, so live it lets the first 20 of a burst through.)
--
-- PASS when: every one of the 762 rows of the window is identified; no row
-- before 25/10 is (the visits of 20/09-24/10, people and known bots alike);
-- no phone visit and no visit with a referrer is, by construction.
with v as (
  select id, claim_token, vista_il, provenienza, schermo, automatico
    from claim_visite
),
nd as (select * from v where provenienza is null and schermo = 'desktop'),
r as (
  select v.*,
         (v.provenienza is null and v.schermo = 'desktop' and (
            (select count(distinct b.claim_token) from nd b
              where b.claim_token <> v.claim_token
                and b.vista_il >= v.vista_il - interval '24 hours' and b.vista_il < v.vista_il) >= 20
         or (select count(distinct b.claim_token) from nd b
              where b.claim_token <> v.claim_token
                and b.vista_il > v.vista_il and b.vista_il <= v.vista_il + interval '24 hours') >= 20
         )) as burst,
         (v.provenienza is null and v.schermo = 'desktop' and
            (select count(distinct b.claim_token) from nd b
              where b.claim_token <> v.claim_token
                and b.vista_il > v.vista_il - interval '24 hours' and b.vista_il < v.vista_il) >= 20
         ) as live_rule
    from v
),
w as (select * from r where vista_il >= '2026-10-25 16:55:00+00' and vista_il < '2026-10-25 21:35:00+00'),
c as (
  select
    (select count(*) from w) as window_rows,
    (select count(distinct claim_token) from w) as window_tokens,
    (select count(*) from w where burst) as window_identified,
    (select count(*) from w where live_rule) as window_live_rule,
    (select count(*) from r where vista_il < '2026-10-25 00:00:00+00') as before_rows,
    (select count(*) from r where vista_il < '2026-10-25 00:00:00+00' and burst) as before_identified,
    (select count(*) from r where vista_il >= '2026-10-25 21:35:00+00' and burst) as after_window_identified,
    (select count(*) from r where vista_il >= '2026-10-25 21:35:00+00') as after_window_rows,
    (select count(*) from r where burst and (schermo <> 'desktop' or provenienza is not null)) as phone_or_referrer_identified
)
select case when window_rows = 762 and window_identified = 762 and before_identified = 0
             and phone_or_referrer_identified = 0 then 'PASS' else 'FAIL' end as verdict,
       c.*
  from c;
