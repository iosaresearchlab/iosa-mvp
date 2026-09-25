import Link from 'next/link';
import type { Metadata } from 'next';
import { PageShell } from '@/components/PageShell';
import { supabaseServer } from '@/lib/supabase-server';
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

// Un video presente in piu' fette conta in ciascuna: si leggono gli array
// countries / categories, non la prima fetta (docs/02 §6.1).
async function conteggi(colonna: 'countries' | 'categories'): Promise<Conteggio> {
  const { data } = await supabaseServer
    .from('posts')
    .select(colonna)
    .eq('method_version', 'v2')
    .eq('status', 'ACTIVE');

  const out: Conteggio = {};
  for (const riga of (data || []) as Record<string, string[] | null>[]) {
    for (const v of riga[colonna] || []) out[v] = (out[v] || 0) + 1;
  }
  return out;
}

export default async function Outliers() {
  const [perPaese, perCategoria, { count }] = await Promise.all([
    conteggi('countries'),
    conteggi('categories'),
    supabaseServer
      .from('posts')
      .select('id', { count: 'exact', head: true })
      .eq('method_version', 'v2')
      .eq('status', 'ACTIVE'),
  ]);

  // Il totale e' dei record, non la somma dei paesi: un video in piu' fette
  // la farebbe contare due volte.
  const totale = count ?? 0;

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
