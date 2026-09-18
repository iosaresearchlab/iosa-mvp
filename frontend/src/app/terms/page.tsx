'use client';

import React from 'react';

export default function TermsPage() {
  const handlePrint = () => {
    if (typeof window !== 'undefined') {
      window.print();
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans p-6 md:p-12">
      {/* Stili dedicati alla stampa PDF */}
      <style jsx global>{`
        @media print {
          body {
            background: #ffffff !important;
            color: #000000 !important;
          }
          .no-print {
            display: none !important;
          }
          .print-container {
            box-shadow: none !important;
            border: none !important;
            padding: 0 !important;
            background: #ffffff !important;
            color: #000000 !important;
          }
          h1, h2, strong {
            color: #000000 !important;
          }
          p, li {
            color: #333333 !important;
          }
        }
      `}</style>

      <div className="max-w-4xl mx-auto bg-slate-900 border border-slate-800 rounded-xl p-8 md:p-12 shadow-2xl print-container">
        {/* Intestazione e Pulsante Stampa */}
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center border-b border-slate-800 pb-6 mb-8 gap-4">
          <div>
            <span className="text-xs font-mono tracking-widest text-emerald-400 uppercase">IOSA Research Lab</span>
            <h1 className="text-3xl font-bold mt-1 text-white">Terms of Service</h1>
            <p className="text-xs text-slate-400 mt-1">Ultimo aggiornamento: 18 Settembre 2026</p>
          </div>
          <button
            onClick={handlePrint}
            className="no-print inline-flex items-center gap-2 bg-emerald-500 hover:bg-emerald-600 text-slate-950 font-semibold px-4 py-2.5 rounded-lg transition-all text-sm shadow-md cursor-pointer"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z" />
            </svg>
            Scarica / Stampa PDF
          </button>
        </div>

        {/* Testo dei Termini Completo */}
        <div className="space-y-8 text-slate-300 text-sm leading-relaxed">
          <section>
            <h2 className="text-lg font-semibold text-white mb-3">1. Accettazione dei Termini</h2>
            <p>
              Accedendo e utilizzando la piattaforma gestita da <strong>IOSA Research Lab</strong> (di seguito "IOSA" o "Servizio"), l'utente accetta integralmente i presenti Termini di Servizio. Se non si concordano i presenti termini, si è invitati a non utilizzare la piattaforma.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">2. Descrizione del Servizio e Indice VPI</h2>
            <p>
              IOSA è un laboratorio analitico indipendente che monitora le tendenze e gli stacchi statistici di performance dei contenuti digitali (Shorts e video) erogati su piattaforme social tramite l'indice proprietario <strong>VPI (Viral Performance Index)</strong>. I report generati hanno natura informativa e di ricerca Open Data.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">3. Utilizzo Consentito e Licenza Open Data</h2>
            <p className="mb-2">
              I report, i dati aggregati e le certificazioni numeriche messe a disposizione da IOSA sono fruibili dagli utenti e dai creator per scopi personali, analitici o scientifici.
            </p>
            <ul className="list-disc pl-5 space-y-1 text-slate-300">
              <li>L'utente si impegna a non manipolare o falsificare le metriche di accreditamento fornite dal sistema.</li>
              <li>È vietato l'utilizzo del servizio per attività dannose, spam o violazioni dei Termini delle piattaforme social di terze parti.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">4. Proprietà Intellettuale e Marchi Terzi</h2>
            <p>
              Tutti i marchi, i loghi e le denominazioni commerciali relativi a YouTube, TikTok, Google o altre piattaforme appartengono ai rispettivi proprietari. IOSA Research Lab è un ente di analisi indipendente e non è affiliato, sponsorizzato o approvato ufficialmente da ByteDance Ltd., TikTok Inc., Google LLC o YouTube LLC.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">5. Esclusione di Garanzie e Limitazione di Responsabilità</h2>
            <p>
              Il Servizio viene fornito "così com'è" ("as is") e "in base alla disponibilità". IOSA non rilascia alcuna garanzia circa la continuità ininterrotta dell'accesso alle API terze o la totale assenza di discrepanze nelle metriche fornite dalle fonti esterne. In nessun caso IOSA sarà responsabile per danni diretti o indiretti derivanti dall'uso o dall'impossibilità di usare il servizio.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">6. Politica di Ritiro e Opt-Out</h2>
            <p>
              Qualsiasi creator che desideri rimuovere permanentemente il proprio account o i propri contenuti dagli indici di tracciamento di IOSA può farlo inviando una richiesta via e-mail all'indirizzo: <a href="mailto:optout@iosaresearch.com" className="text-emerald-400 font-medium underline">optout@iosaresearch.com</a>. La richiesta verrà lavorata nei tempi tecnici strettamente necessari.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">7. Modifiche ai Termini</h2>
            <p>
              IOSA si riserva il diritto di aggiornare o modificare i presenti Termini in qualsiasi momento per adeguarli a novità legislative o aggiornamenti delle API delle piattaforme partner. La data dell'ultimo aggiornamento viene riportata in testa al documento.
            </p>
          </section>

          <section className="border-t border-slate-800 pt-6">
            <h2 className="text-lg font-semibold text-white mb-2">8. Contatti</h2>
            <p>
              Per informazioni o comunicazioni legali sui Termini di Servizio, scrivi a: <strong>optout@iosaresearch.com</strong>.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}