/**
 * Lo stato dell'archivio in home e la query che lo serve (UI-3, 01/10/2026).
 *
 * Prima la home caricava al massimo 5.000 righe e filtrava nel browser: oltre
 * quel tetto i record sparivano senza avviso, e con loro i conteggi dei filtri
 * e l'export. Ora filtri, ordine e pagina stanno nella query e i conteggi li
 * da' il database. Lo stato vive nell'URL: un link condiviso riapre la stessa
 * pagina, il tasto indietro torna alla precedente.
 *
 * Nessun ordine per VPI: ordinare l'insieme misto per VPI ordinerebbe per
 * quanto a lungo e' stato misurato ciascun video (docs/02 §6.2); la classifica
 * per VPI e' Top VPI, al primo giorno osservato.
 */
import { SERIES_FLOOR } from '@/lib/index-start';

export type Vista = 'charting' | 'left' | 'all';
export type Ordine = 'views' | 'first_observed' | 'first_observed_oldest' | 'left_on' | 'days'
  | 'vpi_desc' | 'vpi_asc';
export const PAGE_SIZES = [25, 50, 100] as const;
export type PerPagina = (typeof PAGE_SIZES)[number];

export type StatoArchivio = {
  vista: Vista;
  paese: string | null;
  categoria: string | null;
  q: string;
  /** UI-8: one baseline band (BANDE), or null. */
  banda: string | null;
  ordine: Ordine;
  pagina: number;
  perPagina: PerPagina;
};

export const DEFAULT: StatoArchivio = {
  // UI-6 (owner, 01/10/2026): the archive opens on All; ?view=charting / ?view=left narrow it
  vista: 'all', paese: null, categoria: null, q: '', banda: null, ordine: 'views', pagina: 1, perPagina: 50,
};

export const VISTE: { valore: Vista; etichetta: string }[] = [
  { valore: 'charting', etichetta: 'In Most Popular now' },
  { valore: 'left', etichetta: 'Left Most Popular' },
  { valore: 'all', etichetta: 'All' },
];

/**
 * Le bande della baseline, le stesse del riquadro "How to read a VPI level" e
 * di backend/main.py BASELINE_BANDS. UI-8 (titolare, 01/10/2026): il VPI si
 * ordina solo dentro una banda; fra bande diverse non e' confrontabile.
 */
export const BANDE: { valore: string; etichetta: string; da: number; a: number | null }[] = [
  { valore: '<100', etichetta: '<100 views', da: 0, a: 100 },
  { valore: '100-1k', etichetta: '100-1k views', da: 100, a: 1_000 },
  { valore: '1k-10k', etichetta: '1k-10k views', da: 1_000, a: 10_000 },
  { valore: '10k-100k', etichetta: '10k-100k views', da: 10_000, a: 100_000 },
  { valore: '>=100k', etichetta: '>=100k views', da: 100_000, a: null },
];

export const ORDINI: { valore: Ordine; etichetta: string; viste: Vista[]; soloInBanda?: boolean }[] = [
  { valore: 'views', etichetta: 'Views', viste: ['charting', 'left', 'all'] },
  { valore: 'first_observed', etichetta: 'First observed (newest)', viste: ['charting', 'left', 'all'] },
  { valore: 'first_observed_oldest', etichetta: 'First observed (oldest)', viste: ['charting', 'left', 'all'] },
  { valore: 'left_on', etichetta: 'Left on (newest)', viste: ['left'] },
  { valore: 'days', etichetta: 'Days in Most Popular', viste: ['charting', 'left'] },
  // current VPI while charting, highest VPI observed after: the column public_records.vpi_shown
  { valore: 'vpi_desc', etichetta: 'VPI (high to low)', viste: ['charting', 'left', 'all'], soloInBanda: true },
  { valore: 'vpi_asc', etichetta: 'VPI (low to high)', viste: ['charting', 'left', 'all'], soloInBanda: true },
];

export const SUGGERIMENTO_VPI = 'VPI is compared only within a baseline band';

/** Un ordine e' ammesso nella vista e, se e' per VPI, solo con una banda scelta. */
export function ordineAmmesso(o: Ordine, vista: Vista, banda: string | null): boolean {
  const def = ORDINI.find((x) => x.valore === o);
  return !!def && def.viste.includes(vista) && (!def.soloInBanda || !!banda);
}

export const STATUS_DI: Record<Vista, string | null> = { charting: 'ACTIVE', left: 'CLOSED', all: null };

export const CAMPI_HOME =
  'id,external_post_id,platform,format,author_handle,author_name,channel_id,content_text,post_url,' +
  'country,category,countries,categories,engagement_score,baseline_score,baseline_rule,vpi_ratio,' +
  'vpi_level,vpi_max,vpi_shown,views_max,days_charting,day_n,claim_open_until,entered_on,left_on,status,claim_token';

const VISTE_VALIDE = new Set<string>(VISTE.map((v) => v.valore));
const ORDINI_VALIDI = new Set<string>(ORDINI.map((o) => o.valore));

/** Stato dai parametri dell'URL; ogni valore non valido torna al default. */
export function daParametri(sp: URLSearchParams | { get(k: string): string | null }): StatoArchivio {
  const vista = (VISTE_VALIDE.has(sp.get('view') ?? '') ? sp.get('view') : DEFAULT.vista) as Vista;
  let ordine = (ORDINI_VALIDI.has(sp.get('sort') ?? '') ? sp.get('sort') : DEFAULT.ordine) as Ordine;
  const banda = BANDE.some((b) => b.valore === sp.get('band')) ? sp.get('band') : null;
  if (!ordineAmmesso(ordine, vista, banda)) ordine = 'views';
  const per = Number(sp.get('per'));
  const pagina = Math.max(1, Math.floor(Number(sp.get('page')) || 1));
  return {
    vista,
    paese: (sp.get('country') || '').toUpperCase().replace(/[^A-Z]/g, '').slice(0, 2) || null,
    categoria: (sp.get('category') || '').slice(0, 40) || null,
    q: pulisci(sp.get('q') || ''),
    banda,
    ordine,
    pagina,
    perPagina: (PAGE_SIZES as readonly number[]).includes(per) ? (per as PerPagina) : DEFAULT.perPagina,
  };
}

/** Parametri dell'URL dallo stato; i default non compaiono, cosi' i link restano corti. */
export function aParametri(s: StatoArchivio): URLSearchParams {
  const p = new URLSearchParams();
  if (s.vista !== DEFAULT.vista) p.set('view', s.vista);
  if (s.paese) p.set('country', s.paese);
  if (s.categoria) p.set('category', s.categoria);
  if (s.q) p.set('q', s.q);
  if (s.banda) p.set('band', s.banda);
  if (s.ordine !== DEFAULT.ordine) p.set('sort', s.ordine);
  if (s.perPagina !== DEFAULT.perPagina) p.set('per', String(s.perPagina));
  if (s.pagina > 1) p.set('page', String(s.pagina));
  return p;
}

/** Testo di ricerca sicuro per i filtri di PostgREST: niente separatori ne' jolly. */
export function pulisci(q: string): string {
  return q.replace(/[,()*%\\"'`]/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 80);
}

/** L'id di un video YouTube se la ricerca e' un link (watch, youtu.be, shorts, live). */
export function idVideo(q: string): string | null {
  const m = q.match(/(?:youtube\.com\/(?:watch\?(?:.*&)?v=|shorts\/|live\/)|youtu\.be\/)([A-Za-z0-9_-]{11})/);
  return m ? m[1] : null;
}

type Filtrabile<Q> = {
  eq(col: string, v: unknown): Q;
  gte(col: string, v: unknown): Q;
  lt(col: string, v: unknown): Q;
  contains(col: string, v: unknown): Q;
  ilike(col: string, pattern: string): Q;
};

/** Applica i filtri dello stato a una query PostgREST su public_records. */
export function applicaFiltri<Q extends Filtrabile<Q>>(query: Q, s: StatoArchivio): Q {
  let q = query.eq('method_version', 'v2').gte('entered_on', SERIES_FLOOR);
  const status = STATUS_DI[s.vista];
  if (status) q = q.eq('status', status);
  if (s.paese) q = q.contains('countries', [s.paese]);
  if (s.categoria) q = q.contains('categories', [s.categoria]);
  const banda = BANDE.find((b) => b.valore === s.banda);
  if (banda) {
    q = q.gte('baseline_score', banda.da);
    if (banda.a !== null) q = q.lt('baseline_score', banda.a);
  }
  const video = s.q ? idVideo(s.q) : null;
  if (video) q = q.eq('external_post_id', video);
  else if (s.q) {
    // search_text = handle, channel name and title in one column of the view,
    // the same expression home_facets matches (a video link goes by its id)
    q = q.ilike('search_text', `*${s.q}*`);
  }
  return q;
}

type Ordinabile<Q> = { order(col: string, o: { ascending: boolean; nullsFirst?: boolean }): Q };

/** L'ordine dello stato, sempre con id in coda: le pagine non si sovrappongono. */
export function applicaOrdine<Q extends Ordinabile<Q>>(query: Q, s: StatoArchivio): Q {
  const giu = { ascending: false, nullsFirst: false };
  let q = query;
  if (s.ordine === 'first_observed') q = q.order('entered_on', giu).order('engagement_score', giu);
  else if (s.ordine === 'first_observed_oldest') q = q.order('entered_on', { ascending: true }).order('engagement_score', giu);
  else if ((s.ordine === 'vpi_desc' || s.ordine === 'vpi_asc') && s.banda)
    q = q.order('vpi_shown', { ascending: s.ordine === 'vpi_asc', nullsFirst: false }).order('engagement_score', giu);
  else if (s.ordine === 'left_on') q = q.order('left_on', giu).order('engagement_score', giu);
  else if (s.ordine === 'days') q = q.order('day_n', giu).order('engagement_score', giu);
  else q = q.order('engagement_score', giu);
  return q.order('id', { ascending: true });
}

/** I parametri della funzione archive_facets per lo stato. */
export function parametriFacet(s: StatoArchivio) {
  const video = s.q ? idVideo(s.q) : null;
  const banda = BANDE.find((b) => b.valore === s.banda);
  return {
    p_band_lo: banda ? banda.da : null,
    p_band_hi: banda ? banda.a : null,
    p_floor: SERIES_FLOOR,
    p_status: STATUS_DI[s.vista],
    p_country: s.paese,
    p_category: s.categoria,
    p_q: video ? null : s.q || null,
    p_video: video,
  };
}

/** Le pagine da numerare attorno a quella corrente: 1 … 4 5 [6] 7 8 … 40. */
export function pagineVisibili(corrente: number, totale: number): (number | '…')[] {
  if (totale <= 7) return Array.from({ length: totale }, (_, i) => i + 1);
  const set = new Set([1, totale, corrente - 1, corrente, corrente + 1]);
  if (corrente <= 3) [2, 3, 4].forEach((n) => set.add(n));
  if (corrente >= totale - 2) [totale - 3, totale - 2, totale - 1].forEach((n) => set.add(n));
  const ordinate = [...set].filter((n) => n >= 1 && n <= totale).sort((a, b) => a - b);
  const out: (number | '…')[] = [];
  ordinate.forEach((n, i) => {
    if (i > 0 && n - ordinate[i - 1] > 1) out.push('…');
    out.push(n);
  });
  return out;
}

/** CSV: intestazione e una riga per record, con le virgolette raddoppiate. */
export const COLONNE_CSV = [
  'Rank', 'Status', 'Format', 'Countries', 'Categories', 'Creator handle', 'Title', 'Views',
  'Baseline', 'Baseline rule', 'Current VPI', 'Highest VPI observed', 'Days in Most Popular',
  'First observed', 'Left on', 'Claim open until', 'Video URL',
];

type RigaCsv = Record<string, unknown>;

export function rigaCsv(r: RigaCsv, rank: number): string {
  const charting = r.status !== 'CLOSED';
  const celle = [
    rank, charting ? 'In Most Popular' : 'Left Most Popular', r.format,
    ((r.countries as string[]) || []).join(' '), ((r.categories as string[]) || []).join(' | '),
    r.author_handle, r.content_text, r.engagement_score, r.baseline_score, r.baseline_rule,
    charting ? r.vpi_ratio : '', r.vpi_max, r.day_n, r.entered_on, r.left_on,
    r.vpi_max === null || r.vpi_max === undefined ? '' : r.claim_open_until, r.post_url,
  ];
  return celle.map((c) => {
    const t = c === null || c === undefined ? '' : String(c);
    return /[",\n\r]/.test(t) ? `"${t.replace(/"/g, '""')}"` : t;
  }).join(',');
}
