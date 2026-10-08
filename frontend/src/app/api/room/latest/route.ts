/**
 * The Breakout Room's data, served from Vercel's cache (ROOM-1b, 08/10/2026).
 *
 * The page (/room) reads this route, not the backend: the backend runs on a
 * plan that sleeps after 15 minutes without requests, and it computes the
 * week on the first call after each reading. Vercel's CDN keeps the answer
 * for an hour and, after that, serves the stored copy while it fetches a new
 * one in the background (stale-while-revalidate): no visitor waits for the
 * backend to wake up. The data stays the backend's (GET /api/room/latest,
 * 02 section 6.8), at most an hour behind it. An error is never cached.
 */
export const dynamic = 'force-dynamic';
export const maxDuration = 60;

const BACKEND = (process.env.NEXT_PUBLIC_BACKEND_URL || 'https://iosa-mvp-backend.onrender.com').replace(/\/$/, '');
export const CACHE = 'public, s-maxage=3600, stale-while-revalidate=86400';

export async function GET() {
  try {
    const res = await fetch(`${BACKEND}/api/room/latest`, { cache: 'no-store' });
    if (!res.ok) {
      return new Response(`room data unavailable (${res.status})`, {
        status: 502, headers: { 'Cache-Control': 'no-store' },
      });
    }
    return new Response(await res.text(), {
      status: 200,
      headers: { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': CACHE },
    });
  } catch {
    return new Response('room data unavailable', { status: 502, headers: { 'Cache-Control': 'no-store' } });
  }
}
