// SOC-W1 (24/10/2026): one Findings story, static, at a URL that never changes.
import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { ArrowLeft, Database, Info } from 'lucide-react';
import { FindingChart } from '@/components/FindingChart';
import { CopyLinkButton } from '@/components/CopyLinkButton';
import { Markdown } from '@/lib/markdown';
import { dataLunga, storia, storiePubblicate } from '@/lib/findings';
import { SITO } from '@/lib/seo';

// Only published stories are built; a draft or an unknown slug is a 404.
export const dynamicParams = false;

export function generateStaticParams() {
  return storiePubblicate().map((m) => ({ slug: m.slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const s = storia(slug);
  if (!s) return {};
  const url = `${SITO}/insights/findings/${slug}`;
  const immagine = { url: `/insights/findings/${slug}/og.png`, width: 1200, height: 630, alt: s.meta.og_title };
  return {
    title: `${s.meta.title} — IOSA Findings`,
    description: s.meta.summary,
    alternates: { canonical: url },
    openGraph: {
      type: 'article',
      siteName: 'IOSA',
      title: s.meta.og_title,
      description: s.meta.summary,
      url,
      publishedTime: s.meta.date,
      images: [immagine],
    },
    twitter: { card: 'summary_large_image', title: s.meta.og_title, description: s.meta.summary, images: [immagine.url] },
    robots: { index: true, follow: true },
  };
}

export default async function FindingPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const s = storia(slug);
  if (!s) notFound();
  const url = `${SITO}/insights/findings/${slug}`;
  return (
    <main className="flex-1 bg-[#030508] text-white">
      <article className="max-w-3xl mx-auto px-4 py-8 space-y-6">
        <Link
          href="/insights/findings"
          className="inline-flex items-center gap-1.5 font-mono text-[11px] text-gray-500 hover:text-[#00E5FF]"
        >
          <ArrowLeft className="w-3 h-3" /> All findings
        </Link>

        <header className="space-y-2">
          <p className="font-mono text-[11px] uppercase tracking-wider text-cyan-300">
            Findings · <time dateTime={s.meta.date}>{dataLunga(s.meta.date)}</time>
          </p>
          <h1 className="text-2xl sm:text-3xl font-black font-mono tracking-tight">{s.meta.title}</h1>
          <p className="text-base text-gray-300 leading-relaxed">{s.meta.summary}</p>
        </header>

        <FindingChart d={s.data} />

        <Markdown testo={s.body} />

        <aside className="bg-black/40 border border-cyan-500/30 rounded-xl p-4 space-y-2 text-sm text-gray-300">
          <h2 className="font-mono text-xs font-bold text-[#00E5FF] flex items-center gap-2">
            <Database className="w-3.5 h-3.5" /> How this was measured
          </h2>
          <p>
            The figures come from our reading of <strong className="text-white">{dataLunga(s.data.reading_date)}</strong>,
            produced by the read-only query <code className="font-mono text-cyan-200">tools/findings/{s.meta.source_sql}</code>,
            committed in the project repository with the figures it produced
            (<code className="font-mono text-cyan-200">{s.meta.chart}</code>).
          </p>
          <p>
            <Link href="/#methodology" className="inline-flex items-center gap-1 text-[#00E5FF] hover:text-cyan-300 underline underline-offset-2">
              <Info className="w-3.5 h-3.5" /> Method
            </Link>
            <span className="text-gray-500"> — how the VPI is measured.</span>
          </p>
        </aside>

        <div className="flex items-center gap-3 pt-2 border-t border-gray-800">
          <span className="font-mono text-[11px] text-gray-500">Share</span>
          <CopyLinkButton url={url} />
        </div>
      </article>
    </main>
  );
}
