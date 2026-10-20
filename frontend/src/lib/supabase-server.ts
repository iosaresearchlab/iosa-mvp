import { createClient } from '@supabase/supabase-js';
import { SERIES_FLOOR } from '@/lib/index-start';

// Client per i componenti server. Usa la stessa chiave pubblica del client:
// le policy RLS della tabella posts sono di sola lettura, quindi non c'e'
// nessun privilegio in piu' da proteggere qui.
//
// Serve un client separato perche' quello nel componente client vive nel
// browser, mentre queste pagine devono essere costruite lato server: e' tutto
// il punto dell'operazione, un crawler deve ricevere i dati gia' nell'HTML.
export const supabaseServer = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL || '',
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || '',
  { auth: { persistSession: false } }
);

/**
 * Nessuna soglia sul VPI nelle pagine pubbliche (docs/01 §7): l'indice non e'
 * censurato dal basso, e un record senza baseline calcolabile resta visibile.
 */
export const MIN_VPI_DISPLAY = 0;

export type Post = {
  id: string;
  external_post_id: string | null;
  author_handle: string | null;
  /** Identificatore stabile del canale. Null solo sui record antecedenti al backfill. */
  channel_id: string | null;
  /** Handle reale del canale (customUrl). author_handle lo rispecchia quando c'e'. */
  channel_handle: string | null;
  /** SHORT (square or vertical, <= 180s) or LONG. La baseline e' sempre dello stesso formato. */
  format: 'SHORT' | 'LONG' | null;
  author_name: string | null;
  content_text: string | null;
  post_url: string | null;
  country: string | null;
  category: string | null;
  platform: string | null;
  vpi_ratio: number | string | null;
  vpi_level: number | null;
  vpi_level_name?: string | null;
  baseline_score: number | string | null;
  engagement_score: number | string;
  claim_token: string | null;
  detected_at: string | null;
  entered_on: string | null;
  left_on: string | null;
  days_charting: number | null;
  countries: string[] | null;
  categories: string[] | null;
  vpi_max: number | string | null;
  views_max: number | string | null;
  baseline_rule: string | null;
  method_version: string | null;
  status?: 'ACTIVE' | 'CLOSED' | string | null;
  /** public_records: days observed in Most Popular so far (ACTIVE) or in all (CLOSED). */
  day_n?: number | null;
  /** public_records: last day the plaque can be claimed; null while charting. */
  claim_open_until?: string | null;
  vpi_max_on?: string | null;
};

// Ogni pagina pubblica legge public_records (APP-4, 01/10/2026): i record v2
// di posts con day_n e claim_open_until, sotto le stesse RLS (un record
// nascosto su richiesta non c'e', OPTOUT-1).
export const TABELLA_PUBBLICA = 'public_records';

// vpi_color e vpi_level_name non si leggono: il colore e il nome vengono da
// livelloDaNumero(vpi_level), unica scala (docs/02 §6.1).
const CAMPI =
  'id,external_post_id,format,author_handle,channel_id,channel_handle,author_name,content_text,post_url,country,category,platform,vpi_ratio,vpi_level,baseline_score,engagement_score,claim_token,detected_at,entered_on,left_on,days_charting,countries,categories,vpi_max,views_max,baseline_rule,method_version,status,day_n,claim_open_until,vpi_max_on';

/** I segmenti leggono gli array: un video presente in piu' fette conta in tutte. */
const COLONNA_ARRAY = { country: 'countries', category: 'categories' } as const;

/**
 * FIX-1c (20/10/2026): one read, its error never taken for "no data".
 * The anonymous role has a 3 s statement timeout and the free database
 * times out a few reads an hour under crawler load: a failed read is tried
 * once more after 1 s, then it throws, so the page answers 500 (no cache
 * keeps it; an ISR page keeps its last good version) instead of a 404 or an
 * empty list kept for 6 hours. Without a real database (the CI build points
 * at a local address that refuses connections, .github/workflows/ci.yml)
 * there is nothing to publish and the read is empty, as before.
 */
type Esito<T> = { data: T | null; error: { message: string } | null; count?: number | null };
const SENZA_DATABASE = !/^https:\/\//.test(process.env.NEXT_PUBLIC_SUPABASE_URL || '')
  || /^https?:\/\/(127\.0\.0\.1|localhost)([:/]|$)/.test(process.env.NEXT_PUBLIC_SUPABASE_URL || '');

export async function leggi<T>(etichetta: string, query: () => PromiseLike<Esito<T>>): Promise<Esito<T>> {
  let esito = await query();
  if (!esito.error) return esito;
  if (SENZA_DATABASE) return { data: null, error: null, count: null };
  await new Promise((r) => setTimeout(r, 1000));
  esito = await query();
  if (esito.error) throw new Error(`${etichetta}: ${esito.error.message}`);
  return esito;
}

/** I record v2 di un segmento ancora in classifica, ordinati per views (docs/02 §6.2). */
export async function outlierDi(
  colonna: 'country' | 'category' | 'author_handle',
  valore: string,
  limite = 60
): Promise<Post[]> {
  const { data } = await leggi('public_records', () => {
    const query = supabaseServer
      .from(TABELLA_PUBBLICA)
      .select(CAMPI)
      .eq('method_version', 'v2')
      .gte('entered_on', SERIES_FLOOR)
      .eq('status', 'ACTIVE');
    const filtrata = colonna === 'author_handle'
      ? query.eq(colonna, valore)
      : query.contains(COLONNA_ARRAY[colonna], [valore]);
    return filtrata.order('engagement_score', { ascending: false }).limit(limite);
  });
  return (data || []) as Post[];
}

/**
 * Tutti i record v2 di un creator, in classifica e usciti (APP-8, 01/10/2026):
 * una pagina creator non sparisce quando i suoi video lasciano Most Popular.
 * Prima il picco: ordinati per VPI piu' alto osservato, i record senza VPI in
 * fondo.
 */
export async function recordDelCreator(author: string, limite = 100): Promise<Post[]> {
  const { data } = await leggi('public_records', () =>
    supabaseServer
      .from(TABELLA_PUBBLICA)
      .select(CAMPI)
      .eq('method_version', 'v2')
      .gte('entered_on', SERIES_FLOOR)
      .eq('author_handle', author)
      .order('vpi_max', { ascending: false, nullsFirst: false })
      .order('engagement_score', { ascending: false })
      .limit(limite)
  );
  return (data || []) as Post[];
}

/** Quanti record v2 di un segmento sono ancora in classifica. */
export async function contaDi(
  colonna: 'country' | 'category' | 'author_handle',
  valore: string
): Promise<number> {
  const { count } = await leggi('public_records', () => {
    const query = supabaseServer
      .from(TABELLA_PUBBLICA)
      .select('id', { count: 'exact', head: true })
      .eq('method_version', 'v2')
      .gte('entered_on', SERIES_FLOOR)
      .eq('status', 'ACTIVE');
    return colonna === 'author_handle'
      ? query.eq(colonna, valore)
      : query.contains(COLONNA_ARRAY[colonna], [valore]);
  });
  return count ?? 0;
}
