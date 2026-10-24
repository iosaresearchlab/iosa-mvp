// SOC-W1 (24/10/2026): /insights is a server page so the Findings block (newest
// first, at most 5, from the repository at build time) sits above the stats,
// which the client part still reads from the analytics API.
import Link from 'next/link';
import { ArrowRight, BookOpen } from 'lucide-react';
import InsightsClient from '@/components/InsightsClient';
import { dataLunga, storiePubblicate } from '@/lib/findings';

const MASSIMO = 5;

function BloccoFindings() {
  const storie = storiePubblicate();
  if (!storie.length) return null; // drafts are never linked
  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between pb-1 border-b border-gray-800/80">
        <h2 className="text-sm sm:text-base font-bold font-mono text-white flex items-center gap-2">
          <BookOpen className="w-4 h-4 text-[#00E5FF]" />
          <span>Findings</span>
        </h2>
        <Link href="/insights/findings" className="font-mono text-[11px] text-gray-400 hover:text-[#00E5FF] inline-flex items-center gap-1">
          All findings <ArrowRight className="w-3 h-3" />
        </Link>
      </div>
      <ul className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {storie.slice(0, MASSIMO).map((m) => (
          <li key={m.slug}>
            <Link
              href={`/insights/findings/${m.slug}`}
              className="block h-full bg-[#070A10] border border-gray-800 hover:border-cyan-500/40 rounded-2xl p-4 transition-colors"
            >
              <p className="font-mono text-[10px] text-gray-500">{dataLunga(m.date)}</p>
              <h3 className="font-mono font-bold text-white text-sm mt-1">{m.title}</h3>
              <p className="text-xs text-gray-400 mt-1">{m.summary}</p>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

export default function InsightsPage() {
  return <InsightsClient findings={<BloccoFindings />} />;
}
