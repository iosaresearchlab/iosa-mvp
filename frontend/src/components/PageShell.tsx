import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';

export function PageShell({
  titolo,
  sottotitolo,
  mostraRitorno = true,
  children,
}: {
  titolo: string;
  sottotitolo?: string;
  /** Sulla pagina indice il link "All segments" punterebbe a se stessa. */
  mostraRitorno?: boolean;
  children: React.ReactNode;
}) {
  return (
    <main className="flex-1 bg-black text-white">
      <header className="border-b border-gray-900 px-4 py-3">
        <div className="max-w-5xl mx-auto flex items-center justify-between gap-4">
          <Link href="/" className="flex flex-col">
            <span className="font-mono font-black text-lg tracking-tight">IOSA</span>
            <span className="font-mono text-[8px] text-gray-500 tracking-widest uppercase">
              Institute for Open Social Analytics
            </span>
          </Link>
          <nav className="flex items-center gap-3 font-mono text-[11px]">
            <Link href="/outliers" className="text-gray-400 hover:text-[#00E5FF]">
              Browse
            </Link>
            <Link href="/insights" className="text-gray-400 hover:text-[#00E5FF]">
              Insights
            </Link>
            <Link href="/leaderboard" className="text-gray-400 hover:text-[#00E5FF]">
              Leaderboard
            </Link>
          </nav>
        </div>
      </header>

      <div className="max-w-5xl mx-auto px-4 py-8">
        {mostraRitorno ? (
          <Link
            href="/outliers"
            className="inline-flex items-center gap-1.5 font-mono text-[11px] text-gray-500 hover:text-[#00E5FF] mb-5"
          >
            <ArrowLeft className="w-3 h-3" /> All segments
          </Link>
        ) : null}

        <h1 className="text-2xl sm:text-3xl font-black font-mono tracking-tight mb-2">
          {titolo}
        </h1>
        {sottotitolo ? (
          <p className="text-sm text-gray-400 leading-relaxed max-w-3xl mb-6">
            {sottotitolo}
          </p>
        ) : null}

        {children}
      </div>

      <footer className="border-t border-gray-900 px-4 py-6 mt-8">
        <div className="max-w-5xl mx-auto font-mono text-[10px] text-gray-500 leading-relaxed">
          <p className="mb-2">
            VPI = E<sub>act</sub> / E<sub>base</sub> — a video&#39;s views divided by
            the median views of the same channel&#39;s recent videos of the same
            format — Shorts against Shorts, long videos against long videos. It is our own
            measurement, not a certification issued by any authority.
          </p>
          <p>
            IOSA is an independent, self-funded research project with no profit
            purpose. Not affiliated with, endorsed by, sponsored by, or associated
            with YouTube, Google LLC, TikTok, or any other platform.{' '}
            <a href="/privacy.html" className="underline hover:text-gray-300">
              Privacy
            </a>{' '}
            ·{' '}
            <a href="/terms.html" className="underline hover:text-gray-300">
              Terms
            </a>
          </p>
        </div>
      </footer>
    </main>
  );
}
