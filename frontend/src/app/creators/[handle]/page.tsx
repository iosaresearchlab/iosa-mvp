import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { PageShell } from '@/components/PageShell';
import { OutlierList } from '@/components/OutlierList';
import { outlierDi } from '@/lib/supabase-server';
import { handleDaSlug, SITO } from '@/lib/segments';
import { formatVPI, formatCount } from '@/lib/format';

export const revalidate = 3600;

// Nessuna pagina viene precompilata: sono migliaia e verrebbero costruite
// tutte a ogni deploy. Vengono generate alla prima visita e poi tenute in
// cache per un'ora, che e' esattamente il ritmo con cui un motore di ricerca
// le scopre dalla sitemap.
export const dynamicParams = true;
export function generateStaticParams() {
  return [];
}

/**
 * Una pagina con una sola misurazione non ha abbastanza sostanza per essere
 * proposta a un motore di ricerca: resta raggiungibile dai link del sito ma
 * non viene indicizzata. Solo i creator con piu' di un outlier finiscono
 * nella sitemap.
 */
const MIN_OUTLIER_PER_INDICIZZARE = 2;

export async function generateMetadata({
  params,
}: {
  params: Promise<{ handle: string }>;
}): Promise<Metadata> {
  const { handle } = await params;
  const author = handleDaSlug(handle);
  const posts = await outlierDi('author_handle', author, 50);
  if (posts.length === 0) return { robots: { index: false, follow: false } };

  const migliore = posts[0];
  const indicizzabile = posts.length >= MIN_OUTLIER_PER_INDICIZZARE;

  const titolo = `${author} — viral performance measurements | IOSA`;
  const descrizione = `Independent measurements of ${author}: ${
    posts.length
  } short video${posts.length === 1 ? '' : 's'} that outperformed the channel's own recent median. Best result ${formatVPI(
    migliore.vpi_ratio
  )} — ${formatCount(migliore.engagement_score)} views against a ${formatCount(
    migliore.baseline_score
  )} baseline.`;

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
      images: [{ url: '/og-image.png', width: 1200, height: 630, alt: titolo }],
    },
    twitter: {
      card: 'summary_large_image',
      title: titolo,
      description: descrizione,
      images: ['/og-image.png'],
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
  const posts = await outlierDi('author_handle', author, 50);
  if (posts.length === 0) notFound();

  const migliore = posts[0];
  const paese = posts.find((p) => p.country)?.country;
  const categoria = posts.find((p) => p.category)?.category;

  return (
    <PageShell
      titolo={`${author}`}
      sottotitolo={`IOSA has measured ${posts.length} short video${
        posts.length === 1 ? '' : 's'
      } from this channel currently outperforming its own recent baseline${
        categoria ? ` in ${categoria}` : ''
      }${paese ? ` (${paese})` : ''}. The strongest measurement reached ${formatCount(
        migliore.engagement_score
      )} views against a channel median of ${formatCount(
        migliore.baseline_score
      )}, a VPI of ${formatVPI(
        migliore.vpi_ratio
      )}. These numbers come from the public platform API and compare the channel only with itself.`}
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
          gated and nothing is for sale. If you would rather not appear here at
          all, write to{' '}
          <a
            href="mailto:iosa.research.lab@gmail.com"
            className="text-[#00E5FF] underline"
          >
            iosa.research.lab@gmail.com
          </a>{' '}
          and we remove the channel.
        </p>
      </div>
    </PageShell>
  );
}
