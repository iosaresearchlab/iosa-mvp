import Link from 'next/link';
import type { Metadata } from 'next';
import { PageShell } from '@/components/PageShell';
import { supabaseServer, MIN_VPI_DISPLAY } from '@/lib/supabase-server';
import {
  PAESI,
  CATEGORIE,
  slugPaese,
  slugCategoria,
  SITO,
} from '@/lib/segments';

export const revalidate = 3600;

export const metadata: Metadata = {
  title: 'Browse viral outliers by country and category — IOSA',
  description:
    'Every country and content category we measure, with the number of active viral outliers in each. A viral outlier is a video that outperformed the recent median of its own channel, measured within its own format.',
  alternates: { canonical: `${SITO}/outliers` },
};

type Conteggio = Record<string, number>;

async function conteggi(colonna: 'country' | 'category'): Promise<Conteggio> {
  const { data } = await supabaseServer
    .from('posts')
    .select(colonna)
    .eq('status', 'ACTIVE')
    .gte('vpi_ratio', MIN_VPI_DISPLAY);

  const out: Conteggio = {};
  for (const riga of (data || []) as Record<string, string | null>[]) {
    const v = riga[colonna];
    if (v) out[v] = (out[v] || 0) + 1;
  }
  return out;
}

export default async function Outliers() {
  const [perPaese, perCategoria] = await Promise.all([
    conteggi('country'),
    conteggi('category'),
  ]);

  const totale = Object.values(perPaese).reduce((a, b) => a + b, 0);

  const paesi = Object.keys(PAESI)
    .map((c) => ({ codice: c, nome: PAESI[c], n: perPaese[c] || 0 }))
    .filter((p) => p.n > 0)
    .sort((a, b) => b.n - a.n);

  const categorie = CATEGORIE.map((c) => ({ nome: c, n: perCategoria[c] || 0 }))
    .filter((c) => c.n > 0)
    .sort((a, b) => b.n - a.n);

  return (
    <PageShell
      mostraRitorno={false}
      titolo="Browse viral outliers"
      sottotitolo={`We are currently tracking ${totale.toLocaleString(
        'en-US'
      )} active outliers across ${paesi.length} countries and ${
        categorie.length
      } categories. An outlier is a video whose view count is well above the median of the recent videos of the same format published by the same channel — so a small creator who breaks out counts as much as a large one.`}
    >
      <section className="mb-10">
        <h2 className="font-mono font-bold text-sm text-[#00E5FF] mb-3 uppercase tracking-wider">
          By country
        </h2>
        <ul className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
          {paesi.map((p) => (
            <li key={p.codice}>
              <Link
                href={`/outliers/${slugPaese(p.codice)}`}
                className="flex items-center justify-between gap-2 px-3 py-2 rounded-lg border border-gray-800 hover:border-cyan-500/40 hover:bg-gray-900/40 transition-colors"
              >
                <span className="font-bold text-xs truncate">{p.nome}</span>
                <span className="font-mono text-[10px] text-gray-500 shrink-0">
                  {p.n.toLocaleString('en-US')}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2 className="font-mono font-bold text-sm text-[#00E5FF] mb-3 uppercase tracking-wider">
          By category
        </h2>
        <ul className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
          {categorie.map((c) => (
            <li key={c.nome}>
              <Link
                href={`/categories/${slugCategoria(c.nome)}`}
                className="flex items-center justify-between gap-2 px-3 py-2 rounded-lg border border-gray-800 hover:border-cyan-500/40 hover:bg-gray-900/40 transition-colors"
              >
                <span className="font-bold text-xs truncate">{c.nome}</span>
                <span className="font-mono text-[10px] text-gray-500 shrink-0">
                  {c.n.toLocaleString('en-US')}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </PageShell>
  );
}
