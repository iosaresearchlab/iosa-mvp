// Formattazione compatta dei numeri mostrati nelle schede a larghezza fissa.
// Senza questo, un VPI come 1293859 esce dal badge e si sovrappone al titolo.

/** VPI gia' completo di segno e suffisso: "+12.5x", "+347x", "+1.3Kx", "+1.3Mx". */
export function formatVPI(value: number): string {
  if (!Number.isFinite(value) || value <= 0) return '\u2014';
  if (value >= 1_000_000) return `+${(value / 1_000_000).toFixed(1)}Mx`;
  if (value >= 10_000) return `+${Math.round(value / 1_000)}Kx`;
  if (value >= 1_000) return `+${(value / 1_000).toFixed(1)}Kx`;
  if (value >= 100) return `+${Math.round(value)}x`;
  return `+${value.toFixed(1)}x`;
}

/** Conteggi di visualizzazioni: "842", "1.2K", "37K", "1.3M". */
export function formatCount(value: number): string {
  if (!Number.isFinite(value)) return 'N/A';
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 10_000) return `${Math.round(value / 1_000)}K`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return value.toLocaleString('en-US');
}
