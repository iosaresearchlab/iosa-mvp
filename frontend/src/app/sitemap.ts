import type { MetadataRoute } from 'next';
import { supabaseServer } from '@/lib/supabase-server';
import {
  PAESI,
  CATEGORIE,
  slugPaese,
  slugCategoria,
  slugCreator,
  handleSemplice,
  SITO,
} from '@/lib/segments';

export const revalidate = 3600;

/** Creator con almeno due outlier attivi: sotto non c'e' contenuto a sufficienza. */
const MIN_OUTLIER = 2;

async function creatorDaIndicizzare(): Promise<string[]> {
  const { data } = await supabaseServer
    .from('posts')
    .select('author_handle')
    .eq('method_version', 'v2')
    .eq('status', 'ACTIVE');

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
    { url: `${SITO}/insights`, lastModified: adesso, changeFrequency: 'daily', priority: 0.7 },
    { url: `${SITO}/leaderboard`, lastModified: adesso, changeFrequency: 'daily', priority: 0.7 },
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

  let creator: MetadataRoute.Sitemap = [];
  try {
    const handle = await creatorDaIndicizzare();
    creator = handle.map((h) => ({
      url: `${SITO}/creators/${slugCreator(h)}`,
      lastModified: adesso,
      changeFrequency: 'weekly',
      priority: 0.6,
    }));
  } catch {
    // Se il database non risponde la sitemap esce comunque con le pagine fisse.
  }

  return [...fisse, ...paesi, ...categorie, ...creator];
}
