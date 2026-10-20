// FIX-1a (20/10/2026): plaques are rendered by .github/workflows/plaques.yml
// and served from the Storage archive (bucket "targhe"); the backend answers
// 307 to the archived file or 202 while it is being prepared, and never
// renders on Render.

// The one mug sample in the archive. Its name follows the sample image
// (backend plaque_spec.mug_archive_name); tests/test_fix1a_plaques.py checks
// that the two agree.
export const MUG_SAMPLE_FILE = 'mug_080e8e40.png';

export function archivedPlaqueUrl(file: string): string {
  const base = (process.env.NEXT_PUBLIC_SUPABASE_URL || '').replace(/\/+$/, '');
  return `${base}/storage/v1/object/public/targhe/${file}`;
}

export type PlaqueStatus = 'checking' | 'ready' | 'preparing' | 'unavailable';

// Asks the backend whether the plaque is archived without following the
// redirect: a 307 to the CDN (an opaque redirect here) means ready, 202
// means the next scheduled run renders it.
export async function plaqueStatus(url: string): Promise<PlaqueStatus> {
  try {
    const res = await fetch(url, { redirect: 'manual', cache: 'no-store' });
    if (res.type === 'opaqueredirect' || res.status === 307 || res.status === 200) return 'ready';
    if (res.status === 202) return 'preparing';
    return 'unavailable';
  } catch {
    return 'unavailable';
  }
}
