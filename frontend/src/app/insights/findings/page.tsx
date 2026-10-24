// SOC-W1 (24/10/2026): the index of the published Findings stories, newest first.
import Link from 'next/link';
import { PageShell } from '@/components/PageShell';
import { dataLunga, storiePubblicate } from '@/lib/findings';
import { metadatiPagina } from '@/lib/seo';

export const metadata = {
  ...metadatiPagina({
    titolo: 'Findings — IOSA',
    descrizione: 'Short stories from our daily reading of YouTube’s Most Popular charts, each with its figures and the query behind them.',
    percorso: '/insights/findings',
  }),
  // /insights itself is not indexed (its layout, APP-1); the findings are.
  robots: { index: true, follow: true },
};

export default function FindingsIndex() {
  const storie = storiePubblicate();
  return (
    <PageShell
      titolo="Findings"
      sottotitolo="Short stories from our daily reading of YouTube’s Most Popular charts. Each one shows its figures, the day of the reading and the query behind them."
      mostraRitorno={false}
    >
      {storie.length === 0 ? (
        <p className="font-mono text-sm text-gray-500">No findings published yet.</p>
      ) : (
        <ul className="space-y-3">
          {storie.map((m) => (
            <li key={m.slug}>
              <Link
                href={`/insights/findings/${m.slug}`}
                className="block bg-[#070A10] border border-gray-800 hover:border-cyan-500/40 rounded-2xl p-5 transition-colors"
              >
                <p className="font-mono text-[11px] text-gray-500">{dataLunga(m.date)}</p>
                <h2 className="font-mono font-bold text-white text-lg mt-1">{m.title}</h2>
                <p className="text-sm text-gray-400 mt-1">{m.summary}</p>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </PageShell>
  );
}
