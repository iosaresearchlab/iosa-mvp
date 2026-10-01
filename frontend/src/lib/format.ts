// Formattazione dei numeri mostrati nelle schede a larghezza fissa.
// Senza questo, un VPI come 1293859 esce dal badge e si sovrappone al titolo.
//
// Gli ingressi possono essere stringhe: Supabase restituisce le colonne
// numeric come stringhe, quindi qui si converte sempre prima di formattare.

type Numerico = number | string | null | undefined;

function aNumero(value: Numerico): number {
  if (value === null || value === undefined) return NaN;
  return typeof value === 'number' ? value : Number(String(value).replace(/,/g, '').trim());
}

// UI-11: the two VPI formatters round down at the displayed precision; they
// live in vpi-format.mjs, which a test holds to backend/vpi_format.py.
export { formatVPI, formatVPIFull } from './vpi-format.mjs';

/** Conteggi compatti per il web: "842", "1.2K", "37K", "1.3M". */
export function formatCount(value: Numerico): string {
  const n = aNumero(value);
  if (!Number.isFinite(n)) return 'N/A';
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 10_000) return `${Math.round(n / 1_000)}K`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString('en-US');
}

// Sui gadget (targa, tazza) si stampa il valore esteso con il separatore
// delle migliaia: e' il certificato del dato, non una dashboard.

/** Conteggio esteso per la stampa: "37,155,761". */
export function formatCountFull(value: Numerico): string {
  const n = aNumero(value);
  if (!Number.isFinite(n)) return 'N/A';
  return Math.round(n).toLocaleString('en-US');
}
