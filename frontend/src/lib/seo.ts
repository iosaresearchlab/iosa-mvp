import type { Metadata } from 'next';

/**
 * Titolo e descrizione per pagina, anche nelle anteprime social.
 *
 * Prima ogni pagina aveva il suo <title> ma i tag Open Graph restavano quelli
 * del sito: chi condivideva la classifica dell'Italia mostrava un'anteprima
 * che parlava genericamente di IOSA. Qui i due restano allineati per
 * costruzione, e non si possono piu' dimenticare.
 */
export const SITO =
  process.env.NEXT_PUBLIC_SITE_URL ?? 'https://iosaresearch.org';

export function metadatiPagina({
  titolo,
  descrizione,
  percorso,
  indicizzabile = true,
}: {
  titolo: string;
  descrizione: string;
  percorso: string;
  indicizzabile?: boolean;
}): Metadata {
  const url = `${SITO}${percorso}`;
  return {
    title: titolo,
    description: descrizione,
    alternates: { canonical: url },
    openGraph: {
      type: 'website',
      siteName: 'IOSA',
      title: titolo,
      description: descrizione,
      url,
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
