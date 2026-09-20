import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { PageShell } from '@/components/PageShell';
import { OutlierList } from '@/components/OutlierList';
import { outlierDi, contaDi } from '@/lib/supabase-server';
import { PAESI, slugPaese, paeseDaSlug, SITO } from '@/lib/segments';
import { formatVPI, formatCount } from '@/lib/format';

export const revalidate = 3600;

export function generateStaticParams() {
  return Object.keys(PAESI).map((c) => ({ country: slugPaese(c) }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ country: string }>;
}): Promise<Metadata> {
  const { country } = await params;
  const codice = paeseDaSlug(country);
  if (!codice) return {};
  const nome = PAESI[codice];
  const posts = await outlierDi('country', codice, 1);
  const migliore = posts[0];

  const titolo = `Viral Shorts outliers in ${nome} — IOSA`;
  const descrizione = migliore
    ? `The short videos outperforming their own channel baseline in ${nome} right now. Top measurement: ${
        migliore.author_handle ?? 'a channel'
      } at ${formatVPI(migliore.vpi_ratio)} its usual views.`
    : `Short videos outperforming their own channel baseline in ${nome}.`;

  return {
    title: titolo,
    description: descrizione,
    alternates: { canonical: `${SITO}/outliers/${country}` },
    openGraph: {
      type: 'website',
      siteName: 'IOSA',
      title: titolo,
      description: descrizione,
      url: `${SITO}/outliers/${country}`,
      images: [{ url: '/og-image.png', width: 1200, height: 630, alt: titolo }],
    },
    twitter: {
      card: 'summary_large_image',
      title: titolo,
      description: descrizione,
      images: ['/og-image.png'],
    },
  };
}

export default async function PaginaPaese({
  params,
}: {
  params: Promise<{ country: string }>;
}) {
  const { country } = await params;
  const codice = paeseDaSlug(country);
  if (!codice) notFound();

  const nome = PAESI[codice];
  const [posts, totale] = await Promise.all([
    outlierDi('country', codice, 60),
    contaDi('country', codice),
  ]);

  const migliore = posts[0];
  const sottotitolo = migliore
    ? `${totale.toLocaleString(
        'en-US'
      )} active outliers measured in ${nome}. The strongest one right now is ${
        migliore.author_handle ?? 'a channel'
      }, whose video reached ${formatCount(
        migliore.engagement_score
      )} views against a channel median of ${formatCount(
        migliore.baseline_score
      )} — a VPI of ${formatVPI(
        migliore.vpi_ratio
      )}. Every measurement below compares a video with the recent videos of the same format on its own channel, so channel size does not decide the ranking.`
    : `No active outliers measured in ${nome} right now.`;

  return (
    <PageShell titolo={`Viral outliers in ${nome}`} sottotitolo={sottotitolo}>
      <div className="rounded-xl border border-gray-800 bg-gray-950/40 overflow-hidden">
        <OutlierList posts={posts} />
      </div>
      {totale > posts.length ? (
        <p className="mt-4 font-mono text-[11px] text-gray-500">
          Showing the top {posts.length} of {totale.toLocaleString('en-US')}{' '}
          measurements in {nome}.
        </p>
      ) : null}
    </PageShell>
  );
}
