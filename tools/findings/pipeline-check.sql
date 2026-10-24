-- SOC-W1 (24/10/2026): the query behind the placeholder story "pipeline-check" (draft,
-- never published; it exists so the Findings route and its build are exercised).
-- Read-only. Run in the Supabase SQL editor or through the Supabase connector.
-- Output: frontend/content/findings/pipeline-check.data.json (read on 24/10/2026).
select entered_on, count(*) as records
from public_records
where method_version = 'v2'
  and entered_on between date '2026-10-17' and date '2026-10-23'
group by entered_on
order by entered_on;
