/**
 * SOC-W1 (24/10/2026): the chart of a Findings story, drawn on the server as inline
 * SVG from its data file (no chart library, no client fetch).
 *
 * One series, so no legend: the caption names the measure. Bars: horizontal,
 * one per point, the label on the left and the value at the end of the bar,
 * 4px rounded data end, a 2px gap between bars. Line: 2px, points marked,
 * the last value and the largest labelled. Grid and axes recessive. Every mark
 * carries its value in a <title> (the hover tooltip without script), and the
 * figures are also in a table under the chart.
 */
import type { ChartData } from '@/lib/findings';
import { formatValore } from '@/lib/findings';

const ACCENTO = '#00E5FF';
const GRIGLIA = '#1f2937';
const TESTO = '#9ca3af';
// Two drawings of the same chart: wide for the desktop column, narrow for phones,
// so the labels keep a readable size (SVG text scales with the viewBox).
const LARGO = 720;
const STRETTO = 360;

function tacche(max: number): number[] {
  if (max <= 0) return [0];
  const passoGrezzo = max / 4;
  const potenza = 10 ** Math.floor(Math.log10(passoGrezzo));
  const passo = [1, 2, 2.5, 5, 10].map((m) => m * potenza).find((p) => p >= passoGrezzo) ?? passoGrezzo;
  const out: number[] = [];
  for (let v = 0; v <= max + passo * 0.001; v += passo) out.push(Math.round(v * 1e6) / 1e6);
  if (out[out.length - 1] < max) out.push(out[out.length - 1] + passo);
  return out;
}

function Barre({ d, LARGHEZZA }: { d: ChartData; LARGHEZZA: number }) {
  const stretto = LARGHEZZA < 500;
  const etichetta = stretto ? 86 : 200;
  const destra = stretto ? 62 : 90;
  const altezzaBarra = 22;
  const gap = 10;
  const cima = 24;
  const scala = tacche(Math.max(...d.points.map((p) => p.value)));
  const max = scala[scala.length - 1] || 1;
  const area = LARGHEZZA - etichetta - destra;
  const altezza = cima + d.points.length * (altezzaBarra + gap) + 8;
  const x = (v: number) => etichetta + (Math.max(v, 0) / max) * area;
  return (
    <svg viewBox={`0 0 ${LARGHEZZA} ${altezza}`} width="100%" role="img" aria-label={d.measure} className="block">
      {scala.map((t) => (
        <g key={t}>
          <line x1={x(t)} x2={x(t)} y1={cima - 6} y2={altezza - 8} stroke={GRIGLIA} strokeWidth={1} />
          <text x={x(t)} y={cima - 10} fill={TESTO} fontSize={11} textAnchor="middle" fontFamily="monospace">
            {formatValore(t)}
          </text>
        </g>
      ))}
      {d.points.map((p, i) => {
        const y = cima + i * (altezzaBarra + gap);
        const w = Math.max(x(p.value) - etichetta, 2);
        const r = Math.min(4, w / 2);
        // rounded at the data end only, square on the baseline
        const path = `M${etichetta},${y} h${w - r} q${r},0 ${r},${r} v${altezzaBarra - 2 * r} q0,${r} ${-r},${r} h${-(w - r)} z`;
        return (
          <g key={`${p.label}-${i}`}>
            <title>{`${p.label}: ${formatValore(p.value, d.unit)}`}</title>
            <text x={etichetta - 10} y={y + altezzaBarra / 2 + 4} fill="#d1d5db" fontSize={13} textAnchor="end">
              {p.label.length > (stretto ? 12 : 26) ? `${p.label.slice(0, stretto ? 11 : 25)}…` : p.label}
            </text>
            <path d={path} fill={ACCENTO} />
            <text x={etichetta + w + 8} y={y + altezzaBarra / 2 + 4} fill="#ffffff" fontSize={13} fontFamily="monospace">
              {formatValore(p.value, d.unit)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

function Linea({ d, LARGHEZZA }: { d: ChartData; LARGHEZZA: number }) {
  const stretto = LARGHEZZA < 500;
  const sinistra = stretto ? 44 : 64;
  const destra = stretto ? 30 : 70;
  const cima = 24;
  const basso = 40;
  const altezza = stretto ? 240 : 300;
  const scala = tacche(Math.max(...d.points.map((p) => p.value)));
  const max = scala[scala.length - 1] || 1;
  const n = d.points.length;
  const x = (i: number) => sinistra + (n === 1 ? 0.5 : i / (n - 1)) * (LARGHEZZA - sinistra - destra);
  const y = (v: number) => altezza - basso - (Math.max(v, 0) / max) * (altezza - basso - cima);
  const maggiore = d.points.reduce((a, b, i) => (b.value > d.points[a].value ? i : a), 0);
  const etichettate = new Set([maggiore, n - 1]);
  const passoX = Math.max(1, Math.ceil(n / (stretto ? 4 : 8)));
  return (
    <svg viewBox={`0 0 ${LARGHEZZA} ${altezza}`} width="100%" role="img" aria-label={d.measure} className="block">
      {scala.map((t) => (
        <g key={t}>
          <line x1={sinistra} x2={LARGHEZZA - destra} y1={y(t)} y2={y(t)} stroke={GRIGLIA} strokeWidth={1} />
          <text x={sinistra - 8} y={y(t) + 4} fill={TESTO} fontSize={11} textAnchor="end" fontFamily="monospace">
            {formatValore(t)}
          </text>
        </g>
      ))}
      {d.points.map((p, i) =>
        i % passoX === 0 || i === n - 1 ? (
          <text key={`x${i}`} x={x(i)} y={altezza - basso + 20} fill={TESTO} fontSize={11} textAnchor="middle" fontFamily="monospace">
            {p.label}
          </text>
        ) : null
      )}
      <polyline
        points={d.points.map((p, i) => `${x(i)},${y(p.value)}`).join(' ')}
        fill="none"
        stroke={ACCENTO}
        strokeWidth={2}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      {d.points.map((p, i) => (
        <g key={`p${i}`}>
          <title>{`${p.label}: ${formatValore(p.value, d.unit)}`}</title>
          <circle cx={x(i)} cy={y(p.value)} r={12} fill="transparent" />
          <circle cx={x(i)} cy={y(p.value)} r={4} fill={ACCENTO} stroke="#030508" strokeWidth={2} />
          {etichettate.has(i) ? (
            <text x={x(i)} y={y(p.value) - 12} fill="#ffffff" fontSize={13} textAnchor="middle" fontFamily="monospace">
              {formatValore(p.value, d.unit)}
            </text>
          ) : null}
        </g>
      ))}
    </svg>
  );
}

export function FindingChart({ d }: { d: ChartData }) {
  return (
    <figure className="bg-[#070A10] border border-gray-800 rounded-2xl p-4 sm:p-5">
      <figcaption className="font-mono text-[11px] uppercase tracking-wider text-gray-400 mb-3">{d.measure}</figcaption>
      <div className="hidden sm:block">{d.type === 'bar' ? <Barre d={d} LARGHEZZA={LARGO} /> : <Linea d={d} LARGHEZZA={LARGO} />}</div>
      <div className="sm:hidden" aria-hidden>{d.type === 'bar' ? <Barre d={d} LARGHEZZA={STRETTO} /> : <Linea d={d} LARGHEZZA={STRETTO} />}</div>
      {d.note ? <p className="text-xs text-gray-500 mt-3 leading-relaxed">{d.note}</p> : null}
      <details className="mt-3 text-xs">
        <summary className="cursor-pointer font-mono text-gray-500 hover:text-[#00E5FF]">The figures as a table</summary>
        <table className="mt-2 w-full font-mono text-gray-300">
          <tbody>
            {d.points.map((p, i) => (
              <tr key={i} className="border-t border-gray-800/70">
                <td className="py-1 pr-4">{p.label}</td>
                <td className="py-1 text-right text-white">{formatValore(p.value, d.unit)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </figure>
  );
}
