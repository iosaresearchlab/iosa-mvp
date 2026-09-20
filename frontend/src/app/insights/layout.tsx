import { metadatiPagina } from '@/lib/seo';

export const metadata = metadatiPagina({
  titolo: 'Where short videos break out — IOSA macro insights',
  descrizione:
    'Viral Performance Index by country, macro-region and category: which markets produce the largest jumps from a channel to its own baseline, and which keywords travel with them.',
  percorso: '/insights',
});

export default function LayoutInsights({ children }: { children: React.ReactNode }) {
  return children;
}
