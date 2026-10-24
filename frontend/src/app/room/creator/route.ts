/**
 * SOC-W3 (24/10/2026): /room?c=<channel_id> — the Breakout Room with a channel's link preview.
 *
 * /room is the static page public/room/index.html (rewrite in next.config.ts). A link to a
 * channel's cabinet, /room?c=<channel_id>, is rewritten here: the same page, with its title
 * and Open Graph / X tags naming the channel ("<channel name> in The Breakout Room"; image the
 * room's /room/og.png), because a link preview is read from the HTML, not from the page's
 * script. The page itself selects the cabinet from the query (index.html, fromChannel()).
 *
 * The channel's name is one read of public_records (the public view, under its RLS). An
 * unknown or malformed id, or a failed read, serves the page with its own tags: the link
 * still works. Each URL is kept by Vercel's CDN for a day (no ISR write).
 */
import { readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { supabaseServer } from '@/lib/supabase-server';

export const dynamic = 'force-dynamic';

const PAGINA = readFile(join(process.cwd(), 'public/room/index.html'), 'utf8');
const ID = /^UC[A-Za-z0-9_-]{22}$/;
const CACHE = 'public, s-maxage=86400, stale-while-revalidate=604800';

const esc = (s: string) =>
  s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c] as string);

async function nomeDelCanale(id: string): Promise<string | null> {
  try {
    const { data, error } = await supabaseServer
      .from('public_records')
      .select('author_name')
      .eq('channel_id', id)
      .not('author_name', 'is', null)
      .limit(1);
    if (error || !data?.length) return null;
    return (data[0] as { author_name: string | null }).author_name;
  } catch {
    return null;
  }
}

/** The page's head with the channel's title; exported for the test. */
export function conIlCanale(html: string, nome: string, id: string): string {
  const titolo = esc(`${nome} in The Breakout Room`);
  const url = `https://iosaresearch.org/room?c=${encodeURIComponent(id)}`;
  return html
    .replace(/<title>[^<]*<\/title>/, `<title>${titolo}</title>`)
    .replace(/<meta property="og:title" content="[^"]*">/, `<meta property="og:title" content="${titolo}">`)
    .replace(/<meta property="og:url" content="[^"]*">/, `<meta property="og:url" content="${url}">`)
    .replace(
      /<meta name="twitter:card" content="summary_large_image">/,
      `<meta name="twitter:card" content="summary_large_image">\n<meta name="twitter:title" content="${titolo}">`
    );
}

export async function GET(request: Request) {
  const id = new URL(request.url).searchParams.get('c') || '';
  const html = await PAGINA;
  const nome = ID.test(id) ? await nomeDelCanale(id) : null;
  return new Response(nome ? conIlCanale(html, nome, id) : html, {
    headers: { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': CACHE },
  });
}
