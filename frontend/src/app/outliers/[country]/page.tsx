import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { PageShell } from '@/components/PageShell';
import { OutlierList } from '@/components/OutlierList';
import { outlierDi, contaDi } from '@/lib/supabase-server';
import { PAESI, slugPaese, paeseDaSlug, SITO } from '@/lib/segments';

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
  const titolo = `${nome}: videos in Most Popular now — IOSA`;
  const descrizione = `Long-form videos in YouTube's Most Popular charts in ${nome}, ordered by views, with each video's VPI against its own channel baseline beside it.`;

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

  const sottotitolo = totale
    ? `${totale.toLocaleString('en-US')} long-form videos in Most Popular in ${nome} right now. Ordered by views, VPI beside each video: the VPI compares a video with the same channel's long-form videos published 7-90 days before it.`
    : `No long-form video in Most Popular in ${nome} right now.`;

  return (
    <PageShell titolo={`${nome}: videos in Most Popular now`} sottotitolo={sottotitolo}>
      <div className="rounded-xl border border-gray-800 bg-gray-950/40 overflow-hidden">
        <OutlierList posts={posts} />
      </div>
      {totale > posts.length ? (
        <p className="mt-4 font-mono text-[11px] text-gray-500">
          Showing the first {posts.length} of {totale.toLocaleString('en-US')}{' '}
          videos by views in {nome}.
        </p>
      ) : null}
    </PageShell>
  );
}
