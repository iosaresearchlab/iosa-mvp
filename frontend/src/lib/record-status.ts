/**
 * Lo stato pubblico di un record v2 (HOME-1, CLAIM-2, APP-7; 01/10/2026).
 *
 * Due sole parole di stato, mai altre: "In Most Popular - day N" finche' il
 * video e' nelle classifiche, "Left Most Popular - N days" quando ne e'
 * uscito. Mai "hot", "trending" o "popular" come qualifica: Most Popular e'
 * il nome proprio di cio' che leggiamo, non un giudizio.
 *
 * Il valore mostrato cambia con lo stato (docs/01 §4.1): mentre e' in
 * classifica il VPI del giorno, senza premio; dopo l'uscita il VPI piu' alto
 * osservato, sempre con le views e i giorni in Most Popular.
 */
import { livelloDaRatio, NESSUN_LIVELLO, type Livello } from '@/lib/vpi-scale';

export type RecordPubblico = {
  status?: string | null;
  day_n?: number | null;
  days_charting?: number | null;
  vpi_ratio?: number | string | null;
  vpi_max?: number | string | null;
  views_max?: number | string | null;
  engagement_score?: number | string | null;
  baseline_rule?: string | null;
  left_on?: string | null;
  entered_on?: string | null;
  claim_open_until?: string | null;
};

export function inClassifica(p: RecordPubblico): boolean {
  return p.status !== 'CLOSED';
}

function giorni(n: number): string {
  return `${n} day${n === 1 ? '' : 's'}`;
}

/** "In Most Popular - day 3" oppure "Left Most Popular - 4 days". */
export function etichettaStato(p: RecordPubblico): string {
  const n = p.day_n ?? (inClassifica(p) ? null : p.days_charting) ?? null;
  if (inClassifica(p)) return n ? `In Most Popular - day ${n}` : 'In Most Popular';
  return n ? `Left Most Popular - ${giorni(n)}` : 'Left Most Popular';
}

/** Il VPI che la pagina pubblica: del giorno in classifica, il piu' alto osservato dopo. */
export function vpiPubblicato(p: RecordPubblico): number | string | null {
  return (inClassifica(p) ? p.vpi_ratio : p.vpi_max) ?? null;
}

/** Le views accanto al VPI pubblicato. */
export function viewsPubblicate(p: RecordPubblico): number | string | null {
  return (inClassifica(p) ? p.engagement_score : p.views_max ?? p.engagement_score) ?? null;
}

/**
 * Perche' un record non ha VPI, da baseline_rule (APP-7). Null se il VPI c'e'.
 * Un record senza baseline calcolabile non e' "sotto la soglia": non ha VPI.
 */
export function motivoSenzaVpi(p: RecordPubblico): string | null {
  if (vpiPubblicato(p) !== null && vpiPubblicato(p) !== undefined) return null;
  switch (p.baseline_rule) {
    case 'quota_stop':
    case 'read_failed':
      return 'No VPI yet (baseline still to be read)';
    default:
      return 'No VPI (baseline not computable)';
  }
}

/** Livello del VPI pubblicato, o la ragione per cui non c'e'. */
export function livelloPubblicato(p: RecordPubblico): Livello {
  const motivo = motivoSenzaVpi(p);
  if (motivo) return { livello: 0, nome: motivo, colore: NESSUN_LIVELLO.colore };
  return livelloDaRatio(vpiPubblicato(p)) ?? NESSUN_LIVELLO;
}

/** "1 Oct 2026" da una data ISO (giorno UTC). */
export function dataBreve(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(`${String(iso).slice(0, 10)}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });
}
