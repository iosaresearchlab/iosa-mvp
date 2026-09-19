import { Calculator } from 'lucide-react';
import { LIVELLI, SOGLIE } from '@/lib/vpi-scale';

/**
 * Il corpo del popup "VPI Methodology Standard".
 *
 * Esisteva in tre copie (home, leaderboard, insights): solo quella della home
 * portava le dieci soglie, le altre due si fermavano alla formula. Chi apriva
 * il popup dalla leaderboard leggeva tre righe e non vedeva mai la scala.
 * Una sola definizione, alimentata da vpi-scale, che a sua volta rispecchia
 * VPI_SCALE in backend/vpi_core.py.
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
        <div className="bg-black/40 border border-cyan-500/30 p-3.5 rounded-xl space-y-2">
          <h3 className="font-bold text-[#00E5FF] font-mono text-xs">Mathematical Formulation</h3>
          <p className="font-mono text-sm text-white bg-black p-2 rounded border border-gray-800 text-center">
            VPI = E<sub>act</sub> / E<sub>base</sub>
          </p>
          <p className="text-[11px] text-gray-400">
            Where <strong>E<sub>act</sub></strong> is the observed public view count within the
            15-day window, and <strong>E<sub>base</sub></strong> is the median view count of the
            channel&apos;s recent videos of the same format — Shorts are compared with Shorts and
            long videos with long videos — taken from the last 90 days and requiring at least 5
            videos.
          </p>
        </div>

        <div className="bg-black/40 border border-gray-800 p-3.5 rounded-xl space-y-2">
          <h3 className="font-bold font-mono text-xs text-[#00E5FF]">
            Outlier Qualification Thresholds (10 Levels)
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
                  {indice === LIVELLI.length - 1
                    ? `VPI < ${SOGLIE[indice - 1]}x`
                    : `VPI ≥ ${SOGLIE[indice]}x`}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-black/40 border border-gray-800 p-3.5 rounded-xl space-y-2">
          <h3 className="font-bold font-mono text-xs text-[#00E5FF]">15-Day Rolling Audit Window</h3>
          <p>
            Posts are monitored continuously across active 15-day windows. Indices are recalculated
            automatically to ensure baseline integrity against artificial spikes. Content with
            VPI &le; 1.0x is excluded from indexing.
          </p>
        </div>
      </div>
    </>
  );
}
