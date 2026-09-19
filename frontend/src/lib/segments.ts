// Nomi e indirizzi dei segmenti pubblici.
//
// Ogni paese e ogni categoria ha una pagina propria, servita gia' compilata:
// e' l'unica superficie che un motore di ricerca puo' indicizzare, visto che
// la tabella in home viene costruita dal browser e a un crawler arriva vuota.

export const PAESI: Record<string, string> = {
  AR: 'Argentina',
  AT: 'Austria',
  AU: 'Australia',
  BE: 'Belgium',
  BR: 'Brazil',
  CA: 'Canada',
  CH: 'Switzerland',
  CL: 'Chile',
  CO: 'Colombia',
  DE: 'Germany',
  DK: 'Denmark',
  ES: 'Spain',
  FI: 'Finland',
  FR: 'France',
  GB: 'United Kingdom',
  ID: 'Indonesia',
  IE: 'Ireland',
  IN: 'India',
  IT: 'Italy',
  JP: 'Japan',
  KR: 'South Korea',
  MX: 'Mexico',
  NL: 'Netherlands',
  NO: 'Norway',
  NZ: 'New Zealand',
  PH: 'Philippines',
  PL: 'Poland',
  PT: 'Portugal',
  SE: 'Sweden',
  TH: 'Thailand',
  TR: 'Turkey',
  US: 'United States',
  VN: 'Vietnam',
  ZA: 'South Africa',
};

export const CATEGORIE = [
  'Autos & Vehicles',
  'Comedy',
  'Entertainment',
  'Film & Animation',
  'Gaming',
  'Howto & Style',
  'Music',
  'News & Politics',
  'Nonprofits & Activism',
  'People & Blogs',
  'Pets & Animals',
  'Sports',
  'Tech',
];

/** "Film & Animation" -> "film-animation" */
export function slugCategoria(categoria: string): string {
  return categoria
    .toLowerCase()
    .replace(/&/g, ' ')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

export function categoriaDaSlug(slug: string): string | null {
  return CATEGORIE.find((c) => slugCategoria(c) === slug) ?? null;
}

/** "United States" -> "united-states" */
export function slugPaese(codice: string): string {
  const nome = PAESI[codice];
  if (!nome) return codice.toLowerCase();
  return nome.toLowerCase().replace(/[^a-z0-9]+/g, '-');
}

export function paeseDaSlug(slug: string): string | null {
  const codice = Object.keys(PAESI).find((c) => slugPaese(c) === slug);
  return codice ?? null;
}

/**
 * Indirizzo della pagina di un creator.
 *
 * Il segmento e' l'handle senza la chiocciola iniziale. Non viene ridotto a
 * lettere e trattini perche' gli handle contengono alfabeti non latini
 * (tamil, cirillico) e due creator diversi finirebbero sullo stesso indirizzo.
 * Meglio un indirizzo con qualche carattere percentuale che una collisione.
 */
export function slugCreator(handle: string): string {
  return encodeURIComponent(handle.replace(/^@+/, ''));
}

export function handleDaSlug(slug: string): string {
  return '@' + decodeURIComponent(slug);
}

/** Solo gli handle scrivibili in ASCII finiscono nella sitemap. */
export function handleSemplice(handle: string): boolean {
  return /^@[A-Za-z0-9._-]{2,60}$/.test(handle);
}

export const SITO =
  process.env.NEXT_PUBLIC_SITE_URL ?? 'https://iosa-mvp-psi.vercel.app';
