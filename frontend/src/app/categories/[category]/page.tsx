import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { PageShell } from '@/components/PageShell';
import { OutlierList } from '@/components/OutlierList';
import { outlierDi, contaDi } from '@/lib/supabase-server';
import { categoriaDaSlug, SITO } from '@/lib/segments';

// OPS-4 (30/10/2026, second step): no ISR. With the creator pages out of ISR these pages
// were the writes left (country 158 + category 39 of 211 units, 30/10 10:2x-22:2x UTC),
// one per page a crawler opens. Rendered per request (FIX-1c: the build still reads
// nothing from the database for them) and kept 6 h by Vercel's CDN, as their former
// revalidate = 21600 (Vercel-CDN-Cache-Control, next.config.ts).
export const dynamic = 'force-dynamic';

export async function generateMetadata({
  params,
}: {
  params: Promise<{ category: string }>;
}): Promise<Metadata> {
  const { category } = await params;
  const nome = categoriaDaSlug(category);
  if (!nome) return {};
  const titolo = `${nome}: videos in Most Popular now — IOSA`;
  const descrizione = `${nome} long-form videos in YouTube's Most Popular charts, ordered by views, with each video's VPI against its own channel baseline beside it.`;

  return {
    title: titolo,
    description: descrizione,
    alternates: { canonical: `${SITO}/categories/${category}` },
    openGraph: {
      type: 'website',
      siteName: 'IOSA',
      title: titolo,
      description: descrizione,
      url: `${SITO}/categories/${category}`,
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

export default async function PaginaCategoria({
  params,
}: {
  params: Promise<{ category: string }>;
}) {
  const { category } = await params;
  const nome = categoriaDaSlug(category);
  if (!nome) notFound();

  const [posts, totale] = await Promise.all([
    outlierDi('category', nome, 60),
    contaDi('category', nome),
  ]);

  const sottotitolo = totale
    ? `${totale.toLocaleString('en-US')} long-form ${nome} videos in Most Popular right now. Ordered by views, VPI beside each video: the VPI compares a video with the same channel's long-form videos published 7-90 days before it.`
    : `No long-form ${nome} video in Most Popular right now.`;

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
