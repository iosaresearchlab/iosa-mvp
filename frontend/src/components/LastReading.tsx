'use client';

/**
 * "Last reading: <day>, 23:59 UTC" (UI-2, 01/10/2026): il giorno piu' recente
 * il cui censimento e' completo (last_complete_reading()). Ogni lettura
 * appartiene al giorno appena chiuso, letto alle 23:59 UTC.
 */
import { useEffect, useState } from 'react';
import { createClient } from '@supabase/supabase-js';
import { dataBreve } from '@/lib/record-status';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL || '',
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || '',
  { auth: { persistSession: false } }
);

export function LastReading() {
  const [giorno, setGiorno] = useState<string | null>(null);
  useEffect(() => {
    supabase.rpc('last_complete_reading').then(({ data }) => { if (data) setGiorno(String(data)); }, () => {});
  }, []);
  return (
    <span data-last-reading className="whitespace-nowrap">
      {giorno ? `${dataBreve(giorno)}, 23:59 UTC` : '—'}
    </span>
  );
}
