import { metadatiPagina } from '@/lib/seo';

// La pagina e' un componente client e non puo' esportare metadata da sola:
// serve questo layout. Prima ereditava titolo e descrizione dalla home, e per
// un motore di ricerca erano due pagine uguali.
export const metadata = metadatiPagina({
  titolo: 'Top VPI, first day observed — IOSA',
  descrizione:
    'Videos ranked by VPI on the first day we observed them in YouTube Most Popular: views against the median of the same channel and format. Not age-adjusted.',
  percorso: '/leaderboard',
});

export default function LayoutClassifica({ children }: { children: React.ReactNode }) {
  return children;
}
