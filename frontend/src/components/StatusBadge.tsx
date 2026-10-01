import { Flag, TrendingUp } from 'lucide-react';
import { dataBreve, etichettaStato, inClassifica, type RecordPubblico } from '@/lib/record-status';

/**
 * Lo stato a colpo d'occhio (UI-7, 01/10/2026), identico ovunque compaia:
 * in Most Popular, una freccia che sale in ciano con "day N"; uscito, una
 * bandiera in grigio con "N days, left <data>". Forma dell'icona e testo
 * cambiano insieme al colore, che non e' mai l'unico segnale; l'etichetta
 * completa e' per i lettori di schermo e nel tooltip.
 */
export function StatusIcon({ post, className = 'w-3 h-3' }: { post: RecordPubblico; className?: string }) {
  return inClassifica(post)
    ? <TrendingUp className={`${className} text-[#00E5FF] shrink-0`} aria-hidden data-status-icon="charting" />
    : <Flag className={`${className} text-gray-400 shrink-0`} aria-hidden data-status-icon="left" />;
}

/** "day 3" oppure "3 days, left 30 Sept 2026". */
export function etichettaBreve(post: RecordPubblico): string {
  const n = post.day_n ?? (inClassifica(post) ? null : post.days_charting) ?? null;
  if (inClassifica(post)) return n ? `day ${n}` : 'in Most Popular';
  const giorni = n ? `${n} day${n === 1 ? '' : 's'}` : 'left';
  return post.left_on ? `${giorni}, left ${dataBreve(post.left_on)}` : giorni;
}

/** L'etichetta completa: "In Most Popular - day 3", "Left Most Popular - 3 days, left 30 Sept 2026". */
export function etichettaCompleta(post: RecordPubblico): string {
  const base = etichettaStato(post);
  return !inClassifica(post) && post.left_on ? `${base}, left ${dataBreve(post.left_on)}` : base;
}

export function StatusBadge({ post }: { post: RecordPubblico }) {
  const dentro = inClassifica(post);
  const completa = etichettaCompleta(post);
  return (
    <span
      data-status-badge={dentro ? 'charting' : 'left'}
      title={completa}
      className={`inline-flex items-center gap-1 text-[9px] font-mono px-1.5 py-0.5 rounded border font-bold whitespace-nowrap ${
        dentro
          ? 'bg-cyan-950/50 text-[#00E5FF] border-cyan-500/40'
          : 'bg-gray-900 text-gray-300 border-gray-700'
      }`}
    >
      <StatusIcon post={post} />
      <span aria-hidden>{etichettaBreve(post)}</span>
      <span className="sr-only">{completa}</span>
    </span>
  );
}
