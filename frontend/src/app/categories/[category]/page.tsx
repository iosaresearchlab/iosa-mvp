import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { PageShell } from '@/components/PageShell';
import { OutlierList } from '@/components/OutlierList';
import { outlierDi, contaDi } from '@/lib/supabase-server';
import { CATEGORIE, slugCategoria, categoriaDaSlug, SITO } from '@/lib/segments';
import { formatVPI, formatCount } from '@/lib/format';

export const revalidate = 3600;

export function generateStaticParams() {
  return CATEGORIE.map((c) => ({ category: slugCategoria(c) }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ category: string }>;
}): Promise<Metadata> {
  const { category } = await params;
  const nome = categoriaDaSlug(category);
  if (!nome) return {};
  const posts = await outlierDi('category', nome, 1);
  const migliore = posts[0];

  return {
    title: `${nome} Shorts that broke out — IOSA viral outliers`,
    description: migliore
      ? `${nome} short videos outperforming their own channel baseline. Top measurement: ${
          migliore.author_handle ?? 'a channel'
        } at ${formatVPI(migliore.vpi_ratio)} its usual views.`
      : `${nome} short videos outperforming their own channel baseline.`,
    alternates: { canonical: `${SITO}/categories/${category}` },
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

  const migliore = posts[0];
  const sottotitolo = migliore
    ? `${totale.toLocaleString(
        'en-US'
      )} active outliers measured in ${nome}. The strongest one right now reached ${formatCount(
        migliore.engagement_score
      )} views against a channel median of ${formatCount(
        migliore.baseline_score
      )}, a VPI of ${formatVPI(
        migliore.vpi_ratio
      )}. Ranking is by how far a video beat its own channel, not by raw views.`
    : `No active outliers measured in ${nome} right now.`;

  return (
    <PageShell titolo={`${nome} outliers`} sottotitolo={sottotitolo}>
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
