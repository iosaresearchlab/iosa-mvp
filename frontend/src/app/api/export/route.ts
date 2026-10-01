/**
 * Export CSV dell'archivio in home, generato sul server (UI-3, 01/10/2026).
 *
 * Copre l'intero insieme filtrato, non la pagina visibile: stessi filtri e
 * stesso ordine della tabella (lib/home-query.ts), letto a blocchi di 1.000
 * righe con la chiave pubblica, quindi sotto le stesse RLS (un record nascosto
 * su richiesta non c'e'). Nessun claim_token nel file.
 */
import { supabaseServer } from '@/lib/supabase-server';
import {
  applicaFiltri, applicaOrdine, daParametri, rigaCsv, COLONNE_CSV, CAMPI_HOME,
} from '@/lib/home-query';

export const dynamic = 'force-dynamic';
export const maxDuration = 60;

const BLOCCO = 1000;
const MASSIMO = 200_000;   // tetto di sicurezza: oltre, il file dice che e' troncato

export async function GET(request: Request) {
  const stato = daParametri(new URL(request.url).searchParams);
  const righe: string[] = [COLONNE_CSV.join(',')];
  let da = 0;
  let troncato = false;
  for (;;) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const base = applicaFiltri(supabaseServer.from('public_records').select(CAMPI_HOME) as any, stato);
    const { data, error } = await applicaOrdine(base, stato).range(da, da + BLOCCO - 1);
    if (error) {
      return new Response(`export failed: ${error.message}`, { status: 500 });
    }
    ((data || []) as Record<string, unknown>[]).forEach((r, i) => righe.push(rigaCsv(r, da + i + 1)));
    if (!data || data.length < BLOCCO) break;
    da += BLOCCO;
    if (da >= MASSIMO) { troncato = true; break; }
  }
  if (troncato) righe.push(`# truncated at ${MASSIMO} rows: narrow the filters`);
  const giorno = new Date().toISOString().slice(0, 10);
  return new Response(righe.join('\n') + '\n', {
    headers: {
      'Content-Type': 'text/csv; charset=utf-8',
      'Content-Disposition': `attachment; filename="iosa_index_${stato.vista}_${giorno}.csv"`,
      'Cache-Control': 'no-store',
    },
  });
}
