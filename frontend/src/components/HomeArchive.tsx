'use client';

/**
 * L'archivio in home, paginato sul server (UI-3, 01/10/2026).
 *
 * Filtri, ordine e pagina stanno nell'URL e nella query; i conteggi dei
 * filtri vengono dal database (home_facets); l'export CSV e' generato dal
 * server sull'intero insieme filtrato (/api/export). Nessuna sottoscrizione
 * realtime: i dati cambiano una volta al giorno.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { createClient } from '@supabase/supabase-js';
import { BarChart3, ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, Download, ExternalLink, Search, X } from 'lucide-react';
import { formatCount, formatVPI } from '@/lib/format';
import { stileBadge } from '@/lib/vpi-scale';
import { PAESI } from '@/lib/segments';
import {
  inClassifica, vpiPubblicato, viewsPubblicate, livelloPubblicato, dataBreve,
} from '@/lib/record-status';
import { StatusBadge } from '@/components/StatusBadge';
import {
  aParametri, applicaFiltri, applicaOrdine, daParametri, pagineVisibili, parametriFacet, pulisci,
  CAMPI_HOME, ORDINI, PAGE_SIZES, VISTE, type StatoArchivio, type Vista,
} from '@/lib/home-query';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL || '',
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || '',
  { auth: { persistSession: false } }
);

type Riga = Record<string, any>;
type Facet = { kind: 'status' | 'country' | 'category'; value: string; n: number };

const ALTEZZA_RIGA = 'h-[84px]';

/** Lo stato dall'URL e il modo di cambiarlo: push per pagine e filtri, replace per la ricerca. */
export function useStatoArchivio() {
  const sp = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const stato = useMemo(() => daParametri(sp), [sp]);
  const cambia = useCallback(
    (delta: Partial<StatoArchivio>, modo: 'push' | 'replace' = 'push') => {
      // ogni cambio che non sia la pagina riporta alla prima pagina
      const nuovo = { ...stato, ...delta, pagina: delta.pagina ?? 1 };
      const qs = aParametri(nuovo).toString();
      const url = `${pathname}${qs ? `?${qs}` : ''}`;
      if (modo === 'replace') router.replace(url, { scroll: false });
      else router.push(url, { scroll: false });
    },
    [stato, router, pathname]
  );
  return { stato, cambia };
}

/** La casella di ricerca: scrive q nell'URL dopo una breve pausa. */
export function SearchBox() {
  const { stato, cambia } = useStatoArchivio();
  const [testo, setTesto] = useState(stato.q);
  const ultimo = useRef(stato.q);
  useEffect(() => { if (stato.q !== ultimo.current) { setTesto(stato.q); ultimo.current = stato.q; } }, [stato.q]);
  useEffect(() => {
    const t = setTimeout(() => {
      const q = pulisci(testo);
      if (q !== stato.q) { ultimo.current = q; cambia({ q }, 'replace'); }
    }, 350);
    return () => clearTimeout(t);
  }, [testo, stato.q, cambia]);
  return (
    <form role="search" onSubmit={(e) => { e.preventDefault(); document.getElementById('directory-table')?.scrollIntoView({ behavior: 'smooth' }); }}
      className="relative flex items-center bg-black/90 border border-cyan-500/50 rounded-xl p-1 shadow-2xl focus-within:border-[#00E5FF] transition-all">
      <Search className="w-4 h-4 text-[#00E5FF] ml-2.5 mr-2 shrink-0" aria-hidden />
      <label htmlFor="ricerca-archivio" className="sr-only">Search a handle, a title or a video link</label>
      <input id="ricerca-archivio" type="search" value={testo} onChange={(e) => setTesto(e.target.value)}
        placeholder="Search handle, title or video link..." autoComplete="off"
        className="w-full bg-transparent text-white placeholder-gray-500 text-xs md:text-sm focus:outline-none font-mono py-1" />
      {testo && (
        <button type="button" onClick={() => setTesto('')} aria-label="Clear the search"
          className="p-1 text-gray-500 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#00E5FF] rounded">
          <X className="w-3.5 h-3.5" />
        </button>
      )}
    </form>
  );
}

function CellaVpi({ post }: { post: Riga }) {
  const livello = livelloPubblicato(post);
  const vpi = vpiPubblicato(post);
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[#00E5FF] font-black text-xs">{vpi === null ? '—' : formatVPI(vpi)}</span>
      <span className="text-[8px] px-1.5 py-0.5 rounded font-bold uppercase border w-fit max-w-[11rem] truncate"
        style={stileBadge(livello.colore)} title={livello.nome}>
        {livello.nome}
      </span>
    </div>
  );
}

function Azioni({ post }: { post: Riga }) {
  return (
    <div className="flex items-center gap-1.5 justify-end">
      <a href={`/claim/${post.claim_token}`}
        className="flex items-center gap-1 bg-[#00E5FF] hover:bg-cyan-400 text-black font-bold text-[10px] px-2 py-1 rounded-lg whitespace-nowrap focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white">
        <BarChart3 className="w-3 h-3" aria-hidden /> Analysis
      </a>
      {post.post_url && (
        <a href={post.post_url} target="_blank" rel="noreferrer" aria-label="Open the video on YouTube"
          className="p-1 text-gray-400 hover:text-white border border-gray-800 rounded-lg focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#00E5FF]">
          <ExternalLink className="w-3 h-3" aria-hidden />
        </a>
      )}
    </div>
  );
}

function Video({ post }: { post: Riga }) {
  return (
    <div className="min-w-0">
      <div className="flex items-center gap-1.5 mb-0.5 flex-wrap">
        <StatusBadge post={post} />
        <span className="text-[8px] px-1.5 rounded bg-cyan-950/60 text-[#00E5FF] border border-cyan-500/30 font-bold truncate max-w-[10rem]">
          {(post.countries || [post.country]).filter(Boolean).join(' ') || 'GLOBAL'}
        </span>
      </div>
      <div className="font-sans font-bold text-xs text-white leading-tight line-clamp-2">{post.content_text || 'Untitled video'}</div>
      <div className="text-[10px] text-gray-400 truncate">
        {post.author_handle || post.author_name} &middot; baseline {post.baseline_score ? formatCount(Number(post.baseline_score)) : '—'}
      </div>
    </div>
  );
}

/** Le colonne dedicate a ciascuna vista (HOME-1). */
function colonne(vista: Vista): { titolo: string; destra?: boolean; cella: (p: Riga) => React.ReactNode }[] {
  if (vista === 'charting') return [
    { titolo: 'Day', cella: (p) => <span className="whitespace-nowrap text-white">day {p.day_n ?? '—'}</span> },
    { titolo: 'Current VPI · level', cella: (p) => <CellaVpi post={p} /> },
    { titolo: 'Views', destra: true, cella: (p) => <span className="text-white">{formatCount(viewsPubblicate(p))}</span> },
    { titolo: 'First observed', cella: (p) => <span className="whitespace-nowrap text-gray-300">{dataBreve(p.entered_on)}</span> },
  ];
  if (vista === 'left') return [
    { titolo: 'Highest VPI observed · level', cella: (p) => <CellaVpi post={p} /> },
    { titolo: 'Views', destra: true, cella: (p) => <span className="text-white">{formatCount(viewsPubblicate(p))}</span> },
    { titolo: 'Days in Most Popular', cella: (p) => <span className="text-white">{p.day_n ?? '—'}</span> },
    { titolo: 'Left on', cella: (p) => <span className="whitespace-nowrap text-gray-300">{dataBreve(p.left_on)}</span> },
    { titolo: 'Claim open until', cella: (p) => <span className="whitespace-nowrap text-gray-300">{vpiPubblicato(p) === null ? 'no plaque (no VPI)' : dataBreve(p.claim_open_until)}</span> },
  ];
  return [
    { titolo: 'Status', cella: (p) => <span className="whitespace-nowrap text-gray-300">{inClassifica(p) ? `since ${dataBreve(p.entered_on)}` : `left ${dataBreve(p.left_on)}`}</span> },
    { titolo: 'VPI · level', cella: (p) => <CellaVpi post={p} /> },
    { titolo: 'Views', destra: true, cella: (p) => <span className="text-white">{formatCount(viewsPubblicate(p))}</span> },
  ];
}

const fmt = (n: number) => n.toLocaleString('en-US');

export default function HomeArchive({ onTotale }: { onTotale?: (n: number, vista: Vista) => void }) {
  const { stato, cambia } = useStatoArchivio();
  const [righe, setRighe] = useState<Riga[]>([]);
  const [totale, setTotale] = useState<number | null>(null);
  const [facet, setFacet] = useState<Facet[]>([]);
  const [caricamento, setCaricamento] = useState(true);
  const [errore, setErrore] = useState<string | null>(null);
  const [salto, setSalto] = useState('');
  const turno = useRef(0);

  const chiave = aParametri(stato).toString();
  // l'export copre l'intero insieme filtrato: niente pagina, niente righe per pagina
  const chiaveExport = aParametri({ ...stato, pagina: 1, perPagina: 50 }).toString();
  useEffect(() => {
    const mio = ++turno.current;
    setCaricamento(true);
    setErrore(null);
    const da = (stato.pagina - 1) * stato.perPagina;
    const query = applicaOrdine(
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      applicaFiltri(supabase.from('public_records').select(CAMPI_HOME, { count: 'exact' }) as any, stato), stato
    ).range(da, da + stato.perPagina - 1);
    Promise.all([query, supabase.rpc('home_facets', parametriFacet(stato))])
      .then(([pagina, faccette]) => {
        if (mio !== turno.current) return;
        if (pagina.error) throw pagina.error;
        setRighe(pagina.data || []);
        setTotale(pagina.count ?? 0);
        setFacet(((faccette.data as Facet[]) || []).map((f) => ({ ...f, n: Number(f.n) })));
      })
      .catch(() => { if (mio === turno.current) setErrore('The index could not be loaded. Try again in a minute.'); })
      .finally(() => { if (mio === turno.current) setCaricamento(false); });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chiave]);

  useEffect(() => { if (totale !== null) onTotale?.(totale, stato.vista); }, [totale, stato.vista, onTotale]);

  const pagine = Math.max(1, Math.ceil((totale ?? 0) / stato.perPagina));
  useEffect(() => {   // una pagina oltre l'ultima (link vecchio, filtro nuovo) torna all'ultima
    if (!caricamento && totale !== null && stato.pagina > pagine) cambia({ pagina: pagine }, 'replace');
  }, [caricamento, totale, pagine, stato.pagina, cambia]);

  const perTipo = (k: Facet['kind']) => facet.filter((f) => f.kind === k).sort((a, b) => b.n - a.n || a.value.localeCompare(b.value));
  const contoVista = (v: Vista) => {
    const s = perTipo('status');
    if (v === 'all') return s.reduce((t, f) => t + f.n, 0);
    return s.find((f) => f.value === (v === 'charting' ? 'ACTIVE' : 'CLOSED'))?.n ?? 0;
  };
  const cols = colonne(stato.vista);
  const primo = totale ? (stato.pagina - 1) * stato.perPagina + 1 : 0;
  const ultimo = Math.min(stato.pagina * stato.perPagina, totale ?? 0);
  const vai = (p: number) => {
    cambia({ pagina: Math.min(Math.max(1, p), pagine) });
    document.getElementById('directory-table')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };
  const ordini = ORDINI.filter((o) => o.viste.includes(stato.vista));
  const pulsante = 'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-[#00E5FF]';

  return (
    <section id="directory-table" aria-labelledby="titolo-archivio" className="bg-[#070A10] border border-gray-800 rounded-xl overflow-hidden shadow-2xl scroll-mt-16">
      <h2 id="titolo-archivio" className="sr-only">The index</h2>

      {/* Vista */}
      <div className="p-2.5 px-3 border-b border-gray-800 font-mono text-xs flex flex-wrap items-center gap-2 bg-black/40" role="group" aria-label="Which records">
        {VISTE.map(({ valore, etichetta }) => (
          <button key={valore} type="button" data-vista={valore} aria-pressed={stato.vista === valore}
            onClick={() => cambia({ vista: valore, ordine: ORDINI.find((o) => o.valore === stato.ordine)!.viste.includes(valore) ? stato.ordine : 'views' })}
            className={`px-2.5 py-1 rounded border text-[11px] cursor-pointer ${pulsante} ${stato.vista === valore ? 'text-black bg-[#00E5FF] border-[#00E5FF] font-bold' : 'text-cyan-300 border-cyan-500/30 bg-cyan-950/40 hover:text-white'}`}>
            {etichetta}{facet.length > 0 && <span className="opacity-70"> ({fmt(contoVista(valore))})</span>}
          </button>
        ))}
      </div>

      {/* Filtri, ordine, righe per pagina, export */}
      <div className="p-2.5 px-3 border-b border-gray-800 font-mono text-[11px] grid grid-cols-2 md:flex md:flex-wrap items-center gap-2">
        <label className="flex items-center gap-1 bg-black/60 border border-gray-800 px-2 py-1 rounded-md col-span-1">
          <span className="text-gray-500">Country</span>
          <select value={stato.paese ?? ''} onChange={(e) => cambia({ paese: e.target.value || null })}
            className={`bg-transparent text-white font-bold min-w-0 w-full cursor-pointer ${pulsante}`}>
            <option value="" className="bg-gray-900">All</option>
            {perTipo('country').map((f) => (
              <option key={f.value} value={f.value} className="bg-gray-900">{PAESI[f.value] ?? f.value} ({fmt(f.n)})</option>
            ))}
            {stato.paese && !perTipo('country').some((f) => f.value === stato.paese) && (
              <option value={stato.paese} className="bg-gray-900">{PAESI[stato.paese] ?? stato.paese} (0)</option>
            )}
          </select>
        </label>
        <label className="flex items-center gap-1 bg-black/60 border border-gray-800 px-2 py-1 rounded-md col-span-1">
          <span className="text-gray-500">Category</span>
          <select value={stato.categoria ?? ''} onChange={(e) => cambia({ categoria: e.target.value || null })}
            className={`bg-transparent text-white font-bold min-w-0 w-full cursor-pointer ${pulsante}`}>
            <option value="" className="bg-gray-900">All</option>
            {perTipo('category').map((f) => (
              <option key={f.value} value={f.value} className="bg-gray-900">{f.value} ({fmt(f.n)})</option>
            ))}
            {stato.categoria && !perTipo('category').some((f) => f.value === stato.categoria) && (
              <option value={stato.categoria} className="bg-gray-900">{stato.categoria} (0)</option>
            )}
          </select>
        </label>
        <label className="flex items-center gap-1 bg-black/60 border border-gray-800 px-2 py-1 rounded-md col-span-1">
          <span className="text-gray-500">Sort</span>
          <select value={stato.ordine} onChange={(e) => cambia({ ordine: e.target.value as StatoArchivio['ordine'] })}
            className={`bg-transparent text-white font-bold min-w-0 w-full cursor-pointer ${pulsante}`}>
            {ordini.map((o) => <option key={o.valore} value={o.valore} className="bg-gray-900">{o.etichetta}</option>)}
          </select>
        </label>
        <label className="flex items-center gap-1 bg-black/60 border border-gray-800 px-2 py-1 rounded-md col-span-1">
          <span className="text-gray-500">Rows</span>
          <select value={stato.perPagina} onChange={(e) => cambia({ perPagina: Number(e.target.value) as StatoArchivio['perPagina'] })}
            className={`bg-transparent text-white font-bold cursor-pointer ${pulsante}`}>
            {PAGE_SIZES.map((n) => <option key={n} value={n} className="bg-gray-900">{n}</option>)}
          </select>
        </label>
        {(stato.paese || stato.categoria || stato.q) && (
          <button type="button" onClick={() => cambia({ paese: null, categoria: null, q: '' })}
            className={`text-cyan-300 hover:text-white underline text-[11px] ${pulsante}`}>
            Clear filters
          </button>
        )}
        <a href={`/api/export${chiaveExport ? `?${chiaveExport}` : ''}`} download data-export-csv
          className={`col-span-2 md:ml-auto flex items-center justify-center gap-1.5 bg-gray-900 hover:bg-gray-800 border border-gray-700 text-cyan-300 hover:text-white px-2.5 py-1 rounded text-[11px] ${pulsante}`}>
          <Download className="w-3 h-3 text-[#00E5FF]" aria-hidden />
          Export CSV {totale !== null ? `(${fmt(totale)} rows)` : ''}
        </a>
      </div>

      <p className="px-3 py-1.5 font-mono text-[11px] text-gray-400 border-b border-gray-800/60" aria-live="polite" data-range>
        {totale === null ? ' ' : totale === 0 ? 'No record matches these filters.'
          : <>{fmt(primo)}&ndash;{fmt(ultimo)} of <strong className="text-white">{fmt(totale)}</strong>{stato.q ? <> for &ldquo;{stato.q}&rdquo;</> : null}</>}
      </p>

      {errore ? (
        <p className="p-8 text-center text-red-400 font-mono text-xs" role="alert">{errore}</p>
      ) : (
        <div className="relative" aria-busy={caricamento}>
          {/* desktop */}
          <table className="hidden md:table w-full table-fixed text-left font-mono text-[11px]" data-home-table={stato.vista}>
            <caption className="sr-only">Records, {VISTE.find((v) => v.valore === stato.vista)?.etichetta}</caption>
            <thead className="bg-black/40 text-[9px] uppercase tracking-wider text-gray-500">
              <tr>
                <th scope="col" className="px-3 py-2 font-bold w-14">#</th>
                <th scope="col" className="px-3 py-2 font-bold w-[38%]">Video</th>
                {cols.map((c) => <th key={c.titolo} scope="col" className={`px-3 py-2 font-bold ${c.destra ? 'text-right' : ''}`}>{c.titolo}</th>)}
                <th scope="col" className="px-3 py-2 w-28"><span className="sr-only">Links</span></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/60">
              {caricamento
                ? Array.from({ length: Math.min(stato.perPagina, righe.length || stato.perPagina) }, (_, i) => (
                    <tr key={`s${i}`} className={ALTEZZA_RIGA} data-skeleton>
                      <td colSpan={cols.length + 3} className="px-3"><div className="h-9 rounded bg-gray-800/40 animate-pulse" /></td>
                    </tr>
                  ))
                : righe.map((post, i) => (
                    <tr key={post.id} className={`${ALTEZZA_RIGA} hover:bg-gray-900/40 align-middle`}>
                      <td className="px-3 text-gray-600 font-bold">#{fmt(primo + i)}</td>
                      <td className="px-3"><Video post={post} /></td>
                      {cols.map((c) => <td key={c.titolo} className={`px-3 ${c.destra ? 'text-right' : ''}`}>{c.cella(post)}</td>)}
                      <td className="px-3"><Azioni post={post} /></td>
                    </tr>
                  ))}
            </tbody>
          </table>
          {/* mobile */}
          <ol className="md:hidden divide-y divide-gray-800/60 font-mono text-[11px]">
            {caricamento
              ? Array.from({ length: Math.min(stato.perPagina, righe.length || stato.perPagina) }, (_, i) => (
                  <li key={`s${i}`} className="p-3 h-[150px]" data-skeleton><div className="h-full rounded bg-gray-800/40 animate-pulse" /></li>
                ))
              : righe.map((post, i) => (
                  <li key={post.id} className="p-3 space-y-2">
                    <div className="flex gap-2">
                      <span className="text-gray-600 font-bold shrink-0">#{fmt(primo + i)}</span>
                      <Video post={post} />
                    </div>
                    <dl className="grid grid-cols-2 gap-x-3 gap-y-1">
                      {cols.map((c) => (
                        <div key={c.titolo} className="min-w-0">
                          <dt className="text-[9px] uppercase text-gray-500">{c.titolo}</dt>
                          <dd>{c.cella(post)}</dd>
                        </div>
                      ))}
                    </dl>
                    <Azioni post={post} />
                  </li>
                ))}
          </ol>
        </div>
      )}

      {/* Paginazione */}
      {totale !== null && totale > 0 && (
        <nav aria-label="Pagination" className="flex flex-wrap items-center justify-between gap-2 px-3 py-3 border-t border-gray-800/60 font-mono text-[11px]">
          <div className="flex items-center gap-1">
            <button type="button" onClick={() => vai(1)} disabled={stato.pagina <= 1} aria-label="First page"
              className={`p-1.5 rounded-lg border border-gray-800 text-gray-300 disabled:opacity-30 hover:border-cyan-500/40 ${pulsante}`}><ChevronsLeft className="w-3.5 h-3.5" aria-hidden /></button>
            <button type="button" onClick={() => vai(stato.pagina - 1)} disabled={stato.pagina <= 1} aria-label="Previous page"
              className={`p-1.5 rounded-lg border border-gray-800 text-gray-300 disabled:opacity-30 hover:border-cyan-500/40 ${pulsante}`}><ChevronLeft className="w-3.5 h-3.5" aria-hidden /></button>
            <ul className="hidden sm:flex items-center gap-1">
              {pagineVisibili(stato.pagina, pagine).map((n, i) => (
                <li key={`${n}-${i}`}>
                  {n === '…' ? <span className="px-1 text-gray-600">…</span> : (
                    <button type="button" onClick={() => vai(n)} aria-current={n === stato.pagina ? 'page' : undefined}
                      aria-label={`Page ${n}`}
                      className={`min-w-[2rem] px-2 py-1 rounded-lg border ${pulsante} ${n === stato.pagina ? 'bg-[#00E5FF] text-black border-[#00E5FF] font-bold' : 'border-gray-800 text-gray-300 hover:border-cyan-500/40'}`}>
                      {n}
                    </button>
                  )}
                </li>
              ))}
            </ul>
            <span className="sm:hidden px-2 text-gray-400">page {stato.pagina} of {fmt(pagine)}</span>
            <button type="button" onClick={() => vai(stato.pagina + 1)} disabled={stato.pagina >= pagine} aria-label="Next page"
              className={`p-1.5 rounded-lg border border-gray-800 text-gray-300 disabled:opacity-30 hover:border-cyan-500/40 ${pulsante}`}><ChevronRight className="w-3.5 h-3.5" aria-hidden /></button>
            <button type="button" onClick={() => vai(pagine)} disabled={stato.pagina >= pagine} aria-label="Last page"
              className={`p-1.5 rounded-lg border border-gray-800 text-gray-300 disabled:opacity-30 hover:border-cyan-500/40 ${pulsante}`}><ChevronsRight className="w-3.5 h-3.5" aria-hidden /></button>
          </div>
          <form className="flex items-center gap-1.5" onSubmit={(e) => { e.preventDefault(); const n = parseInt(salto, 10); if (n) vai(n); setSalto(''); }}>
            <label htmlFor="salta-pagina" className="text-gray-500">Go to page</label>
            <input id="salta-pagina" type="number" inputMode="numeric" min={1} max={pagine} value={salto}
              onChange={(e) => setSalto(e.target.value)} placeholder={String(stato.pagina)}
              className={`w-16 bg-black border border-gray-800 rounded-lg px-2 py-1 text-white ${pulsante}`} />
            <button type="submit" className={`px-2 py-1 rounded-lg border border-gray-800 text-gray-300 hover:border-cyan-500/40 ${pulsante}`}>Go</button>
            <span className="text-gray-500">of {fmt(pagine)}</span>
          </form>
        </nav>
      )}
    </section>
  );
}
