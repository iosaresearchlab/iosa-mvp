/**
 * SOC-W1 (24/10/2026): the small Markdown a Findings story is written in, rendered
 * on the server as React elements (no HTML is ever injected, so a story cannot
 * carry markup or scripts).
 *
 * Blocks: ## and ### headings (# is the page title and becomes ##), paragraphs,
 * "- " or "* " lists, "1. " lists, "> " quotes, "---" rules.
 * Inline: **bold**, *italic*, `code`, [text](https://...) links.
 */
import Link from 'next/link';
import type { ReactNode } from 'react';

const INLINE = /(\*\*[^*]+\*\*|\*[^*\s][^*]*\*|`[^`]+`|\[[^\]]+\]\([^)\s]+\))/g;

export function inline(testo: string, chiave = 'i'): ReactNode[] {
  return testo.split(INLINE).filter(Boolean).map((pezzo, i) => {
    const k = `${chiave}-${i}`;
    if (pezzo.startsWith('**') && pezzo.endsWith('**') && pezzo.length > 4) {
      return <strong key={k} className="text-white">{pezzo.slice(2, -2)}</strong>;
    }
    if (pezzo.startsWith('`') && pezzo.endsWith('`') && pezzo.length > 2) {
      return <code key={k} className="font-mono text-[0.9em] text-cyan-200 bg-black/60 px-1 rounded">{pezzo.slice(1, -1)}</code>;
    }
    const link = /^\[([^\]]+)\]\(([^)\s]+)\)$/.exec(pezzo);
    if (link) {
      const [, etichetta, href] = link;
      const classe = 'text-[#00E5FF] underline underline-offset-2 hover:text-cyan-300';
      if (href.startsWith('/')) return <Link key={k} href={href} className={classe}>{etichetta}</Link>;
      if (/^https?:\/\//.test(href)) {
        return <a key={k} href={href} className={classe} target="_blank" rel="noopener noreferrer">{etichetta}</a>;
      }
      return etichetta;
    }
    if (pezzo.startsWith('*') && pezzo.endsWith('*') && pezzo.length > 2) {
      return <em key={k}>{pezzo.slice(1, -1)}</em>;
    }
    return pezzo;
  });
}

type Blocco =
  | { t: 'h'; livello: 2 | 3; testo: string }
  | { t: 'p'; testo: string }
  | { t: 'ul' | 'ol'; voci: string[] }
  | { t: 'quote'; testo: string }
  | { t: 'hr' };

export function blocchi(md: string): Blocco[] {
  const out: Blocco[] = [];
  let par: string[] = [];
  const chiudi = () => {
    if (par.length) out.push({ t: 'p', testo: par.join(' ') });
    par = [];
  };
  for (const grezza of md.split(/\r?\n/)) {
    const riga = grezza.trim();
    const h = /^(#{1,3})\s+(.*)$/.exec(riga);
    const ul = /^[-*]\s+(.*)$/.exec(riga);
    const ol = /^\d+\.\s+(.*)$/.exec(riga);
    const ultimo = () => out[out.length - 1];
    if (!riga) chiudi();
    else if (/^(-{3,}|\*{3,})$/.test(riga)) { chiudi(); out.push({ t: 'hr' }); }
    else if (h) { chiudi(); out.push({ t: 'h', livello: h[1].length === 3 ? 3 : 2, testo: h[2] }); }
    else if (ul) {
      chiudi();
      const u = ultimo();
      if (u && u.t === 'ul') u.voci.push(ul[1]);
      else out.push({ t: 'ul', voci: [ul[1]] });
    } else if (ol) {
      chiudi();
      const u = ultimo();
      if (u && u.t === 'ol') u.voci.push(ol[1]);
      else out.push({ t: 'ol', voci: [ol[1]] });
    } else if (riga.startsWith('>')) {
      chiudi();
      const testo = riga.replace(/^>\s?/, '');
      const u = ultimo();
      if (u && u.t === 'quote') u.testo += ` ${testo}`;
      else out.push({ t: 'quote', testo });
    } else par.push(riga);
  }
  chiudi();
  return out;
}

export function Markdown({ testo }: { testo: string }) {
  return (
    <div className="space-y-4 text-[15px] leading-relaxed text-gray-300">
      {blocchi(testo).map((b, i) => {
        const k = `b${i}`;
        switch (b.t) {
          case 'h':
            return b.livello === 2
              ? <h2 key={k} className="text-lg font-bold font-mono text-white pt-2">{inline(b.testo, k)}</h2>
              : <h3 key={k} className="text-base font-bold font-mono text-white pt-1">{inline(b.testo, k)}</h3>;
          case 'p':
            return <p key={k}>{inline(b.testo, k)}</p>;
          case 'ul':
            return <ul key={k} className="list-disc pl-5 space-y-1">{b.voci.map((v, j) => <li key={j}>{inline(v, `${k}-${j}`)}</li>)}</ul>;
          case 'ol':
            return <ol key={k} className="list-decimal pl-5 space-y-1">{b.voci.map((v, j) => <li key={j}>{inline(v, `${k}-${j}`)}</li>)}</ol>;
          case 'quote':
            return <blockquote key={k} className="border-l-2 border-cyan-500/50 pl-4 text-gray-400 italic">{inline(b.testo, k)}</blockquote>;
          case 'hr':
            return <hr key={k} className="border-gray-800" />;
        }
      })}
    </div>
  );
}
