import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { PageShell } from '@/components/PageShell';
import { OutlierList } from '@/components/OutlierList';
import { outlierDi, contaDi } from '@/lib/supabase-server';
import { categoriaDaSlug, SITO } from '@/lib/segments';

export const revalidate = 21600; // OPS-1, 17/10: hourly ISR passed the Vercel Hobby limit (212K of 200K ISR writes a month); 6 h keeps pages at most 6 h behind the daily reading

// FIX-1c (20/10/2026): not prerendered at build. 47 segment pages read the
// database at once during the build and a few reads hit the 3 s timeout:
// with leggi() a failed read fails the build (two deploys of 20/10). Each
// page is now rendered on its first visit and kept 6 h like the creator
// pages; the build reads nothing from the database for them.
export function generateStaticParams() {
  return [];
}

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
