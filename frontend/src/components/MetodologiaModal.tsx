import { Calculator } from 'lucide-react';
import { LIVELLI, SOGLIE, SOGLIA_MINIMA } from '@/lib/vpi-scale';
import { INDEX_START_DATE } from '@/lib/index-start';
import { DisclosureBox } from '@/components/DisclosureBox';

/**
 * Il corpo del popup "VPI Methodology Standard", riscritto per intero
 * secondo docs/02 §6.5. Una sola definizione, usata da home, leaderboard e
 * insights; le soglie vengono da vpi-scale, che rispecchia VPI_SCALE in
 * backend/vpi_core.py.
 */

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
        <DisclosureBox compatta />
        <div className="bg-black/40 border border-cyan-500/30 p-3.5 rounded-xl space-y-2">
          <h3 className="font-bold text-[#00E5FF] font-mono text-xs">What we measure</h3>
          <p className="font-mono text-sm text-white bg-black p-2 rounded border border-gray-800 text-center">
            VPI = E<sub>act</sub> / E<sub>base</sub>
          </p>
          <p className="text-[11px] text-gray-400">
            <strong>E<sub>act</sub></strong> is the video&apos;s public view count, read once a day
            from the first day we observe it in Most Popular until the day it leaves every chart:
            a daily series, not a single reading. <strong>E<sub>base</sub></strong> is the median
            view count of the same channel&apos;s long-form videos (over 180 seconds) published
            between 7 and 90 days before
            the measured video was published: at least 5 of them, at most 20 spread evenly across
            the window. The baseline is computed once, the first day the video is observed, and
            then frozen. When fewer than 5 such videos exist the record is kept, without a VPI.
          </p>
        </div>

        <div className="bg-black/40 border border-gray-800 p-3.5 rounded-xl space-y-2">
          <h3 className="font-bold font-mono text-xs text-[#00E5FF]">The population</h3>
          <p>
            Long-form videos (over 180 seconds) first observed in YouTube&apos;s Most Popular category
            charts, across 34 countries and the 13 categories that return data. One reading a day,
            at 23:59 UTC, through the official YouTube Data API. &ldquo;First observed&rdquo; is the
            first reading in which a video is present after being absent from the previous one:
            YouTube publishes no entry time. Nothing is filtered on VPI.
          </p>
          <p>
            <strong className="text-white">For now the index does not measure Shorts.</strong> The
            daily API quota cannot pay for a baseline for every Short that enters the charts, and
            a baseline read later would read other view counts, so it would be a different
            measure. The charts are still read in full, Shorts included, and Shorts will return
            when the budget allows. The two formats are never compared or pooled.
          </p>
          <p>
            {INDEX_START_DATE
              ? `The index starts on ${INDEX_START_DATE}. The readings of 25 and 26 September 2026 are reference states, not part of the series. Everything that was in the charts before the start is outside the measurement: we did not observe it arrive.`
              : 'The published series starts with the first complete reading under the current perimeter; its date is published here once that reading has passed its checks. The readings of 25 and 26 September 2026 are reference states only. Everything that was in the charts before the start is outside the measurement: we did not observe it arrive.'}
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
