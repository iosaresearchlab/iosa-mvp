import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { PageShell } from '@/components/PageShell';
import { OutlierList } from '@/components/OutlierList';
import { recordDelCreator } from '@/lib/supabase-server';
import { handleDaSlug, SITO } from '@/lib/segments';

// OPS-4 (30/10/2026): no ISR. Creator pages were 3.4K of the ~3.8K ISR write units of
// 12 h (Vercel Observability, 29-30/10), one write per path a crawler reaches (Googlebot,
// PetalBot, OAI-SearchBot), and the team stood at 292K ISR writes in 30 days against the
// Hobby 200K (FIX-1d had already cut 1 h -> 24 h). The page is rendered per request and
// kept by Vercel's CDN for the same 24 h (Vercel-CDN-Cache-Control, next.config.ts): the
// same page, the same age at most, and the CDN cache counts no ISR write. A 500 is never
// kept (Vercel caches only 200/404/410/redirects); stale-if-error serves the last good page.
export const dynamic = 'force-dynamic';

/**
 * Una pagina con una sola misurazione non ha abbastanza sostanza per essere
 * proposta a un motore di ricerca: resta raggiungibile dai link del sito ma
 * non viene indicizzata. Solo i creator con piu' di un record finiscono
 * nella sitemap. I record usciti da Most Popular contano (APP-8).
 */
const MIN_OUTLIER_PER_INDICIZZARE = 2;

export async function generateMetadata({
  params,
}: {
  params: Promise<{ handle: string }>;
}): Promise<Metadata> {
  const { handle } = await params;
  const author = handleDaSlug(handle);
  const posts = await recordDelCreator(author);
  if (posts.length === 0) return { robots: { index: false, follow: false } };

  const indicizzabile = posts.length >= MIN_OUTLIER_PER_INDICIZZARE;

  const titolo = `${author} — VPI measurements | IOSA`;
  const descrizione = `Independent measurements of ${author}: ${posts.length} long-form video${
    posts.length === 1 ? '' : 's'
  } first observed in Most Popular, in the charts now or since left, each with its views and its VPI against the channel's own median.`;

  return {
    title: titolo,
    description: descrizione,
    alternates: { canonical: `${SITO}/creators/${handle}` },
    openGraph: {
      type: 'website',
      siteName: 'IOSA',
      title: titolo,
      description: descrizione,
      url: `${SITO}/creators/${handle}`,
    },
    twitter: {
      card: 'summary_large_image',
      title: titolo,
      description: descrizione,
    },
    robots: indicizzabile ? undefined : { index: false, follow: true },
  };
}

export default async function PaginaCreator({
  params,
}: {
  params: Promise<{ handle: string }>;
}) {
  const { handle } = await params;
  const author = handleDaSlug(handle);
  const posts = await recordDelCreator(author);
  if (posts.length === 0) notFound();

  const paese = posts.find((p) => p.country)?.country;
  const categoria = posts.find((p) => p.category)?.category;

  return (
    <PageShell
      titolo={`${author}`}
      sottotitolo={`${posts.length} long-form video${
        posts.length === 1 ? '' : 's'
      } from this channel first observed in Most Popular, still charting or since left${
        categoria ? ` (${categoria}` : ''
      }${paese ? `${categoria ? ', ' : ' ('}${paese}` : ''}${categoria || paese ? ')' : ''}. Each one is measured against the median of the same channel's long-form videos published 7-90 days before it. The figures come from the official YouTube API and compare the channel only with itself.`}
    >
      <div className="rounded-xl border border-gray-800 bg-gray-950/40 overflow-hidden">
        <OutlierList posts={posts} mostraCreator={false} />
      </div>

      <div className="mt-6 rounded-xl border border-cyan-500/20 bg-cyan-950/10 p-4">
        <h2 className="font-mono font-bold text-xs text-[#00E5FF] uppercase tracking-wider mb-2">
          Is this your channel?
        </h2>
        <p className="text-sm text-gray-300 leading-relaxed">
          Every measurement above has its own analysis page with the full
          breakdown, and a free digital plaque you can download. Nothing is
          gated and nothing is for sale. If you would rather not appear here,
          write to{' '}
          <a
            href="mailto:iosa.research.lab@gmail.com"
            className="text-[#00E5FF] underline"
          >
            iosa.research.lab@gmail.com
          </a>{' '}
          and your records are hidden from public pages. They are never
          deleted: the index is a research series and stays complete.
        </p>
      </div>
    </PageShell>
  );
}
