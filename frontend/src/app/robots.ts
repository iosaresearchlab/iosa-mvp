import type { MetadataRoute } from 'next';
import { SITO } from '@/lib/segments';

// The crawlers that build link previews on the networks we post to and in DMs.
const PREVIEW_BOTS = [
  'Twitterbot',
  'facebookexternalhit',
  'Bluesky Cardyb',
  'Slackbot',
  'LinkedInBot',
  'WhatsApp',
  'TelegramBot',
  'Discordbot',
];

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
      {
        // FIX-1d: link-preview fetchers, not search indexes. They obey
        // robots.txt (Twitterbot does), so a claim link sent in a DM or posted
        // on X would preview as nothing. They may read the claim page and its
        // card; search engines still may not.
        userAgent: PREVIEW_BOTS,
        allow: '/',
      },
    ],
    sitemap: `${SITO}/sitemap.xml`,
    host: SITO,
  };
}
