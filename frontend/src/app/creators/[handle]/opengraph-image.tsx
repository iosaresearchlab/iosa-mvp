// FIX-1d: the link preview of a creator page is the card of the record the
// page lists first (the highest VPI observed), from the same read.
import { cardDelRecord, OG_CONTENT_TYPE, OG_SIZE } from '@/lib/og-card';
import { recordDelCreator } from '@/lib/supabase-server';
import { handleDaSlug } from '@/lib/segments';

// Dynamic, so no ISR write; the response carries its own Cache-Control.
export const dynamic = 'force-dynamic';
export const alt = 'IOSA measurements: how far this creator’s videos beat the channel’s usual views';
export const size = OG_SIZE;
export const contentType = OG_CONTENT_TYPE;

export default async function Image({ params }: { params: Promise<{ handle: string }> }) {
  const { handle } = await params;
  const posts = await recordDelCreator(handleDaSlug(handle));
  return cardDelRecord(posts[0] ?? null);
}
