import { Calculator } from 'lucide-react';
import { LIVELLI, SOGLIE, SOGLIA_MINIMA } from '@/lib/vpi-scale';

/**
 * Il corpo del popup "VPI Methodology Standard", riscritto per intero
 * secondo docs/02 §6.5. Una sola definizione, usata da home, leaderboard e
 * insights; le soglie vengono da vpi-scale, che rispecchia VPI_SCALE in
 * backend/vpi_core.py.
 */

/**
 * Data di inizio dell'indice (docs/01 §1): il primo giorno 1 riuscito. Si
 * scrive qui nel commit di T-17, insieme a docs/01. Finche' e' null il testo
 * lo dice senza inventare una data.
 */
export const DATA_INIZIO_INDICE: string | null = null;

export default function ContenutoMetodologia() {
  return (
    <>
      <div className="flex items-center gap-2 text-[#00E5FF] font-mono text-xs font-bold mb-1">
        <Calculator className="w-4 h-4 text-[#00E5FF]" /> STATISTICAL AUDIT STANDARD
      </div>

      <h2 className="text-xl font-bold font-mono text-white mb-4">
        VPI Methodology Standard
      </h2>

      <div className="space-y-3 font-sans text-xs text-gray-300 leading-relaxed">
        <div className="bg-black/40 border border-cyan-500/30 p-3.5 rounded-xl space-y-2">
          <h3 className="font-bold text-[#00E5FF] font-mono text-xs">What we measure</h3>
          <p className="font-mono text-sm text-white bg-black p-2 rounded border border-gray-800 text-center">
            VPI = E<sub>act</sub> / E<sub>base</sub>
          </p>
          <p className="text-[11px] text-gray-400">
            <strong>E<sub>act</sub></strong> is the video&apos;s public view count, read once a day
            from the first day we observe it in Most Popular until the day it leaves every chart:
            a daily series, not a single reading. <strong>E<sub>base</sub></strong> is the median
            view count of the same channel&apos;s videos of the same format — Shorts (up to 180
            seconds) with Shorts, long-form with long-form — published between 7 and 90 days before
            the measured video was published: at least 5 of them, at most 20 spread evenly across
            the window. The baseline is computed once, the first day the video is observed, and
            then frozen. When fewer than 5 such videos exist the record is kept, without a VPI.
          </p>
        </div>

        <div className="bg-black/40 border border-gray-800 p-3.5 rounded-xl space-y-2">
          <h3 className="font-bold font-mono text-xs text-[#00E5FF]">The population</h3>
          <p>
            Videos, Shorts and long-form, first observed in YouTube&apos;s Most Popular category
            charts, across 34 countries and the 13 categories that return data. One reading a day,
            at 23:59 UTC, through the official YouTube Data API. &ldquo;First observed&rdquo; is the
            first reading in which a video is present after being absent from the previous one:
            YouTube publishes no entry time. Nothing is filtered on VPI.
          </p>
          <p>
            {DATA_INIZIO_INDICE
              ? `The index starts on ${DATA_INIZIO_INDICE}. Everything that was in the charts before that date is outside the measurement: we did not observe it arrive.`
              : 'The index starts on its first complete day with records; the date is published here once that reading has run. Everything that was in the charts before it is outside the measurement: we did not observe it arrive.'}
          </p>
        </div>

        <div className="bg-black/40 border border-gray-800 p-3.5 rounded-xl space-y-2">
          <h3 className="font-bold font-mono text-xs text-[#00E5FF]">How to read it</h3>
          <p>
            VPI is cumulative and age-dependent. It is recalculated daily while the video remains
            in the observed Most Popular chart, and is interpreted together with the video&apos;s
            age and its days observed in the chart.
          </p>
          <p>
            VPI is not age-adjusted: values observed at different video ages are not directly
            comparable as age-independent measures of performance.
          </p>
          <p>
            The published value is the highest VPI observed, always shown with the view count and
            the number of days in Most Popular. Rankings across videos read the first day each
            video is observed, the one reading every record has.
          </p>
        </div>

        <div className="bg-black/40 border border-gray-800 p-3.5 rounded-xl space-y-2">
          <h3 className="font-bold font-mono text-xs text-[#00E5FF]">
            Levels (10), set by the project owner on 25 September 2026
          </h3>
          <div className="space-y-1.5 font-mono text-[11px] max-h-64 overflow-y-auto pr-1">
            {LIVELLI.map((l, indice) => (
              <div
                key={l.livello}
                className="flex items-center justify-between p-1.5 rounded border"
                style={{ backgroundColor: `${l.colore}1a`, borderColor: `${l.colore}66` }}
              >
                <span className="flex items-center gap-2">
                  <span
                    className="w-2.5 h-2.5 rounded-full shrink-0"
                    style={{ backgroundColor: l.colore, boxShadow: `0 0 8px ${l.colore}cc` }}
                  />
                  <strong style={{ color: l.colore }}>{l.nome.replace(' - ', ' — ')}</strong>
                </span>
                <span className="font-bold" style={{ color: l.colore }}>
                  {`VPI ≥ ${SOGLIE[indice]}x`}
                </span>
              </div>
            ))}
            <p className="text-gray-400 pt-1">
              {`Below ${SOGLIA_MINIMA}x a video keeps its VPI and has no level.`}
            </p>
          </div>
        </div>
      </div>
    </>
  );
}
