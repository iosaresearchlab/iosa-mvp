'use client';

/** SOC-W1: the share row of a Findings story: copy its fixed URL. */
import { useState } from 'react';
import { Link2, Check } from 'lucide-react';

export function CopyLinkButton({ url }: { url: string }) {
  const [copiato, setCopiato] = useState(false);
  return (
    <button
      type="button"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(url);
          setCopiato(true);
          setTimeout(() => setCopiato(false), 2000);
        } catch {
          window.prompt('Copy this link', url);
        }
      }}
      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-800 bg-gray-900/80 hover:border-cyan-500/50 font-mono text-xs text-gray-300 hover:text-[#00E5FF] transition-colors cursor-pointer"
    >
      {copiato ? <Check className="w-3.5 h-3.5 text-[#00E5FF]" /> : <Link2 className="w-3.5 h-3.5" />}
      {copiato ? 'Link copied' : 'Copy link'}
    </button>
  );
}
