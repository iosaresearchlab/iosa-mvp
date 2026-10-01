import { metadatiPagina } from '@/lib/seo';

export const metadata = metadatiPagina({
  titolo: 'Where videos break out — IOSA macro insights',
  descrizione:
    'Viral Performance Index by country, macro-region and category: which markets produce the largest jumps from a channel to its own baseline, and which keywords travel with them.',
  percorso: '/insights',
  // APP-1 (01/10/2026): out of the nav and the sitemap, not indexed, until it
  // is rebuilt on the per-band x format cells (n and median, long-form only).
  indicizzabile: false,
});

export default function LayoutInsights({ children }: { children: React.ReactNode }) {
  return children;
}
