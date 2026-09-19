/**
 * Scala VPI: unica definizione lato frontend.
 *
 * I valori qui sotto rispecchiano VPI_SCALE in backend/vpi_core.py, che e' la
 * definizione documentata della scala e quella che il motore scrive nella
 * colonna vpi_color di ogni record.
 *
 * Prima di questo file convivevano quattro palette diverse e incompatibili:
 * una in page.tsx, una quasi identica ma non uguale in claim/[token]/page.tsx,
 * una a scaglioni di due livelli in OutlierList.tsx e quella del backend che
 * nessuna delle tre leggeva. Lo stesso record poteva comparire oro in home,
 * oro con un'altra ombra sulla pagina claim e rosa nelle pagine di segmento.
 * Il colore deve significare intensita', quindi puo' esistere una sola scala.
 */

export type Livello = {
  livello: number;
  nome: string;
  colore: string;
};

/** (soglia minima, livello, nome, colore) — dal piu' alto al piu' basso. */
const SCALA: ReadonlyArray<readonly [number, number, string, string]> = [
  [50.0, 10, 'Lvl 10 - Hyper Outlier', '#FF0055'],
  [25.0, 9, 'Lvl 9 - Mega Outlier', '#FF2A00'],
  [15.0, 8, 'Lvl 8 - Outlier', '#FF5500'],
  [10.0, 7, 'Lvl 7 - Super Viral', '#FF8800'],
  [7.5, 6, 'Lvl 6 - Viral', '#FFAA00'],
  [5.0, 5, 'Lvl 5 - Breakout', '#FFCC00'],
  [3.0, 4, 'Lvl 4 - Trending', '#00CC88'],
  [2.0, 3, 'Lvl 3 - Rising', '#0099FF'],
  [1.5, 2, 'Lvl 2 - Moderate', '#7755FF'],
  [0.0, 1, 'Lvl 1 - Standard', '#888888'],
];

export const LIVELLI: ReadonlyArray<Livello> = SCALA.map(
  ([, livello, nome, colore]) => ({ livello, nome, colore })
);

/** Soglia minima di ogni livello, nello stesso ordine di LIVELLI. */
export const SOGLIE: ReadonlyArray<number> = SCALA.map(([soglia]) => soglia);

const PER_NUMERO = new Map(LIVELLI.map((l) => [l.livello, l]));
const FALLBACK = PER_NUMERO.get(1)!;

/** Il livello a cui appartiene un rapporto VPI. */
export function livelloDaRatio(ratio: number | string | null | undefined): Livello {
  const v = typeof ratio === 'number' ? ratio : parseFloat(String(ratio ?? ''));
  if (!Number.isFinite(v)) return FALLBACK;
  for (const [soglia, livello, nome, colore] of SCALA) {
    if (v >= soglia) return { livello, nome, colore };
  }
  return FALLBACK;
}

/** Il livello dato il numero salvato in vpi_level. */
export function livelloDaNumero(n: number | null | undefined): Livello | null {
  if (typeof n !== 'number') return null;
  return PER_NUMERO.get(n) ?? null;
}

/**
 * Il livello di un record, nell'ordine in cui i dati sono affidabili:
 * vpi_level (scritto dal motore), poi il nome, poi il rapporto.
 */
export function livelloDiRecord(post: {
  vpi_level?: number | null;
  vpi_level_name?: string | null;
  vpi_ratio?: number | string | null;
}): Livello {
  const daNumero = livelloDaNumero(post.vpi_level ?? null);
  if (daNumero) return daNumero;

  const match = post.vpi_level_name?.match(/Lvl\s*(\d+)/i);
  if (match) {
    const daNome = livelloDaNumero(parseInt(match[1], 10));
    if (daNome) return daNome;
  }
  return livelloDaRatio(post.vpi_ratio);
}

/**
 * Stile inline del badge. Serve inline e non con classi Tailwind perche' i
 * colori sono valori esatti calcolati a runtime: una classe costruita per
 * concatenazione non verrebbe vista dal compilatore e finirebbe scartata.
 */
export function stileBadge(colore: string): React.CSSProperties {
  return {
    color: colore,
    borderColor: colore,
    backgroundColor: `${colore}1f`,
    boxShadow: `0 0 12px ${colore}33`,
  };
}
