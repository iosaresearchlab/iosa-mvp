/**
 * Il valore VPI e il suo livello (UI-9, 01/10/2026).
 *
 * Il badge compare solo per i livelli 1-10. Sotto la prima soglia c'e' il
 * valore e basta ("Below level 1" nel tooltip); senza baseline calcolabile
 * c'e' "n/c", attenuato, con la ragione nel tooltip; in attesa della lettura
 * della baseline, "pending". Il valore e' la cifra principale della riga.
 */
import { formatVPI } from '@/lib/format';
import { livelloDaRatio, stileBadge, SOGLIA_MINIMA } from '@/lib/vpi-scale';
import { vpiPubblicato, type RecordPubblico } from '@/lib/record-status';

export const TOOLTIP_NC = 'No VPI: the channel has fewer than 5 long-form videos in the baseline window';
export const TOOLTIP_PENDING = 'No VPI yet: the baseline is still to be read';
export const TOOLTIP_BELOW = 'Below level 1';

function Spiegato({ testo, spiegazione, className }: { testo: string; spiegazione: string; className: string }) {
  return (
    <abbr title={spiegazione} tabIndex={0} className={`no-underline cursor-help ${className}`} data-vpi-note={testo}>
      <span aria-hidden>{testo}</span>
      <span className="sr-only">{spiegazione}</span>
    </abbr>
  );
}

export function VpiCell({ post, grande = true }: { post: RecordPubblico; grande?: boolean }) {
  const vpi = vpiPubblicato(post);
  const dim = grande ? 'text-base' : 'text-sm';
  if (vpi === null || vpi === undefined) {
    const pending = post.baseline_rule === 'quota_stop' || post.baseline_rule === 'read_failed';
    return (
      <Spiegato testo={pending ? 'pending' : 'n/c'} spiegazione={pending ? TOOLTIP_PENDING : TOOLTIP_NC}
        className={`${dim} font-mono text-gray-500`} />
    );
  }
  const livello = livelloDaRatio(vpi);
  if (!livello) {
    return <Spiegato testo={formatVPI(vpi)} spiegazione={`${TOOLTIP_BELOW} (${SOGLIA_MINIMA}x)`}
      className={`${dim} font-mono font-black text-gray-300`} />;
  }
  return (
    <div className="flex flex-col gap-0.5 items-start">
      <span className={`${dim} font-mono font-black leading-none text-[#00E5FF]`}>{formatVPI(vpi)}</span>
      <span className="text-[8px] px-1.5 py-0.5 rounded font-bold uppercase border w-fit whitespace-nowrap"
        style={stileBadge(livello.colore)} data-level-badge>
        {livello.nome}
      </span>
    </div>
  );
}
