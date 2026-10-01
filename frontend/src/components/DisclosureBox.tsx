'use client';

/**
 * APP-6 (01/10/2026): how to read a VPI level, with the live figures.
 *
 * A video needs absolute views to enter Most Popular, so the VPI it needs
 * depends on the size of its channel: high levels come almost entirely from
 * small-baseline channels. Said with the day-1 median VPI of each baseline
 * band and its n, fed live from the backend cells (/api/analytics/day1-bands),
 * never smoothed and never pooled across bands (docs/01 §4.2, 04, 09).
 */
import { useEffect, useState } from 'react';
import { formatVPI } from '@/lib/format';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

type Cella = { baseline_band: string; format: string; n: number; median_vpi: number | null };
type Risposta = {
  cells: Cella[];
  n: number;
  without_vpi?: { not_computable: number; pending: number };
};

export function DisclosureBox({ compatta = false }: { compatta?: boolean }) {
  const [dati, setDati] = useState<Risposta | null>(null);
  const [errore, setErrore] = useState(false);

  useEffect(() => {
    let annullato = false;
    fetch(`${BACKEND_URL}/api/analytics/day1-bands?format=LONG`)
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((d: Risposta) => { if (!annullato) setDati(d); })
      .catch(() => { if (!annullato) setErrore(true); });
    return () => { annullato = true; };
  }, []);

  const senza = dati?.without_vpi?.not_computable ?? 0;
  const inAttesa = dati?.without_vpi?.pending ?? 0;

  return (
    <section
      data-disclosure-box
      className="border border-amber-500/40 bg-amber-950/20 rounded-xl p-3 px-4 font-sans text-left"
    >
      <h2 className="text-[11px] font-mono font-bold tracking-widest text-amber-300 uppercase mb-1">
        How to read a VPI level
      </h2>
      <p className="text-xs text-amber-100/90 leading-relaxed">
        To enter Most Popular a video needs absolute views, so the VPI it needs depends on the size of its
        channel. Most records come from large channels, where the median VPI is low; the high levels come
        almost entirely from small channels. Below, the median VPI on the first day observed, per channel
        baseline band, long-form videos only.
      </p>
      {errore ? (
        <p className="mt-2 text-[11px] font-mono text-gray-400">The figures could not be loaded. Try again in a minute.</p>
      ) : !dati ? (
        <p className="mt-2 text-[11px] font-mono text-gray-500">Loading the figures…</p>
      ) : (
        <>
          <table className={`mt-2 w-full font-mono ${compatta ? 'text-[10px]' : 'text-[11px]'}`}>
            <thead className="text-gray-400 text-left">
              <tr>
                <th className="py-1 pr-3 font-bold">Channel baseline</th>
                <th className="py-1 pr-3 font-bold text-right">n</th>
                <th className="py-1 font-bold text-right">Median VPI, day 1</th>
              </tr>
            </thead>
            <tbody className="text-white">
              {dati.cells.map((c) => (
                <tr key={c.baseline_band} className="border-t border-amber-500/10">
                  <td className="py-1 pr-3">{c.baseline_band} views</td>
                  <td className="py-1 pr-3 text-right">{c.n.toLocaleString('en-US')}</td>
                  <td className="py-1 text-right text-[#00E5FF] font-bold">{formatVPI(c.median_vpi)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-1 text-[10px] font-mono text-gray-400" data-disclosure-n>
            n = {dati.n.toLocaleString('en-US')} with a VPI
            {senza > 0 ? ` + ${senza.toLocaleString('en-US')} without a computable baseline` : ''}
            {inAttesa > 0 ? ` + ${inAttesa.toLocaleString('en-US')} with the baseline still to be read` : ''}
            {' '}&middot; live from the published series.
          </p>
        </>
      )}
    </section>
  );
}
