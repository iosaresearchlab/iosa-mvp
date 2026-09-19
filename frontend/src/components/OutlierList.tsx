import Link from 'next/link';
import { livelloDiRecord, stileBadge } from '@/lib/vpi-scale';
import { ExternalLink } from 'lucide-react';
import { formatVPI, formatCount } from '@/lib/format';
import type { Post } from '@/lib/supabase-server';
import { slugCreator } from '@/lib/segments';

// Componente server: il markup che produce finisce nell'HTML della risposta,
// quindi e' questo che un motore di ricerca legge davvero.

export function OutlierList({
  posts,
  mostraCreator = true,
}: {
  posts: Post[];
  mostraCreator?: boolean;
}) {
  if (posts.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-gray-500 font-mono">
        No active outliers in this segment right now.
      </p>
    );
  }

  return (
    <ol className="divide-y divide-gray-800/60">
      {posts.map((post, i) => {
        const titolo =
          post.content_text || post.author_name || 'Observed public metric data';
        return (
          <li
            key={post.id}
            className="p-3 flex flex-col md:flex-row md:items-center justify-between gap-3"
          >
            <div className="flex items-center gap-3 min-w-0">
              <div className="font-mono text-gray-600 font-bold text-xs w-10 shrink-0">
                #{i + 1}
              </div>

              <div className="w-14 h-11 rounded-lg bg-black border border-cyan-500/30 flex flex-col items-center justify-center font-mono font-black text-sm text-[#00E5FF] shrink-0">
                {formatVPI(post.vpi_ratio)}
                <span className="text-[7px] text-gray-500 font-normal -mt-0.5">
                  VPI RATIO
                </span>
              </div>

              <div className="min-w-0">
                <div className="flex items-center gap-1.5 mb-0.5 flex-wrap">
                  <span className="text-[8px] font-mono px-1.5 rounded bg-gray-900 text-gray-300 border border-gray-800 uppercase font-bold">
                    {post.platform || 'YOUTUBE'}
                  </span>
                  <span className="text-[8px] font-mono px-1.5 rounded bg-gray-900 text-gray-400 border border-gray-800 uppercase font-bold">
                    {post.format === 'LONG' ? 'Long' : 'Short'}
                  </span>
                  <span
                    className="text-[8px] font-mono px-1.5 py-0.5 rounded font-bold uppercase border"
                    style={stileBadge(livelloDiRecord(post).colore)}
                  >
                    {post.vpi_level_name || livelloDiRecord(post).nome}
                  </span>
                </div>

                <h3 className="font-bold text-xs text-white leading-tight truncate">
                  {titolo}
                </h3>

                <p className="text-[10px] text-gray-400 font-mono truncate">
                  {mostraCreator && post.author_handle ? (
                    <>
                      Creator:{' '}
                      <Link
                        href={`/creators/${slugCreator(post.author_handle)}`}
                        className="text-white font-bold hover:text-[#00E5FF]"
                      >
                        {post.author_handle}
                      </Link>{' '}
                      |{' '}
                    </>
                  ) : null}
                  Baseline: {formatCount(post.baseline_score)} | Recorded:{' '}
                  <span className="text-[#00E5FF] font-bold">
                    {formatCount(post.engagement_score)}
                  </span>
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2 justify-end shrink-0">
              {post.claim_token ? (
                <Link
                  href={`/claim/${post.claim_token}`}
                  className="font-mono font-bold text-[11px] px-3 py-1.5 rounded-lg bg-[#00E5FF] text-black hover:bg-cyan-400 transition-colors"
                >
                  View Analysis
                </Link>
              ) : null}
              {post.post_url ? (
                <a
                  href={post.post_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-label="Open the measured video"
                  className="p-1.5 rounded-lg border border-gray-800 text-gray-400 hover:text-white"
                >
                  <ExternalLink className="w-3.5 h-3.5" />
                </a>
              ) : null}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
