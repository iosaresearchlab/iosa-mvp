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
    <main className="flex-1 bg-[#030508] text-white">

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

    </main>
  );
}
