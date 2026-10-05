-- FMT-2 (owner decision 04/10/2026, option A; 02 section 4.10): every record
-- from the start of the series follows the Short rule of 01 section 1.1, paid
-- with the quota the daily reading leaves unused.
--
--   quota_ledger   one row per run that spends units (reading, second
--                  attempt, reprocess, recovery), written when it ends: the
--                  brake counts per run, the recovery spends only what the
--                  Pacific quota day has left;
--   fmt2_run       one row per recovery run: units, phase, days done,
--                  records checked / opened, baselines changed, records left
--                  under the old rule in all (records_uncovered, the rows of
--                  fmt2_left), phase 3's playlist pages and videos.list
--                  calls, the position
--                  inside a phase-1 day (cursor), notes;
--   fmt2_history   every value phase 2 replaces, written in the same
--                  transaction as the replacement: nothing is lost and every
--                  change can be audited or undone;
--   fmt2_replace_baseline(post, values)  that transaction;
--   chiedi_recupero_fmt2() and the pg_cron job 'recupero-fmt2' at 06:00 UTC,
--                  calling POST /api/recover/run (the backend decides whether
--                  there is anything to do: the night finished, nothing
--                  waiting for the morning pass, budget left).
-- All tables: RLS on, no policy (service role only).
--
-- Applied to project jodgdhkfkgvbyirvfcds on 2026-10-05 as migration
-- 20261005131433 "v2_fmt2_recovery"; below this header, the exact SQL applied
-- (the comment block on fmt2_left aside). Database 201,886,867 -> 202,050,707
-- bytes. Right after, quota_ledger seeded with the units already spent in the
-- Pacific quota days the ledger did not yet record: the reading of
-- 2026-10-04 (7,096, at its finish) and the measurement of 04/10 (5).
--
-- Rollback: select cron.unschedule('recupero-fmt2'); fmt2_history restores
-- every replaced value (fmt2_replace_baseline in reverse); records opened by
-- phase 1 are entered before the first reading under FMT-1 and carry
-- duration_s (no record opened before FMT-1 does); then drop the functions
-- and the three tables.

create table public.quota_ledger (
  id     bigserial primary key,
  at     timestamptz not null default now(),
  source text not null,
  units  int not null
);
create index quota_ledger_at_idx on public.quota_ledger (at);
alter table public.quota_ledger enable row level security;

create table public.fmt2_run (
  id                bigserial primary key,
  started_at        timestamptz not null default now(),
  finished_at       timestamptz,
  units             int,
  phase             int,
  days_done         date[] not null default '{}',
  records_checked   int not null default 0,
  records_opened    int not null default 0,
  baselines_changed int not null default 0,
  records_uncovered int,
  phase3_pages      int,
  phase3_videos     int,
  cursor            jsonb,
  notes             text
);
alter table public.fmt2_run enable row level security;

-- The records the recovery leaves under the old rule because their check
-- cannot be complete, and why: 'gone' (an item of the window, unknown at
-- FMT-1 or dropped by the cap, that videos.list no longer returns or the
-- channel no longer lists), 'unlisted' (the channel's uploads cannot be
-- listed any more). Never read again. Their count is declared when FMT-2
-- closes.
create table public.fmt2_left (
  post_id uuid primary key references public.posts(id) on delete cascade,
  reason  text not null check (reason in ('gone', 'unlisted')),
  at      timestamptz not null default now()
);
alter table public.fmt2_left enable row level security;

create table public.fmt2_history (
  post_id              uuid not null references public.posts(id) on delete cascade,
  replaced_at          timestamptz not null default now(),
  baseline_score       numeric,
  baseline_samples     int,
  baseline_rule        text,
  baseline_span_days   numeric,
  baseline_video_ids   text[],
  baseline_computed_at timestamptz,
  vpi_ratio            numeric,
  vpi_level            int,
  vpi_level_name       text,
  vpi_color            text,
  vpi_max              numeric,
  vpi_max_on           date,
  post_daily           jsonb not null,
  primary key (post_id, replaced_at)
);
alter table public.fmt2_history enable row level security;

-- Phase 2, one record, one transaction: keep the old values, then write the
-- baseline of the new candidate set, every post_daily VPI from its stored
-- views, the record's VPI fields, and format_rule. Only a record still under
-- the duration-only rule: run twice, the second call changes nothing (0).
create function public.fmt2_replace_baseline(p_post_id uuid, p jsonb)
returns int
language plpgsql
set search_path = public
as $f$
declare
  n int;
begin
  insert into fmt2_history (post_id, replaced_at, baseline_score, baseline_samples, baseline_rule,
                            baseline_span_days, baseline_video_ids, baseline_computed_at,
                            vpi_ratio, vpi_level, vpi_level_name, vpi_color, vpi_max, vpi_max_on,
                            post_daily)
  select po.id, now(), po.baseline_score, po.baseline_samples, po.baseline_rule,
         po.baseline_span_days, po.baseline_video_ids, po.baseline_computed_at,
         po.vpi_ratio, po.vpi_level, po.vpi_level_name, po.vpi_color, po.vpi_max, po.vpi_max_on,
         (select coalesce(jsonb_agg(jsonb_build_object('day', pd.day, 'vpi_ratio', pd.vpi_ratio,
                                                       'vpi_level', pd.vpi_level) order by pd.day),
                          '[]'::jsonb)
            from post_daily pd where pd.post_id = po.id)
    from posts po
   where po.id = p_post_id and po.method_version = 'v2' and po.format_rule = 'duration_180';
  get diagnostics n = row_count;
  if n = 0 then
    return 0;
  end if;

  update post_daily pd
     set vpi_ratio = (x->>'vpi_ratio')::numeric,
         vpi_level = (x->>'vpi_level')::int
    from jsonb_array_elements(p->'daily') x
   where pd.post_id = p_post_id and pd.day = (x->>'day')::date;

  update posts po
     set baseline_score       = (p->>'baseline_score')::numeric,
         baseline_samples     = (p->>'baseline_samples')::int,
         baseline_rule        = p->>'baseline_rule',
         baseline_span_days   = (p->>'baseline_span_days')::numeric,
         baseline_video_ids   = array(select jsonb_array_elements_text(coalesce(p->'baseline_video_ids', '[]'))),
         baseline_computed_at = (p->>'baseline_computed_at')::timestamptz,
         vpi_ratio            = (p->>'vpi_ratio')::numeric,
         vpi_level            = (p->>'vpi_level')::int,
         vpi_level_name       = p->>'vpi_level_name',
         vpi_color            = p->>'vpi_color',
         vpi_max              = (p->>'vpi_max')::numeric,
         vpi_max_on           = (p->>'vpi_max_on')::date,
         format_rule          = 'youtube_shape'
   where po.id = p_post_id;
  return 1;
end
$f$;

revoke all on function public.fmt2_replace_baseline(uuid, jsonb) from public, anon, authenticated;
grant execute on function public.fmt2_replace_baseline(uuid, jsonb) to service_role;

create function public.chiedi_recupero_fmt2()
returns bigint
language plpgsql
security definer
set search_path = public, extensions, vault
as $function$
declare
  segreto text;
  richiesta bigint;
begin
  select decrypted_secret into segreto
  from vault.decrypted_secrets
  where name = 'INGEST_TRIGGER_TOKEN';

  if segreto is null then
    raise warning 'INGEST_TRIGGER_TOKEN non e'' nel Vault: recupero non richiesto';
    return null;
  end if;

  select net.http_post(
    url := 'https://iosa-mvp-backend.onrender.com/api/recover/run',
    headers := jsonb_build_object(
      'Authorization', 'Bearer ' || segreto,
      'Content-Type', 'application/json'),
    body := '{}'::jsonb,
    timeout_milliseconds := 90000
  ) into richiesta;

  return richiesta;
end;
$function$;

revoke all on function public.chiedi_recupero_fmt2() from public, anon, authenticated, service_role;

select cron.schedule('recupero-fmt2', '0 6 * * *', 'select public.chiedi_recupero_fmt2()');
