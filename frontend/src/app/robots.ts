import type { MetadataRoute } from 'next';
import { SITO } from '@/lib/segments';

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: '*',
        allow: '/',
        // Le pagine claim sono personali e raggiungibili solo con il token:
        // non hanno motivo di finire in un indice pubblico.
        disallow: ['/claim/'],
      },
    ],
    sitemap: `${SITO}/sitemap.xml`,
    host: SITO,
  };
}
