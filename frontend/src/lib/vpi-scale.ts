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

/**
 * (soglia minima, livello, nome, colore) — dal piu' alto al piu' basso.
 * Soglie fissate dal titolare del progetto il 25/09/2026 (docs/01 §4.3); puo'
 * cambiarle quando vuole. Sotto la soglia piu' bassa un record non ha livello.
 */
const SCALA: ReadonlyArray<readonly [number, number, string, string]> = [
  [2500.0, 10, 'Lvl 10 - Hyper Outlier', '#FF0055'],
  [1500.0, 9, 'Lvl 9 - Mega Outlier', '#FF2A00'],
  [1000.0, 8, 'Lvl 8 - Outlier', '#FF5500'],
  [250.0, 7, 'Lvl 7 - Super Viral', '#FF8800'],
  [100.0, 6, 'Lvl 6 - Viral', '#FFAA00'],
  [50.0, 5, 'Lvl 5 - Breakout', '#FFCC00'],
  [25.0, 4, 'Lvl 4 - Trending', '#00CC88'],
  [10.0, 3, 'Lvl 3 - Rising', '#0099FF'],
  [5.0, 2, 'Lvl 2 - Moderate', '#7755FF'],
  [1.5, 1, 'Lvl 1 - Standard', '#888888'],
];

export const LIVELLI: ReadonlyArray<Livello> = SCALA.map(
  ([, livello, nome, colore]) => ({ livello, nome, colore })
);

/** Soglia minima di ogni livello, nello stesso ordine di LIVELLI. */
export const SOGLIE: ReadonlyArray<number> = SCALA.map(([soglia]) => soglia);

const PER_NUMERO = new Map(LIVELLI.map((l) => [l.livello, l]));

/** Soglia sotto la quale un record ha un VPI ma nessun livello. */
export const SOGLIA_MINIMA = SCALA[SCALA.length - 1][0];

/** Cosa mostrare per un record senza livello: il VPI c'e', il livello no. */
export const NESSUN_LIVELLO: Livello = {
  livello: 0,
  nome: `No level (VPI < ${SOGLIA_MINIMA}x)`,
  colore: SCALA[SCALA.length - 1][3],
};

/** Il livello a cui appartiene un rapporto VPI; null sotto la soglia minima. */
export function livelloDaRatio(ratio: number | string | null | undefined): Livello | null {
  const v = typeof ratio === 'number' ? ratio : parseFloat(String(ratio ?? ''));
  if (!Number.isFinite(v)) return null;
  for (const [soglia, livello, nome, colore] of SCALA) {
    if (v >= soglia) return { livello, nome, colore };
  }
  return null;
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
  return livelloDaRatio(post.vpi_ratio) ?? NESSUN_LIVELLO;
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
