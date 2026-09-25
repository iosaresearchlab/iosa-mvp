import { createClient } from '@supabase/supabase-js';

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
  /** SHORT (<= 180s) oppure LONG. La baseline e' sempre dello stesso formato. */
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
};

// vpi_color e vpi_level_name non si leggono: il colore e il nome vengono da
// livelloDaNumero(vpi_level), unica scala (docs/02 §6.1).
const CAMPI =
  'id,external_post_id,format,author_handle,channel_id,channel_handle,author_name,content_text,post_url,country,category,platform,vpi_ratio,vpi_level,baseline_score,engagement_score,claim_token,detected_at,entered_on,left_on,days_charting,countries,categories,vpi_max,views_max,baseline_rule,method_version';

/** I segmenti leggono gli array: un video presente in piu' fette conta in tutte. */
const COLONNA_ARRAY = { country: 'countries', category: 'categories' } as const;

/** I record v2 di un segmento ancora in classifica, ordinati per views (docs/02 §6.2). */
export async function outlierDi(
  colonna: 'country' | 'category' | 'author_handle',
  valore: string,
  limite = 60
): Promise<Post[]> {
  const query = supabaseServer
    .from('posts')
    .select(CAMPI)
    .eq('method_version', 'v2')
    .eq('status', 'ACTIVE');
  const filtrata = colonna === 'author_handle'
    ? query.eq(colonna, valore)
    : query.contains(COLONNA_ARRAY[colonna], [valore]);
  const { data, error } = await filtrata
    .order('engagement_score', { ascending: false })
    .limit(limite);

  if (error) return [];
  return (data || []) as Post[];
}

/** Quanti record v2 di un segmento sono ancora in classifica. */
export async function contaDi(
  colonna: 'country' | 'category' | 'author_handle',
  valore: string
): Promise<number> {
  const query = supabaseServer
    .from('posts')
    .select('id', { count: 'exact', head: true })
    .eq('method_version', 'v2')
    .eq('status', 'ACTIVE');
  const { count } = colonna === 'author_handle'
    ? await query.eq(colonna, valore)
    : await query.contains(COLONNA_ARRAY[colonna], [valore]);
  return count ?? 0;
}
