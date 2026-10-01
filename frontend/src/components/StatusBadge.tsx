import { etichettaStato, inClassifica, type RecordPubblico } from '@/lib/record-status';

/** Il badge di stato, identico su ogni pagina (HOME-1). */
export function StatusBadge({ post }: { post: RecordPubblico }) {
  const dentro = inClassifica(post);
  return (
    <span
      data-status-badge={dentro ? 'charting' : 'left'}
      className={`text-[8px] font-mono px-1.5 py-0.5 rounded border uppercase font-bold whitespace-nowrap ${
        dentro
          ? 'bg-emerald-950/50 text-emerald-300 border-emerald-500/40'
          : 'bg-gray-900 text-gray-300 border-gray-700'
      }`}
    >
      {etichettaStato(post)}
    </span>
  );
}
