// UI-11 (owner decision 02/10/2026): a VPI shown to people is rounded DOWN at
// the precision it is displayed with, so the number never reaches a level
// threshold the record has not reached (1.48 is "+1.4x", never "+1.5x"; 2,496
// is "+2.4Kx", never "+2.5Kx"). The level is still computed on the full value.
//
// Plain JavaScript on purpose: tests/test_vpi_format.py runs this file in node
// and holds it to backend/vpi_format.py, string for string.
//
// The floor is taken on the shortest decimal that identifies the number (the
// same digits in JavaScript's String() and Python's repr()), with string
// arithmetic only: no multiplication in floating point, so 2.3 stays 2.3.

const DASH = '—';

/** The number as [digits, exponent]: value = digits x 10^exponent. */
function decimale(n) {
  const m = /^(\d+)(?:\.(\d+))?(?:e([+-]?\d+))?$/.exec(String(n));
  if (!m) return null;
  const frazione = m[2] || '';
  return [(m[1] + frazione).replace(/^0+(?=\d)/, ''), Number(m[3] || 0) - frazione.length];
}

/** floor(n / 10^scala) with `cifre` decimals, as a string ("1.4", "2", "0.0"). */
function giu(n, scala, cifre) {
  const [digits, esp] = decimale(n);
  const p = esp - scala + cifre;
  let m = p >= 0 ? digits + '0'.repeat(p) : digits.slice(0, Math.max(0, digits.length + p));
  m = (m.replace(/^0+/, '') || '0').padStart(cifre + 1, '0');
  return cifre ? `${m.slice(0, -cifre)}.${m.slice(-cifre)}` : m;
}

function migliaia(s) {
  return s.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

function numero(value) {
  if (value === null || value === undefined) return NaN;
  return typeof value === 'number' ? value : Number(String(value).replace(/,/g, '').trim());
}

/** Compact, for the web: "+12.5x", "+347x", "+1.3Kx", "+13Kx", "+1.3Mx". */
export function formatVPI(value) {
  const n = numero(value);
  if (!Number.isFinite(n) || n <= 0) return DASH;
  if (n >= 1_000_000) return `+${giu(n, 6, 1)}Mx`;
  if (n >= 10_000) return `+${giu(n, 3, 0)}Kx`;
  if (n >= 1_000) return `+${giu(n, 3, 1)}Kx`;
  if (n >= 100) return `+${giu(n, 0, 0)}x`;
  return `+${giu(n, 0, 1)}x`;
}

/** Full, for print (plaque, mug): "+1,293,859x"; below 100, one decimal. */
export function formatVPIFull(value) {
  const n = numero(value);
  if (!Number.isFinite(n) || n <= 0) return DASH;
  if (n >= 100) return `+${migliaia(giu(n, 0, 0))}x`;
  return `+${giu(n, 0, 1)}x`;
}
