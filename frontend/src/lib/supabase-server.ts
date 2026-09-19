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

/** Soglia di ingresso nelle pagine pubbliche, allineata alla home. */
export const MIN_VPI_DISPLAY = 1.4;

export type Post = {
  id: string;
  external_post_id: string | null;
  author_handle: string | null;
  /** Identificatore stabile del canale. Null solo sui record antecedenti al backfill. */
  channel_id: string | null;
  /** Handle reale del canale (customUrl). author_handle lo rispecchia quando c'e'. */
  channel_handle: string | null;
  author_name: string | null;
  content_text: string | null;
  post_url: string | null;
  country: string | null;
  category: string | null;
  platform: string | null;
  vpi_ratio: number | string;
  vpi_level: number;
  vpi_level_name: string | null;
  baseline_score: number | string;
  engagement_score: number | string;
  claim_token: string | null;
  detected_at: string | null;
};

const CAMPI =
  'id,external_post_id,author_handle,channel_id,channel_handle,author_name,content_text,post_url,country,category,platform,vpi_ratio,vpi_level,vpi_level_name,baseline_score,engagement_score,claim_token,detected_at';

/** Outlier attivi di un segmento, dal piu' alto al piu' basso. */
export async function outlierDi(
  colonna: 'country' | 'category' | 'author_handle',
  valore: string,
  limite = 60
): Promise<Post[]> {
  const { data, error } = await supabaseServer
    .from('posts')
    .select(CAMPI)
    .eq('status', 'ACTIVE')
    .eq(colonna, valore)
    .gte('vpi_ratio', MIN_VPI_DISPLAY)
    .order('vpi_ratio', { ascending: false })
    .limit(limite);

  if (error) return [];
  return (data || []) as Post[];
}

/** Conteggio degli outlier attivi di un segmento. */
export async function contaDi(
  colonna: 'country' | 'category' | 'author_handle',
  valore: string
): Promise<number> {
  const { count } = await supabaseServer
    .from('posts')
    .select('id', { count: 'exact', head: true })
    .eq('status', 'ACTIVE')
    .eq(colonna, valore)
    .gte('vpi_ratio', MIN_VPI_DISPLAY);
  return count ?? 0;
}
