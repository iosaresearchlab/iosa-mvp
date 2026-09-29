-- INC-1c: ask the backend to reprocess a day, the way pg_cron asks for the
-- nightly reading: the trigger token is read from the Vault inside the
-- database, never handled outside it. Used for 2026-09-28 (INC-1) and for
-- any day whose processing is incomplete (reprocess_day). Callable by the
-- database owner only: no API role may execute it.
--
-- Applied to project jodgdhkfkgvbyirvfcds on 2026-09-29 as migration
-- 20260929124500 "v2_inc1c_reprocess_trigger"; below this header, the exact SQL applied.

create function public.chiedi_ripresa_di_un_giorno(p_day date)
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
    raise warning 'INGEST_TRIGGER_TOKEN non e'' nel Vault: ripresa non richiesta';
    return null;
  end if;

  select net.http_post(
    url := 'https://iosa-mvp-backend.onrender.com/api/ingest/reprocess/' || p_day::text,
    headers := jsonb_build_object(
      'Authorization', 'Bearer ' || segreto,
      'Content-Type', 'application/json'),
    body := '{}'::jsonb,
    timeout_milliseconds := 90000
  ) into richiesta;

  return richiesta;
end;
$function$;

revoke all on function public.chiedi_ripresa_di_un_giorno(date) from public, anon, authenticated, service_role;
