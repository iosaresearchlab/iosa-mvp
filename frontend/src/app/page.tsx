'use client';

import { Suspense, useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import ContenutoMetodologia from '@/components/MetodologiaModal';
import { DisclosureBox } from '@/components/DisclosureBox';
import HomeArchive, { SearchBox } from '@/components/HomeArchive';
import type { Vista } from '@/lib/home-query';
import {
  Award,
  BarChart3,
  Zap,
  ArrowDown,
  ArrowUp,
  X,
  Calendar,
  HelpCircle,
  Mail,
  ShieldCheck,
  FileText,
  Info,
  CheckCircle2,
  Building2,
  Trophy,
} from 'lucide-react';
import { INDEX_START_DATE } from '@/lib/index-start';

// La home e' la nostra classifica generale (docs/02 §6.2): l'unione delle
// classifiche di categoria ordinata per views, con il VPI di ogni video
// accanto. L'archivio e' paginato sul server (UI-3, components/HomeArchive).

type ModalType = 'faq' | 'methodology' | null;

export default function Home() {
  const [totale, setTotale] = useState<{ n: number; vista: Vista } | null>(null);
  const [activeModal, setActiveModal] = useState<ModalType>(null);
  const [showScrollTop, setShowScrollTop] = useState<boolean>(false);
  const suTotale = useCallback((n: number, vista: Vista) => setTotale({ n, vista }), []);

  useEffect(() => {
    document.title = 'IOSA — Viral Performance Index';
  }, []);

  useEffect(() => {
    const handleScroll = () => setShowScrollTop(window.scrollY > 300);
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  // Legge l'hash dell'URL all'avvio per aprire automaticamente la modale corrispondente
  useEffect(() => {
    const hash = window.location.hash.replace('#', '');
    if (hash === 'faq' || hash === 'methodology') {
      setActiveModal(hash as ModalType);
    }
  }, []);

  const scrollToTop = () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const scrollToDirectory = () => {
    document.getElementById('directory-table')?.scrollIntoView({ behavior: 'smooth' });
  };

  const scrollToHowItWorks = () => {
    document.getElementById('how-it-works')?.scrollIntoView({ behavior: 'smooth' });
  };

  return (
    <main className="min-h-screen bg-[#030508] text-white font-sans relative flex flex-col justify-between">
      {/* Fixed Navigation Header - Ottimizzato in altezza con collegamenti a Leaderboard e Insights */}
      <header className="fixed top-0 left-0 right-0 z-50 bg-[#030508]/90 backdrop-blur-md border-b border-gray-800/80 px-4 md:px-10 py-2 flex justify-between items-center">
        <div className="flex items-center gap-2.5">
          <svg className="h-5 w-3 text-[#00E5FF]" viewBox="0 0 18.5 32" fill="none">
            <path
              d="M1 26.5H6.5L14 8.5L17.5 14"
              stroke="currentColor"
              strokeWidth="3.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <circle cx="14" cy="3" r="3" fill="#00E5FF" />
          </svg>
          <div className="flex flex-col">
            <span className="font-mono font-black text-base tracking-tighter text-white leading-none">
              IOSA
            </span>
            <span className="text-[7px] font-mono text-gray-400 tracking-widest uppercase opacity-80">
              Institute for Open Social Analytics
            </span>
          </div>
        </div>

        <div className="flex items-center gap-1.5 md:gap-2">
          {/* Collegamenti diretti alle nuove viste */}
          <Link
            href="/leaderboard"
            className="flex items-center gap-1 bg-cyan-950/60 hover:bg-cyan-900/80 border border-cyan-500/40 px-2.5 py-1 rounded-full text-cyan-300 font-mono text-xs transition-colors cursor-pointer"
          >
            <Trophy className="w-3.5 h-3.5 text-[#00E5FF]" />
            <span className="hidden sm:inline">Top 10</span>
          </Link>


          <button
            onClick={() => setActiveModal('faq')}
            className="flex items-center gap-1 bg-gray-900 hover:bg-gray-800 border border-gray-700 px-2.5 py-1 rounded-full text-gray-200 font-mono text-xs transition-colors cursor-pointer"
          >
            <HelpCircle className="w-3.5 h-3.5 text-[#00E5FF]" />
            <span className="hidden sm:inline">FAQ</span>
          </button>

          <button
            onClick={scrollToHowItWorks}
            className="hidden sm:flex items-center gap-1 bg-cyan-950/40 hover:bg-cyan-900/60 border border-cyan-500/30 px-2.5 py-1 rounded-full text-cyan-300 font-mono text-xs transition-colors cursor-pointer"
          >
            <Info className="w-3.5 h-3.5 text-[#00E5FF]" />
            <span>Method</span>
          </button>

          <div className="hidden lg:flex items-center gap-1.5 bg-emerald-950/40 border border-emerald-500/30 px-2.5 py-1 rounded-full text-emerald-400 font-mono text-xs">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
            </span>
            <span className="font-bold text-[9px] tracking-wider">LIVE</span>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <div className="pt-14 pb-5 px-3 md:px-8 max-w-6xl mx-auto space-y-2 flex-grow w-full">
        
        {/* Perimeter notice: stated on the front page, not in a footnote (27/09/2026) */}
        <section
          data-perimeter-notice
          className="border border-amber-500/50 bg-amber-950/40 rounded-xl p-3 px-4 font-sans"
        >
          <p className="text-xs md:text-sm text-amber-200 leading-relaxed">
            <strong className="text-amber-300">For now the index measures long-form videos only (over 3 minutes). Shorts are not measured.</strong>{' '}
            The daily API quota cannot cover a baseline for every Short that enters the charts, so
            Shorts are out of scope until the budget allows. The charts are still read in full.
          </p>
          <p className="text-xs text-amber-200/90 leading-relaxed mt-1">
            {INDEX_START_DATE
              ? `The published series starts on ${INDEX_START_DATE}.`
              : 'The published series has not started yet: it starts with the first complete reading under this perimeter, and its date will be shown here.'}
          </p>
        </section>

        {/* Top Section: WHO WE ARE */}
        <section className="bg-gradient-to-r from-cyan-950/60 via-black to-cyan-950/60 border border-cyan-500/30 rounded-xl p-3 px-4 shadow-md font-sans">
          <div className="flex items-center gap-2 mb-1">
            <Building2 className="w-4 h-4 text-[#00E5FF] shrink-0" />
            <span className="text-[11px] font-mono font-bold tracking-widest text-[#00E5FF] uppercase">
              WHO WE ARE
            </span>
          </div>
          <p className="text-xs md:text-xs text-gray-300 leading-relaxed font-sans">
            The Institute for Open Social Analytics (IOSA) is an independent, self-funded research project with no profit purpose, measuring public social media metrics against each channel&apos;s own statistical baseline. Trend data is open access. Optional commemorative items fund our servers, API quota and development. IOSA is fully independent and is not affiliated, endorsed, associated, or partnered with YouTube, TikTok, Instagram, X (Twitter), or Meta.
          </p>
        </section>

        {/* Hero Section */}
        <section className="bg-gradient-to-b from-[#0B101B] to-[#070A10] border border-gray-800 rounded-xl p-3.5 md:p-5 relative shadow-xl">
          <div className="absolute inset-0 rounded-xl overflow-hidden pointer-events-none">
            <div className="absolute top-0 right-0 w-64 h-64 bg-[#00E5FF]/10 rounded-full blur-3xl" />
          </div>

          <div className="relative z-10 max-w-4xl mx-auto text-center">
            <div className="inline-flex items-center gap-1.5 text-[10px] font-mono text-cyan-300 bg-cyan-950/50 border border-cyan-500/30 px-3 py-0.5 rounded-full mb-2">
              <Calendar className="w-3 h-3 text-[#00E5FF]" />
              <span>One reading a day: <strong className="text-white">23:59 UTC</strong></span>
            </div>

            <h1 className="text-xl md:text-2xl font-black font-mono tracking-tight text-white mb-1 leading-tight">
              Did Your Content Outperform Statistical Baselines?
            </h1>

            <p className="text-gray-400 text-xs md:text-xs leading-relaxed mb-3 font-sans max-w-2xl mx-auto">
              Search a handle or a video link among the long-form videos first observed in YouTube&apos;s Most Popular charts.
            </p>

            {/* Search: writes q into the URL, the archive below reads it (UI-3) */}
            <div className="relative max-w-xl mx-auto z-30 mb-3.5">
              <Suspense fallback={<div className="h-[38px] rounded-xl border border-cyan-500/50 bg-black/90" />}>
                <SearchBox />
              </Suspense>
              <button type="button" onClick={scrollToDirectory}
                className="mt-1.5 text-[10px] font-mono text-[#00E5FF] hover:underline inline-flex items-center gap-1">
                Jump to the index <ArrowDown className="w-3 h-3" aria-hidden />
              </button>
            </div>

            {/* VPI Formula & Key Stats Box Grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 font-mono text-center w-full border-t border-gray-800/80 pt-3 bg-black/40 p-2.5 rounded-xl border border-gray-800/60">
              <div className="flex flex-col justify-center items-center border-r border-gray-800/80 pr-2">
                <div className="text-[9px] text-gray-400 uppercase tracking-wider mb-0.5">
                  VPI FORMULA
                </div>
                <div className="text-xs md:text-sm font-black text-[#00E5FF] font-mono">
                  VPI = E<sub>act</sub> / E<sub>base</sub>
                </div>
              </div>

              <div className="flex flex-col justify-center items-center md:border-r border-gray-800/80 pr-2">
                <div className="text-[9px] text-gray-400 uppercase tracking-wider mb-0.5">{!totale || totale.vista === 'charting' ? 'IN MOST POPULAR NOW' : totale.vista === 'left' ? 'LEFT MOST POPULAR' : 'RECORDS'}</div>
                <div className="text-sm md:text-base font-black text-white">{totale ? totale.n.toLocaleString('en-US') : '\u2014'}</div>
              </div>

              <div className="flex flex-col justify-center items-center border-r border-gray-800/80 pr-2">
                <div className="text-[9px] text-gray-400 uppercase tracking-wider mb-0.5">ORDERED BY</div>
                <div className="text-sm md:text-base font-black text-[#00E5FF]">VIEWS</div>
              </div>

              <div className="flex flex-col justify-center items-center">
                <div className="text-[9px] text-gray-400 uppercase tracking-wider mb-0.5">NODE STATUS</div>
                <div className="text-sm md:text-base font-black text-emerald-400">ACTIVE</div>
              </div>
            </div>

          </div>
        </section>

        {/* APP-6: how to read a level, live day-1 figures per baseline band */}
        <DisclosureBox />

        {/* The index: server-side pages, filters and counts (UI-3) */}
        <Suspense fallback={<div className="h-[600px] rounded-xl border border-gray-800 bg-[#070A10]" />}>
          <HomeArchive onTotale={suTotale} />
        </Suspense>

        {/* How It Works Section - Aggiornato con la nuova metodologia di campionamento trasparente */}
        <section id="how-it-works" className="pt-2">
          <div className="text-center mb-2.5">
            <h2 className="text-[9px] font-mono tracking-widest text-[#00E5FF] uppercase font-bold mb-0.5">
              HOW THE INDEX IS BUILT
            </h2>
            <p className="text-sm md:text-base font-extrabold font-mono text-white">
              A full reading of 34 countries and the 13 category charts that return data
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5">
            <div className="bg-[#070A10] border border-gray-800 p-3 rounded-xl relative overflow-hidden">
              <Zap className="w-4 h-4 text-[#00E5FF] mb-1.5" />
              <h3 className="font-bold text-xs text-white mb-1 font-mono">1. One reading a day</h3>
              <p className="text-[11px] text-gray-400 leading-relaxed font-sans">
                Every day at 23:59 UTC we read every Most Popular category chart of 34 countries through the official YouTube Data API v3. For now a record opens only for long-form videos (over 3 minutes). A video enters the index the first day we observe it in a chart.
              </p>
            </div>

            <div className="bg-[#070A10] border border-gray-800 p-3 rounded-xl relative overflow-hidden">
              <BarChart3 className="w-4 h-4 text-[#00E5FF] mb-1.5" />
              <h3 className="font-bold text-xs text-white mb-1 font-mono">2. Against its own channel</h3>
              <p className="text-[11px] text-gray-400 leading-relaxed font-sans">
                VPI divides a video&apos;s views by the median of the same channel&apos;s videos of the same format, published 7 to 90 days before it. Nothing is filtered on VPI: every video we observe is recorded.
              </p>
            </div>

            <div className="bg-[#070A10] border border-gray-800 p-3 rounded-xl relative overflow-hidden">
              <Award className="w-4 h-4 text-[#00E5FF] mb-1.5" />
              <h3 className="font-bold text-xs text-white mb-1 font-mono">3. Rankings</h3>
              <p className="text-[11px] text-gray-400 leading-relaxed font-sans">
                The ranking by VPI is read on the first day each video is observed, the one reading every record has. VPI is not age-adjusted.
              </p>
            </div>
          </div>
        </section>
      </div>

      {/* Floating Scroll to Top Button */}
      {showScrollTop && (
        <button
          onClick={scrollToTop}
          className="fixed bottom-6 left-1/2 -translate-x-1/2 z-40 bg-white/10 backdrop-blur-md border border-white/20 hover:bg-white/20 text-white p-3 rounded-full shadow-lg transition-all cursor-pointer flex items-center justify-center"
          aria-label="Scroll to top"
        >
          <ArrowUp className="w-5 h-5 text-[#00E5FF]" />
        </button>
      )}

      {/* Pop-up Dialog Modals (FAQ, Methodology) */}
      {activeModal && (
        <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in">
          <div className="bg-[#0B101B] border border-cyan-500/50 rounded-2xl max-w-xl w-full p-5 max-h-[85vh] overflow-y-auto relative shadow-2xl">
            <button
              onClick={() => setActiveModal(null)}
              className="absolute top-4 right-4 p-1 text-gray-400 hover:text-white font-mono cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>

            {/* FAQ Modal */}
            {activeModal === 'faq' && (
              <>
                <div className="flex items-center gap-2 text-[#00E5FF] font-mono text-xs font-bold mb-1">
                  <ShieldCheck className="w-4 h-4" /> TRANSPARENCY & GOVERNANCE FAQ
                </div>

                <h2 className="text-xl font-bold font-mono text-white mb-4">
                  Frequently Asked Questions
                </h2>

                <div className="space-y-4 font-sans text-xs">
                  <div className="bg-black/40 border border-gray-800 p-3.5 rounded-xl">
                    <h3 className="font-bold text-white text-sm font-mono mb-1 flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4 text-[#00E5FF]" /> Are digital metric cards really 100% free?
                    </h3>
                    <p className="text-gray-300 leading-relaxed">
                      Yes, absolutely. Generating, viewing, and downloading digital metric cards and summary graphics is completely free forever.
                    </p>
                  </div>

                  <div className="bg-black/40 border border-gray-800 p-3.5 rounded-xl">
                    <h3 className="font-bold text-white text-sm font-mono mb-1 flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4 text-[#00E5FF]" /> Is IOSA affiliated with YouTube, TikTok, or Meta?
                    </h3>
                    <p className="text-gray-300 leading-relaxed">
                      No. IOSA is an independent third-party research project. We process publicly accessible data to provide objective trend analytics. We are not affiliated with, endorsed by, or officially connected with YouTube, TikTok, Instagram, or Meta.
                    </p>
                  </div>

                  <div className="bg-black/40 border border-gray-800 p-3.5 rounded-xl">
                    <h3 className="font-bold text-white text-sm font-mono mb-1 flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4 text-[#00E5FF]" /> How is the VPI Ratio calculated?
                    </h3>
                    <p className="text-gray-300 leading-relaxed font-mono text-[11px]">
                      VPI = views / channel baseline, within the same format. If a channel&apos;s recent videos have a median of 10,000 views and a video reaches 150,000, its VPI is 15.0x. It is recalculated every day the video stays in Most Popular.
                    </p>
                  </div>

                  <div className="bg-black/40 border border-gray-800 p-3.5 rounded-xl">
                    <h3 className="font-bold text-white text-sm font-mono mb-1 flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4 text-[#00E5FF]" /> Are physical mementos mandatory?
                    </h3>
                    <p className="text-gray-300 leading-relaxed">
                      No. Physical mementos are purely unofficial souvenirs (100% free of platform logos or trademarks) available for creators who wish to celebrate their milestone.
                    </p>
                  </div>
                </div>
              </>
            )}

            {activeModal === 'methodology' && <ContenutoMetodologia />}

            <div className="mt-5 pt-3 border-t border-gray-800 flex justify-end">
              <button
                onClick={() => setActiveModal(null)}
                className="bg-[#00E5FF] hover:bg-cyan-400 text-black font-mono font-bold text-xs px-4 py-2 rounded-lg transition-colors cursor-pointer"
              >
                Got it, Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Institutional Footer */}
      <footer className="w-full bg-[#020305] border-t border-gray-800/80 pt-6 pb-5 px-6 md:px-12 mt-6 text-xs font-mono text-gray-400">
        <div className="max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-4 gap-6 pb-5 border-b border-gray-800/60">
          
          <div className="md:col-span-2 space-y-2">
            <div className="flex items-center gap-2">
              <svg className="h-5 w-3 text-[#00E5FF]" viewBox="0 0 18.5 32" fill="none">
                <path d="M1 26.5H6.5L14 8.5L17.5 14" stroke="currentColor" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round"/>
                <circle cx="14" cy="3" r="3" fill="#00E5FF"/>
              </svg>
              <span className="font-mono font-black text-base text-white">IOSA — Institute for Open Social Analytics</span>
            </div>
            <p className="text-[11px] text-gray-400 font-sans leading-relaxed max-w-md">
              An independent, self-funded research project with no profit purpose, measuring how long-form videos first observed in YouTube&apos;s Most Popular charts perform against each channel&apos;s own baseline.
            </p>
            <div className="flex items-center gap-2 text-[10px] text-[#00E5FF] pt-1">
              <Mail className="w-3.5 h-3.5" />
              <a href="mailto:iosa.research.lab@gmail.com" className="hover:underline">iosa.research.lab@gmail.com</a>
            </div>
          </div>

          <div className="space-y-2">
            <span className="text-white font-bold text-xs tracking-wider uppercase block border-b border-gray-800 pb-1">
              Governance & Legal
            </span>
            <ul className="space-y-2 text-[11px]">
              <li>
                <a href="/privacy.html" target="_blank" rel="noopener noreferrer" className="hover:text-[#00E5FF] transition-colors flex items-center gap-1.5 cursor-pointer text-left">
                  <ShieldCheck className="w-3 h-3 text-cyan-400" /> Privacy Policy
                </a>
              </li>
              <li>
                <a href="/terms.html" target="_blank" rel="noopener noreferrer" className="hover:text-[#00E5FF] transition-colors flex items-center gap-1.5 cursor-pointer text-left">
                  <FileText className="w-3 h-3 text-cyan-400" /> Terms of Service
                </a>
              </li>
              <li>
                <button 
                  onClick={() => setActiveModal('methodology')} 
                  className="hover:text-[#00E5FF] transition-colors flex items-center gap-1.5 cursor-pointer text-left">
                  <Info className="w-3 h-3 text-cyan-400" /> VPI Methodology Standard
                </button>
              </li>
            </ul>
          </div>

          <div className="space-y-2">
            <span className="text-white font-bold text-xs tracking-wider uppercase block border-b border-gray-800 pb-1">
              Community Contact
            </span>
            <p className="text-[10px] text-gray-400 font-sans leading-relaxed">
              Have questions about your VPI record or wish to contribute open analytical nodes?
            </p>
            <a 
              href="mailto:iosa.research.lab@gmail.com"
              className="inline-flex items-center gap-1.5 bg-gray-900 hover:bg-gray-800 text-white border border-gray-700 px-3 py-1.5 rounded-lg text-[10px] font-mono transition-colors"
            >
              <Mail className="w-3 h-3 text-[#00E5FF]" /> iosa.research.lab@gmail.com
            </a>
          </div>

        </div>

        <div className="max-w-6xl mx-auto pt-4 flex flex-col md:flex-row justify-between items-center gap-3 text-[10px] text-gray-400">
          <p className="text-center md:text-left font-sans">
            © 2026 Institute for Open Social Analytics (IOSA). Independent, self-funded research project.
          </p>
          <p className="text-center md:text-right font-sans text-gray-400 max-w-xl">
            Disclaimer: IOSA is an independent analytics project and is not affiliated, endorsed, or partnered with YouTube, TikTok, Instagram, X (Twitter), or Meta.
          </p>
        </div>
      </footer>
    </main>
  );
}