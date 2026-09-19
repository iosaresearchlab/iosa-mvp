'use client';

import { useState } from 'react';
import { createClient } from '@supabase/supabase-js';
import { Check, Loader2, Mail } from 'lucide-react';

// I gadget non sono acquistabili. Invece di lasciare un banner morto, o di
// raccontare una domanda che non c'e', si raccoglie quella vera: chi lascia
// l'indirizzo e' un dato, e i dati si possono citare.
//
// La tabella waitlist accetta inserimenti dalla chiave pubblica ma non
// letture: gli indirizzi sono dati personali di terzi e non devono poter
// essere riletti da chi apre il sito.

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL || '',
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || ''
);

type Stato = 'pronto' | 'invio' | 'fatto' | 'errore';

export function WaitlistForm({
  claimToken,
  authorHandle,
  source = 'claim',
}: {
  claimToken?: string;
  authorHandle?: string;
  source?: string;
}) {
  const [email, setEmail] = useState('');
  const [stato, setStato] = useState<Stato>('pronto');

  const valida = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email.trim());

  async function invia(e: React.FormEvent) {
    e.preventDefault();
    if (!valida || stato === 'invio') return;
    setStato('invio');

    const { error } = await supabase.from('waitlist').insert({
      email: email.trim().toLowerCase(),
      claim_token: claimToken ?? null,
      author_handle: authorHandle ?? null,
      source,
    });

    // Un doppio invio dello stesso indirizzo viola l'indice unico: per chi
    // scrive e' comunque "sei in lista", non un errore da mostrare.
    if (error && error.code !== '23505') {
      setStato('errore');
      return;
    }
    setStato('fatto');
  }

  if (stato === 'fatto') {
    return (
      <div className="bg-emerald-950/30 border border-emerald-500/40 rounded-xl p-4 flex items-start gap-3">
        <Check className="w-4 h-4 text-emerald-400 mt-0.5 shrink-0" />
        <p className="text-xs font-mono text-emerald-200 leading-relaxed">
          You&#39;re on the list. We&#39;ll write once, when commemorative items are
          back — and never for anything else.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-gray-900/60 border border-gray-700 rounded-xl p-4">
      <div className="flex items-center gap-2 mb-1.5">
        <Mail className="w-3.5 h-3.5 text-[#00E5FF]" />
        <h3 className="font-mono font-bold text-xs text-white uppercase tracking-wider">
          Commemorative items are paused
        </h3>
      </div>
      <p className="text-[11px] text-gray-400 font-mono leading-relaxed mb-3">
        Mugs, prints and plaques are not on sale while we complete the
        non-profit setup. Your digital plaque above stays free, now and always.
        Want one of the physical items when they return? Leave your address and
        we&#39;ll write once.
      </p>

      <form onSubmit={invia} className="flex flex-col sm:flex-row gap-2">
        <input
          type="email"
          required
          value={email}
          onChange={(e) => {
            setEmail(e.target.value);
            if (stato === 'errore') setStato('pronto');
          }}
          placeholder="you@example.com"
          aria-label="Your email address"
          className="flex-1 bg-black/60 border border-gray-700 rounded-lg px-3 py-2 text-xs font-mono text-white placeholder:text-gray-600 focus:outline-none focus:border-[#00E5FF]/60"
        />
        <button
          type="submit"
          disabled={!valida || stato === 'invio'}
          className="flex items-center justify-center gap-1.5 bg-[#00E5FF] hover:bg-cyan-400 disabled:opacity-30 disabled:cursor-not-allowed text-black font-mono font-bold text-xs px-4 py-2 rounded-lg transition-colors"
        >
          {stato === 'invio' ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
          ) : null}
          Notify me
        </button>
      </form>

      {stato === 'errore' ? (
        <p className="mt-2 text-[10px] font-mono text-amber-400">
          That didn&#39;t go through. Try again in a moment.
        </p>
      ) : (
        <p className="mt-2 text-[10px] font-mono text-gray-600">
          One email, only about this. No newsletter, nothing shared with anyone.
        </p>
      )}
    </div>
  );
}
