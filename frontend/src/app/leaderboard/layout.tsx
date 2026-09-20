import { metadatiPagina } from '@/lib/seo';

// La pagina e' un componente client e non puo' esportare metadata da sola:
// serve questo layout. Prima ereditava titolo e descrizione dalla home, e per
// un motore di ricerca erano due pagine uguali.
export const metadata = metadatiPagina({
  titolo: 'Top creators by viral spikes — IOSA leaderboard',
  descrizione:
    'Creators ranked by how often their short videos outrun their own channel baseline, not by subscriber count. Global and per-country, updated continuously.',
  percorso: '/leaderboard',
});

export default function LayoutClassifica({ children }: { children: React.ReactNode }) {
  return children;
}
