'use client';

// Classifica per VPI, ricostruita secondo docs/02 §6.3.
//
// La classifica legge post_daily a day_index = 1 (via /api/analytics/top10):
// il primo giorno osservato e' l'unica lettura che ogni record ha. Nessun
// selettore del giorno: dal giorno 2 in poi la classifica si restringerebbe
// da sola ai video rimasti abbastanza a lungo. La tabella del picco e' a
// parte ed e' etichettata come "valori piu' alti osservati", mai come
// "i video migliori": quell'ordine dipende da quanto a lungo e' stato misurato
// ciascun video.

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { createClient } from '@supabase/supabase-js';
import { ArrowLeft, Trophy, ExternalLink } from 'lucide-react';
import { formatVPI, formatCount } from '@/lib/format';
import { PAESI, CATEGORIE } from '@/lib/segments';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL || '',
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || ''
);

type Periodo = 'today' | '7d' | '30d' | 'all';
const PERIODI: { valore: Periodo; etichetta: string; giorni: number | null }[] = [
  { valore: 'today', etichetta: 'Today', giorni: 0 },
  { valore: '7d', etichetta: '7 days', giorni: 7 },
  { valore: '30d', etichetta: '30 days', giorni: 30 },
  { valore: 'all', etichetta: 'All', giorni: null },
];

type Riga = {
  id: string;
  author_handle: string | null;
  author_name: string | null;
  content_text: string | null;
  post_url: string | null;
  format: string | null;
  countries: string[] | null;
  claim_token: string | null;
  age_at_first_obs_days: number | null;
  entered_on: string | null;
  vpi_day1: number;
  views_day1: number | string;
  baseline_band: string | null;
};

type Risposta = {
  n: number;
  label?: string;
  age_at_first_obs_days?: { min: number | null; median: number | null; max: number | null };
  top10: Riga[];
};

type Picco = {
  id: string;
  author_handle: string | null;
  content_text: string | null;
  format: string | null;
  claim_token: string | null;
  vpi_max: number | string | null;
  views_max: number | string | null;
  days_charting: number | null;
  entered_on: string | null;
};

function dataDa(giorni: number | null): string | null {
  if (giorni === null) return null;
  const d = new Date();
  d.setUTCDate(d.getUTCDate() - giorni);
  return d.toISOString().slice(0, 10);
}

export default function LeaderboardPage() {
  const [periodo, setPeriodo] = useState<Periodo>('7d');
  const [formato, setFormato] = useState<'ALL' | 'SHORT' | 'LONG'>('ALL');
  const [paese, setPaese] = useState<string>('ALL');
  const [categoria, setCategoria] = useState<string>('ALL');
  const [risposta, setRisposta] = useState<Risposta | null>(null);
  const [picchi, setPicchi] = useState<Picco[]>([]);
  const [errore, setErrore] = useState<string | null>(null);
  const [caricamento, setCaricamento] = useState(true);

  useEffect(() => {
    document.title = 'IOSA — Top VPI, first day observed';
  }, []);

  useEffect(() => {
    let annullato = false;
    async function carica() {
      setCaricamento(true);
      setErrore(null);
      try {
        const params = new URLSearchParams({ timeframe: periodo, limit: '10' });
        if (formato !== 'ALL') params.set('format', formato);
        if (paese !== 'ALL') params.set('country', paese);
        if (categoria !== 'ALL') params.set('category', categoria);
        const res = await fetch(`${BACKEND_URL}/api/analytics/top10?${params.toString()}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const dati: Risposta = await res.json();

        const giorni = PERIODI.find((p) => p.valore === periodo)?.giorni ?? null;
        let q = supabase
          .from('posts')
          .select('id,author_handle,content_text,format,claim_token,vpi_max,views_max,days_charting,entered_on')
          .eq('method_version', 'v2')
          .not('vpi_max', 'is', null);
        const da = dataDa(giorni);
        if (da) q = q.gte('entered_on', da);
        if (formato !== 'ALL') q = q.eq('format', formato);
        if (paese !== 'ALL') q = q.contains('countries', [paese]);
        if (categoria !== 'ALL') q = q.contains('categories', [categoria]);
        const { data: picco } = await q.order('vpi_max', { ascending: false }).limit(10);

        if (!annullato) {
          setRisposta(dati);
          setPicchi((picco || []) as Picco[]);
        }
      } catch {
        if (!annullato) setErrore('The ranking could not be loaded. Try again in a minute.');
      } finally {
        if (!annullato) setCaricamento(false);
      }
    }
    carica();
    return () => {
      annullato = true;
    };
  }, [periodo, formato, paese, categoria]);

  const eta = risposta?.age_at_first_obs_days;

  return (
    <main className="min-h-screen bg-[#030508] text-white font-sans px-3 md:px-8 py-6">
      <div className="max-w-5xl mx-auto space-y-5">
        <Link href="/" className="inline-flex items-center gap-1.5 text-xs font-mono text-cyan-300 hover:text-white">
          <ArrowLeft className="w-3.5 h-3.5" /> Back to the index
        </Link>

        <header className="space-y-1">
          <h1 className="text-xl md:text-2xl font-black font-mono tracking-tight flex items-center gap-2">
            <Trophy className="w-5 h-5 text-[#00E5FF]" /> Top VPI — first day observed
          </h1>
          <p className="text-xs text-gray-400">
            VPI on the first day observed in Most Popular. Not age-adjusted.
          </p>
        </header>

        <section className="flex flex-wrap items-center gap-2 font-mono text-[11px]">
          <div className="flex bg-black border border-gray-800 rounded-lg overflow-hidden">
            {PERIODI.map((p) => (
              <button
                key={p.valore}
                onClick={() => setPeriodo(p.valore)}
                className={`px-3 py-1.5 cursor-pointer ${periodo === p.valore ? 'bg-[#00E5FF] text-black font-bold' : 'text-gray-300 hover:text-white'}`}
              >
                {p.etichetta}
              </button>
            ))}
          </div>
          <select value={formato} onChange={(e) => setFormato(e.target.value as 'ALL' | 'SHORT' | 'LONG')}
            className="bg-black border border-gray-800 rounded-lg px-2 py-1.5 text-gray-200">
            <option value="ALL">Shorts and long-form</option>
            <option value="SHORT">Shorts</option>
            <option value="LONG">Long-form</option>
          </select>
          <select value={paese} onChange={(e) => setPaese(e.target.value)}
            className="bg-black border border-gray-800 rounded-lg px-2 py-1.5 text-gray-200">
            <option value="ALL">All 34 countries</option>
            {Object.entries(PAESI).map(([codice, nome]) => (
              <option key={codice} value={codice}>{nome}</option>
            ))}
          </select>
          <select value={categoria} onChange={(e) => setCategoria(e.target.value)}
            className="bg-black border border-gray-800 rounded-lg px-2 py-1.5 text-gray-200">
            <option value="ALL">All categories</option>
            {CATEGORIE.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </section>

        <section className="bg-[#070A10] border border-gray-800 rounded-xl overflow-hidden">
          <div className="px-3 py-2 border-b border-gray-800 font-mono text-[11px] text-gray-400 flex flex-wrap gap-x-4 gap-y-1">
            <span>n = <strong className="text-white">{risposta?.n ?? 0}</strong> videos with a VPI on their first day</span>
            <span>
              age at first observation:{' '}
              <strong className="text-white">
                {eta && eta.min !== null ? `${eta.min}–${eta.max} days` : '—'}
              </strong>
            </span>
          </div>
          {caricamento ? (
            <p className="p-6 text-center text-xs font-mono text-gray-500">Loading…</p>
          ) : errore ? (
            <p className="p-6 text-center text-xs font-mono text-red-400">{errore}</p>
          ) : !risposta || risposta.top10.length === 0 ? (
            <p className="p-6 text-center text-xs font-mono text-gray-500">
              No first-day readings in this period yet.
            </p>
          ) : (
            <ol className="divide-y divide-gray-800/60">
              {risposta.top10.map((r, i) => (
                <li key={r.id} className="p-3 flex items-center justify-between gap-3">
                  <div className="flex items-center gap-3 min-w-0">
                    <span className="w-6 text-right font-mono text-gray-500 text-xs">{i + 1}</span>
                    <span className="w-16 shrink-0 text-center font-mono font-black text-sm text-[#00E5FF]">
                      {formatVPI(r.vpi_day1)}
                    </span>
                    <div className="min-w-0">
                      <p className="text-xs font-bold truncate">{r.content_text || 'Untitled video'}</p>
                      <p className="text-[10px] font-mono text-gray-400 truncate">
                        {r.author_handle || r.author_name} · {r.format === 'LONG' ? 'Long-form' : 'Short'} ·
                        {' '}baseline {r.baseline_band ?? '—'} · {formatCount(r.views_day1)} views on day 1 ·
                        {' '}{r.age_at_first_obs_days ?? '—'} days old when first observed
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    {r.claim_token && (
                      <Link href={`/claim/${r.claim_token}`}
                        className="text-[10px] font-mono font-bold bg-[#00E5FF] text-black px-2 py-1 rounded">
                        Plaque
                      </Link>
                    )}
                    {r.post_url && (
                      <a href={r.post_url} target="_blank" rel="noreferrer"
                        className="p-1 text-gray-400 hover:text-white border border-gray-800 rounded">
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    )}
                  </div>
                </li>
              ))}
            </ol>
          )}
        </section>

        <section className="bg-[#070A10] border border-gray-800 rounded-xl overflow-hidden">
          <div className="px-3 py-2 border-b border-gray-800">
            <h2 className="text-sm font-black font-mono">Highest values observed</h2>
            <p className="text-[11px] text-gray-400">
              Peak VPI reached while in Most Popular. Not a ranking of the best-performing
              videos: a video measured for longer has had more days to reach a peak.
            </p>
          </div>
          {picchi.length === 0 ? (
            <p className="p-6 text-center text-xs font-mono text-gray-500">No values observed in this period yet.</p>
          ) : (
            <ol className="divide-y divide-gray-800/60">
              {picchi.map((p) => (
                <li key={p.id} className="p-3 flex items-center gap-3 text-xs">
                  <span className="w-16 shrink-0 text-center font-mono font-black text-[#00E5FF]">{formatVPI(p.vpi_max)}</span>
                  <span className="min-w-0 truncate">{p.content_text || 'Untitled video'}</span>
                  <span className="ml-auto shrink-0 font-mono text-[10px] text-gray-400">
                    {p.author_handle} · {formatCount(p.views_max)} views · {p.days_charting ?? 1} days in Most Popular
                  </span>
                </li>
              ))}
            </ol>
          )}
        </section>
      </div>
    </main>
  );
}
