// FIX-1a (20/10/2026): the claim page shows the plaque live
// (components/LivePlaque.tsx); PNGs are rendered by
// .github/workflows/plaques.yml and served from the Storage archive (bucket
// "targhe"). The backend never renders on Render.

// The one mug sample in the archive. Its name follows the sample image
// (backend plaque_spec.mug_archive_name); tests/test_fix1a_plaques.py checks
// that the two agree.
export const MUG_SAMPLE_FILE = 'mug_080e8e40.png';

export function archivedPlaqueUrl(file: string): string {
  const base = (process.env.NEXT_PUBLIC_SUPABASE_URL || '').replace(/\/+$/, '');
  return `${base}/storage/v1/object/public/targhe/${file}`;
}
