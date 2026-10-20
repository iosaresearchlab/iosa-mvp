// FIX-1d: the link preview (X card) of a claim page is the record's card (lib/og-card).
import { cardDelRecord, OG_CONTENT_TYPE, OG_SIZE, recordDelToken } from '@/lib/og-card';

// Dynamic, so no ISR write; the response carries its own Cache-Control.
export const dynamic = 'force-dynamic';
export const alt = 'IOSA measurement: how far this video beat its channel’s usual views';
export const size = OG_SIZE;
export const contentType = OG_CONTENT_TYPE;

export default async function Image({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  return cardDelRecord(await recordDelToken(token));
}
