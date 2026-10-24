import type { MetadataRoute } from 'next';
import { leggi, supabaseServer } from '@/lib/supabase-server';
import {
  PAESI,
  CATEGORIE,
  slugPaese,
  slugCategoria,
  slugCreator,
  handleSemplice,
  SITO,
} from '@/lib/segments';
import { SERIES_FLOOR } from '@/lib/index-start';
import { storiePubblicate } from '@/lib/findings';

export const revalidate = 21600; // OPS-1, 17/10: hourly ISR passed the Vercel Hobby limit (212K of 200K ISR writes a month); 6 h keeps pages at most 6 h behind the daily reading

/** Creator con almeno due record, in classifica o usciti: sotto non c'e' contenuto a sufficienza. */
const MIN_OUTLIER = 2;

async function creatorDaIndicizzare(): Promise<string[]> {
  const { data } = await leggi('public_records', () =>
    supabaseServer
      .from('public_records')
      .select('author_handle')
      .eq('method_version', 'v2')
      .gte('entered_on', SERIES_FLOOR)   // in Most Popular or left (APP-8)
  );

  const conteggio = new Map<string, number>();
  for (const riga of (data || []) as { author_handle: string | null }[]) {
    const h = riga.author_handle;
    if (h && handleSemplice(h)) conteggio.set(h, (conteggio.get(h) || 0) + 1);
  }

  return [...conteggio.entries()]
    .filter(([, n]) => n >= MIN_OUTLIER)
    .map(([h]) => h);
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const adesso = new Date();

  const fisse: MetadataRoute.Sitemap = [
    { url: `${SITO}/`, lastModified: adesso, changeFrequency: 'hourly', priority: 1 },
    { url: `${SITO}/outliers`, lastModified: adesso, changeFrequency: 'hourly', priority: 0.9 },
    { url: `${SITO}/leaderboard`, lastModified: adesso, changeFrequency: 'daily', priority: 0.7 },
    { url: `${SITO}/room`, lastModified: adesso, changeFrequency: 'weekly', priority: 0.7 },
  ];

  const paesi: MetadataRoute.Sitemap = Object.keys(PAESI).map((c) => ({
    url: `${SITO}/outliers/${slugPaese(c)}`,
    lastModified: adesso,
    changeFrequency: 'daily',
    priority: 0.8,
  }));

  const categorie: MetadataRoute.Sitemap = CATEGORIE.map((c) => ({
    url: `${SITO}/categories/${slugCategoria(c)}`,
    lastModified: adesso,
    changeFrequency: 'daily',
    priority: 0.8,
  }));

  // FIX-1c (20/10/2026): a failed read throws instead of publishing a sitemap
  // without its creators for 6 hours; the cached sitemap stays until the
  // next regeneration succeeds.
  const creator: MetadataRoute.Sitemap = (await creatorDaIndicizzare()).map((h) => ({
    url: `${SITO}/creators/${slugCreator(h)}`,
    lastModified: adesso,
    changeFrequency: 'weekly',
    priority: 0.6,
  }));

  // SOC-W1 (24/10/2026): published Findings stories and their index; drafts never.
  const storie = storiePubblicate();
  const findings: MetadataRoute.Sitemap = storie.length
    ? [
        { url: `${SITO}/insights/findings`, lastModified: new Date(`${storie[0].date}T00:00:00Z`), changeFrequency: 'weekly', priority: 0.7 },
        ...storie.map((m) => ({
          url: `${SITO}/insights/findings/${m.slug}`,
          lastModified: new Date(`${m.date}T00:00:00Z`),
          changeFrequency: 'monthly' as const,
          priority: 0.7,
        })),
      ]
    : [];

  return [...fisse, ...findings, ...paesi, ...categorie, ...creator];
}
