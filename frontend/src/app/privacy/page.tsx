'use client';

import React from 'react';

export default function PrivacyPage() {
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
            <h1 className="text-3xl font-bold mt-1 text-white">Privacy Policy</h1>
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

        {/* Testo Informativo Completo */}
        <div className="space-y-8 text-slate-300 text-sm leading-relaxed">
          <section>
            <h2 className="text-lg font-semibold text-white mb-3">1. Titolare del Trattamento</h2>
            <p>
              Il Titolare del trattamento dei dati è <strong>IOSA Research Lab</strong> (di seguito "IOSA", "Laboratorio" o "noi"), raggiungibile per qualsiasi chiarimento in materia di privacy e protezione dati all’indirizzo e-mail: <a href="mailto:optout@iosaresearch.com" className="text-emerald-400 underline">optout@iosaresearch.com</a>.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">2. Tipologia di Dati Raccolti</h2>
            <p className="mb-2">
              IOSA Research Lab opera come osservatorio scientifico e piattaforma di analisi metrica. Raccogliamo ed elaboriamo esclusivamente metriche aggregate di tipo pubblico fornite dalle API ufficiali delle piattaforme social (inclusi YouTube API Services e TikTok Official API v2):
            </p>
            <ul className="list-disc pl-5 space-y-1 text-slate-300">
              <li><strong>Identificativi pubblici del contenuto:</strong> ID video, URL del post, titolo, descrizione e categoria di appartenenza.</li>
              <li><strong>Identificativi pubblici del creator:</strong> Nome del canale/account, handle pubblico (es. @username) e conteggio pubblico degli iscritti/follower.</li>
              <li><strong>Metriche di performance pubbliche:</strong> Conteggio visualizzazioni (views), interazioni aggregate e timestamp di pubblicazione.</li>
            </ul>
            <p className="mt-2 text-slate-400 text-xs">
              Nota: IOSA non raccoglie né memorizza dati personali sensibili, dati di tracciamento privato, indirizzi IP di utenti terzi o credenziali di accesso.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">3. Finalità del Trattamento e Algoritmo VPI</h2>
            <p className="mb-2">I dati pubblici raccolti vengono elaborati al solo scopo di:</p>
            <ul className="list-disc pl-5 space-y-1 text-slate-300">
              <li>Calcolare l'indice di prestazione relativo <strong>VPI (Viral Performance Index)</strong> basato sulla mediana storica di coorte omogenea (es. confronto di contenuti Short vs Short).</li>
              <li>Rilevare anomalie statistiche positive (outlier di crescita) per fini di ricerca aperta (Open Data).</li>
              <li>Consentire ai creator di verificare la certificazione di performance del proprio contenuto.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">4. Base Giuridica del Trattamento</h2>
            <p>
              Il trattamento si fonda sul <strong>legittimo interesse del Titolare</strong> (Art. 6, par. 1, lett. f del GDPR) al perseguimento di attività di ricerca scientifica, analisi statistica indipendente e sviluppo di modelli metrici per l'ecosistema digitale, utilizzando dati resi manifestamente pubblici dagli stessi interessati o dalle piattaforme erogatrici.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">5. Conservazione dei Dati</h2>
            <p>
              I dati relativi ai contenuti e alle metriche rilevate vengono conservati nei nostri sistemi gestiti tramite infrastrutture protette per un periodo massimo necessario all'analisi delle campagne (di norma 15 giorni per la fase attiva), trascorsi i quali vengono archiviati o disattivati secondo le policy di pulizia automatizzata del database.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">6. Conformità alle Piattaforme Terze (TikTok & YouTube)</h2>
            <p>
              IOSA rispetta pienamente i Termini di Servizio degli sviluppatori di TikTok e i Terms of Service di YouTube API. L'utilizzo di dati provenienti da tali piattaforme si attiene strettamente alle linee guida di utilizzo dei dati pubblici ed erogati via API ufficiali.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">7. Diritti dell'Utente e Diritto di Opt-Out</h2>
            <p className="mb-2">
              In qualità di creator o titolare del canale analizzato, puoi esercitare in qualsiasi momento i diritti previsti dal GDPR (accesso, rettifica, cancellazione, opposizione).
            </p>
            <p>
              Se desideri rimuovere il tuo canale o i tuoi contenuti dalle nostre rilevazioni analitiche, è possibile richiedere l'opt-out immediato inviando una e-mail a: <a href="mailto:optout@iosaresearch.com" className="text-emerald-400 font-medium underline">optout@iosaresearch.com</a> fornendo l'handle del tuo account. Il sistema escluderà permanentemente il profilo dai futuri aggiornamenti.
            </p>
          </section>

          <section className="border-t border-slate-800 pt-6">
            <h2 className="text-lg font-semibold text-white mb-2">8. Contatti</h2>
            <p>
              Per qualsiasi domanda riguardante questa Privacy Policy o le pratiche sulla tutela dei dati, contattaci a: <strong>optout@iosaresearch.com</strong>.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}