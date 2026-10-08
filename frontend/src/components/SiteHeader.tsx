'use client';

/**
 * L'unica testata del sito (UI-4, 01/10/2026), montata dal layout radice: home,
 * Top VPI, outliers, paesi, categorie, creator, claim e insights hanno la
 * stessa. Il metodo e le FAQ sono modali della home, raggiunte da qui con
 * l'ancora (#methodology, #faq).
 */
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Globe, HelpCircle, Info, Trophy, Tv } from 'lucide-react';
import { Logo } from '@/components/Logo';

const VOCI = [
  { href: '/outliers', etichetta: 'Browse', icona: Globe, attiva: (p: string) => p.startsWith('/outliers') || p.startsWith('/categories') },
  { href: '/leaderboard', etichetta: 'Top VPI', icona: Trophy, attiva: (p: string) => p.startsWith('/leaderboard') },
  // ROOM-1: a static page outside the app router, so a plain link (see below)
  { href: '/room', etichetta: 'The Room', icona: Tv, attiva: () => false, statica: true },
  { href: '/#methodology', etichetta: 'Method', icona: Info, attiva: () => false },
  { href: '/#faq', etichetta: 'FAQ', icona: HelpCircle, attiva: () => false },
];

export function SiteHeader() {
  const percorso = usePathname() || '/';
  return (
    <header data-site-header className="sticky top-0 z-50 bg-[#030508]/90 backdrop-blur-md border-b border-gray-800/80">
      <div className="max-w-6xl mx-auto px-3 md:px-8 py-1.5 flex items-center justify-between gap-3">
        <Link href="/" aria-label="IOSA - home" className="shrink-0 rounded focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#00E5FF]">
          <Logo altezza={44} />
        </Link>
        <nav aria-label="Main" className="flex items-center gap-1.5 md:gap-2">
          {VOCI.map(({ href, etichetta, icona: Icona, attiva, statica }) => {
            const corrente = attiva(percorso);
            const Ancora = statica ? 'a' : Link;
            return (
              <Ancora key={href} href={href} aria-current={corrente ? 'page' : undefined}
                className={`flex items-center gap-1 px-2.5 py-1 rounded-full font-mono text-xs border transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#00E5FF] ${
                  corrente ? 'bg-[#00E5FF] text-black border-[#00E5FF] font-bold' : 'bg-gray-900 hover:bg-gray-800 border-gray-700 text-gray-200'}`}>
                <Icona className={`w-3.5 h-3.5 ${corrente ? 'text-black' : 'text-[#00E5FF]'}`} aria-hidden />
                <span className="hidden sm:inline">{etichetta}</span>
                <span className="sr-only sm:hidden">{etichetta}</span>
              </Ancora>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
