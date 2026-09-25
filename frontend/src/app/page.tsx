'use client';

import { useState, useEffect, useMemo } from 'react';
import Link from 'next/link';
import { formatVPI, formatCount } from '@/lib/format';
import { livelloDiRecord, stileBadge } from '@/lib/vpi-scale';
import { PAESI } from '@/lib/segments';

// Nessuna soglia sul VPI (docs/01 §7): l'indice non e' censurato dal basso e
// un record senza baseline calcolabile resta in tabella, senza VPI.
//
// La home e' la nostra classifica generale (docs/02 §6.2): l'unione delle
// classifiche di categoria ordinata per views, con il VPI di ogni video
// accanto. Il dato quantitativo e' di YouTube, quello qualitativo e' nostro.
// Si caricano le prime MAX_RIGHE per views; il conteggio resta esatto.
const MAX_RIGHE = 5000;

type Vista = 'charting' | 'archive';

const CAMPI_HOME =
  'id,external_post_id,platform,format,author_handle,author_name,channel_id,content_text,post_url,country,category,countries,categories,engagement_score,baseline_score,baseline_rule,vpi_ratio,vpi_level,vpi_max,views_max,days_charting,entered_on,left_on,status,claim_token';

// Quante righe si disegnano per volta.
//
// Prima la tabella renderizzava tutti i record insieme: 11.565 righe, circa
// 300.000 nodi DOM e una pagina alta quasi due chilometri sul telefono. Una
// pagina in quelle condizioni non viene nemmeno valutata da un motore di
// ricerca, oltre a essere inusabile.
const PER_PAGINA = 100;
import { createClient } from '@supabase/supabase-js';
import ContenutoMetodologia from '@/components/MetodologiaModal';
import {
  Award,
  ExternalLink,
  Filter,
  Globe,
  BarChart3,
  Search,
  Zap,
  Sparkles,
  ArrowDown,
  ArrowUp,
  X,
  Calendar,
  HelpCircle,
  Heart,
  Mail,
  ShieldCheck,
  FileText,
  Info,
  Download,
  CheckCircle2,
  Building2,
  Trophy,
  TrendingUp,
} from 'lucide-react';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || '';
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || '';
const supabase = createClient(supabaseUrl, supabaseAnonKey);

// English comment: Define active modal state type for transparent user policy dialogs
type ModalType = 'faq' | 'methodology' | null;

// English comment: Level badge styling aligned strictly with the 10-tier high-contrast VPI color hierarchy
export default function Home() {
  const [posts, setPosts] = useState<any[]>([]);
  const [totalIndexed, setTotalIndexed] = useState<number>(0);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [selectedPlatform, setSelectedPlatform] = useState<string>('ALL');
  const [selectedCountry, setSelectedCountry] = useState<string>('ALL');
  const [selectedCategory, setSelectedCategory] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [lastUpdated, setLastUpdated] = useState<string>('');

  const [vista, setVista] = useState<Vista>('charting');
  
  // English comment: Modal management state for transparent governance popups
  const [activeModal, setActiveModal] = useState<ModalType>(null);

  // English comment: State for floating scroll-to-top button visibility
  const [showScrollTop, setShowScrollTop] = useState<boolean>(false);
  const [pagina, setPagina] = useState<number>(1);

  useEffect(() => {
    document.title = 'IOSA — Viral Performance Index';
  }, []);

  function VPILoader() {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-4 space-y-4">
      <div className="relative flex items-center justify-center">
        {/* Anelli animati ad impulso neon */}
        <div className="absolute w-16 h-16 rounded-full bg-[#00E5FF]/20 animate-ping" />
        <div className="absolute w-24 h-24 rounded-full bg-cyan-500/10 animate-pulse" />
        
        {/* Badge Centrale VPI */}
        <div className="relative z-10 w-12 h-12 rounded-xl bg-black border border-[#00E5FF]/50 flex items-center justify-center shadow-[0_0_20px_rgba(0,229,255,0.4)]">
          <span className="text-transparent bg-clip-text bg-gradient-to-tr from-[#00E5FF] via-cyan-300 to-white font-black text-base font-mono">
            VPI
          </span>
        </div>
      </div>

      <div className="text-center space-y-1">
        <p className="text-xs font-mono font-bold tracking-widest text-white uppercase animate-pulse">
          Reading Most Popular...
        </p>
        <p className="text-[10px] text-gray-400 font-mono">
          IOSA Research Lab • one reading a day at 23:59 UTC
        </p>
      </div>
    </div>
  );
  }

  useEffect(() => {
    const handleScroll = () => {
      if (window.scrollY > 300) {
        setShowScrollTop(true);
      } else {
        setShowScrollTop(false);
      }
    };
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

  const loadData = async () => {
    try {
      // Verificato sul progetto: max_rows non e' limitato e la query restituisce
      // tutte le righe. Nessun range, ma chiediamo comunque il conteggio esatto
      // cosi' la statistica resta corretta anche se un domani il tetto cambia.
      let query = supabase
        .from('posts')
        .select(CAMPI_HOME, { count: 'exact' })
        .eq('method_version', 'v2');
      if (vista === 'charting') query = query.eq('status', 'ACTIVE');
      const { data, error, count } = await query
        .order('engagement_score', { ascending: false })
        .range(0, MAX_RIGHE - 1);

      if (!error && data) {
        setPosts(data);
        setTotalIndexed(count ?? data.length);
        setLastUpdated(new Date().toLocaleTimeString());
      }
    } catch (e) {
      console.error('Error loading live data:', e);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();

    // Niente polling: la sottoscrizione realtime basta e non moltiplica
    // le letture Supabase per ogni scheda aperta.
    const channel = supabase
      .channel('schema-db-changes')
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table: 'posts' },
        () => {
          loadData();
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [vista]);

  // Le voci dei filtri si ricavano dai record caricati, non da un elenco
  // scritto a mano. Un elenco fisso si scolla dai dati al primo paese nuovo
  // che il motore trova, e soprattutto offre voci che non restituiscono
  // niente: bastava scrivere "People" al posto di "People & Blogs" perche'
  // quel filtro svuotasse la tabella. Il conteggio accanto al nome dice
  // quante righe ci sono dietro, cosi' una voce vuota non puo' esistere.
  const opzioniFiltri = useMemo(() => {
    // Paese e categoria dagli array: un video presente in piu' fette compare
    // sotto ciascuna (docs/02 §6.1).
    const conta = (chiave: 'platform' | 'countries' | 'categories') => {
      const mappa = new Map<string, number>();
      for (const post of posts) {
        const grezzo = post[chiave];
        const valori: unknown[] = Array.isArray(grezzo) ? grezzo : [grezzo];
        for (const valore of valori) {
          if (typeof valore !== 'string' || !valore.trim()) continue;
          mappa.set(valore, (mappa.get(valore) ?? 0) + 1);
        }
      }
      return Array.from(mappa.entries())
        .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
        .map(([valore, quanti]) => ({ valore, quanti }));
    };
    return {
      piattaforme: conta('platform'),
      paesi: conta('countries'),
      categorie: conta('categories'),
    };
  }, [posts]);

  // Se un valore selezionato sparisce dai dati (un paese che esce dalla
  // finestra di 15 giorni) si torna a TUTTI, altrimenti la tabella resta
  // vuota senza che si capisca perche'.
  useEffect(() => {
    if (!posts.length) return;
    const presente = (elenco: { valore: string }[], scelto: string) =>
      scelto === 'ALL' || elenco.some((o) => o.valore.toLowerCase() === scelto.toLowerCase());
    if (!presente(opzioniFiltri.piattaforme, selectedPlatform)) setSelectedPlatform('ALL');
    if (!presente(opzioniFiltri.paesi, selectedCountry)) setSelectedCountry('ALL');
    if (!presente(opzioniFiltri.categorie, selectedCategory)) setSelectedCategory('ALL');
  }, [opzioniFiltri, posts.length, selectedPlatform, selectedCountry, selectedCategory]);

  const filteredPosts = useMemo(() => {
    return posts.filter((post) => {
      const matchPlatform =
        selectedPlatform === 'ALL' ||
        (post.platform &&
          post.platform.toLowerCase() === selectedPlatform.toLowerCase());
      const matchCountry =
        selectedCountry === 'ALL' ||
        (post.countries || []).some((c: string) => c.toUpperCase() === selectedCountry.toUpperCase());
      const matchCategory =
        selectedCategory === 'ALL' ||
        (post.categories || []).some((c: string) => c.toLowerCase() === selectedCategory.toLowerCase());

      const query = searchQuery.toLowerCase().trim();
      const matchSearch =
        !query ||
        (post.author_handle && post.author_handle.toLowerCase().includes(query)) ||
        (post.author_name && post.author_name.toLowerCase().includes(query)) ||
        (post.content_text && post.content_text.toLowerCase().includes(query)) ||
        (post.post_url && post.post_url.toLowerCase().includes(query));

      return matchPlatform && matchCountry && matchCategory && matchSearch;
    });
  }, [posts, selectedPlatform, selectedCountry, selectedCategory, searchQuery]);

  // Cambiando filtro o ricerca si riparte dalla prima pagina, altrimenti si
  // resta su una pagina che nel nuovo risultato non esiste piu'.
  useEffect(() => {
    setPagina(1);
  }, [selectedPlatform, selectedCountry, selectedCategory, searchQuery]);

  const pagineTotali = Math.max(1, Math.ceil(filteredPosts.length / PER_PAGINA));
  const paginaCorrente = Math.min(pagina, pagineTotali);
  const primoIndice = (paginaCorrente - 1) * PER_PAGINA;
  const postsVisibili = useMemo(
    () => filteredPosts.slice(primoIndice, primoIndice + PER_PAGINA),
    [filteredPosts, primoIndice]
  );

  // La vetrina in alto mostra un record per canale. Senza questo vincolo un
  // broadcaster che pubblica molte clip con la stessa baseline bassa occupa da
  // solo quasi tutte e cinque le posizioni, e la prima cosa che vede chi arriva
  // e' lo stesso programma ripetuto invece di cinque casi diversi.
  // Il vincolo vale solo qui: l'indice completo, il conteggio e l'export
  // restano integrali, perche' togliere record falserebbe il dataset.
  const topCinque = useMemo(() => {
    const visti = new Set<string>();
    const fuori: typeof filteredPosts = [];
    for (const post of filteredPosts) {
      const canale = post.channel_id || post.author_handle || post.id;
      if (visti.has(canale)) continue;
      visti.add(canale);
      fuori.push(post);
      if (fuori.length === 5) break;
    }
    return fuori;
  }, [filteredPosts]);

  const exportToCSV = () => {
    if (!filteredPosts || filteredPosts.length === 0) return;
    // Nessun claim_token nell'export: e' il codice che autorizza il claim del creator.
    const headers = ['Rank by views', 'Platform', 'Format', 'Countries', 'Categories', 'Creator Handle', 'Views', 'Baseline', 'VPI', 'Peak VPI observed', 'Days in Most Popular', 'First observed', 'Baseline rule', 'Post URL'];
    const rows = filteredPosts.map((post, idx) => [
      idx + 1,
      `"${post.platform || ''}"`,
      `"${post.format || ''}"`,
      `"${(post.countries || []).join(' ')}"`,
      `"${(post.categories || []).join(' | ')}"`,
      `"${(post.author_handle || '').replace(/"/g, '""')}"`,
      post.engagement_score ?? '',
      post.baseline_score ?? '',
      post.vpi_ratio ?? '',
      post.vpi_max ?? '',
      post.days_charting ?? '',
      post.entered_on ?? '',
      post.baseline_rule ?? '',
      `"${post.post_url || ''}"`
    ]);

    const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map(e => e.join(','))].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `iosa_outliers_export_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
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

          <Link
            href="/insights"
            className="flex items-center gap-1 bg-gray-900 hover:bg-gray-800 border border-gray-700 px-2.5 py-1 rounded-full text-gray-200 font-mono text-xs transition-colors cursor-pointer"
          >
            <TrendingUp className="w-3.5 h-3.5 text-[#00E5FF]" />
            <span className="hidden sm:inline">Insights</span>
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
              Search a handle or a video link among the videos we observed entering YouTube&apos;s Most Popular charts.
            </p>

            {/* Search Bar Container */}
            <div className="relative max-w-xl mx-auto z-30 mb-3.5">
              <div className="relative flex items-center bg-black/90 border border-cyan-500/50 rounded-xl p-1 shadow-2xl focus-within:border-[#00E5FF] transition-all">
                <Search className="w-4 h-4 text-[#00E5FF] ml-2.5 mr-2" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search handle (e.g. @MrBeast) or video link..."
                  className="w-full bg-transparent text-white placeholder-gray-500 text-xs md:text-sm focus:outline-none font-mono py-1"
                />
                {searchQuery && (
                  <button
                    onClick={() => setSearchQuery('')}
                    className="p-1 text-gray-500 hover:text-white font-mono"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>

              {searchQuery.trim().length > 0 && (
                <div className="absolute top-full left-0 right-0 mt-1.5 bg-[#0B101B] border border-cyan-500/50 rounded-xl shadow-2xl z-50 overflow-hidden text-left p-2.5 animate-in fade-in slide-in-from-top-2">
                  <div className="flex justify-between items-center pb-1.5 border-b border-gray-800 text-[10px] font-mono text-gray-400">
                    <span>SEARCH RESULTS: <strong className="text-[#00E5FF]">{filteredPosts.length} FOUND</strong></span>
                    <button
                      onClick={scrollToDirectory}
                      className="text-[#00E5FF] hover:underline flex items-center gap-1 font-bold"
                    >
                      Jump to table <ArrowDown className="w-3 h-3" />
                    </button>
                  </div>

                  {filteredPosts.length > 0 ? (
                    <div className="divide-y divide-gray-800/60 max-h-48 overflow-y-auto">
                      {topCinque.map((post, idx) => (
                        <div key={idx} className="py-1.5 flex items-center justify-between text-xs hover:bg-black/40 px-1 rounded transition-colors">
                          <div className="truncate mr-2">
                            <span className="font-bold text-white font-mono text-[11px]">{post.author_handle || post.author_name}</span>
                            <p className="text-[9px] text-gray-400 truncate">{post.content_text || post.title}</p>
                          </div>
                          <span className="font-mono text-[#00E5FF] font-bold text-[10px] bg-cyan-950/60 px-1.5 py-0.5 rounded border border-cyan-500/30 shrink-0">
                            {formatVPI(Number(post.vpi_ratio || 0))}
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="py-2.5 text-center text-[10px] text-gray-500 font-mono">
                      No matching registered outliers found.
                    </div>
                  )}
                </div>
              )}
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
                <div className="text-[9px] text-gray-400 uppercase tracking-wider mb-0.5">{vista === 'charting' ? 'CHARTING NOW' : 'RECORDS'}</div>
                <div className="text-sm md:text-base font-black text-white">{totalIndexed || posts.length}</div>
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

        {/* Filter Controls */}
        <section className="bg-[#070A10] border border-gray-800 rounded-lg p-2 flex flex-wrap items-center justify-between gap-2 font-mono text-xs">
          <div className="flex items-center gap-1.5 text-gray-400 font-bold uppercase tracking-wider text-[10px]">
            <Filter className="w-3 h-3 text-[#00E5FF]" /> Filters:
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-1 bg-black/60 border border-gray-800 px-2 py-0.5 rounded-md text-[10px]">
              <span className="text-gray-500">PLATFORM:</span>
              <select
                value={selectedPlatform}
                onChange={(e) => setSelectedPlatform(e.target.value)}
                className="bg-transparent text-white font-bold focus:outline-none cursor-pointer"
              >
                <option value="ALL" className="bg-gray-900">ALL</option>
                {opzioniFiltri.piattaforme.map(({ valore, quanti }) => (
                  <option key={valore} value={valore} className="bg-gray-900">
                    {valore.toUpperCase()} ({quanti})
                  </option>
                ))}
              </select>
            </div>

            <div className="flex items-center gap-1 bg-black/60 border border-gray-800 px-2 py-0.5 rounded-md text-[10px]">
              <Globe className="w-3 h-3 text-gray-500" />
              <span className="text-gray-500">COUNTRY:</span>
              <select
                value={selectedCountry}
                onChange={(e) => setSelectedCountry(e.target.value)}
                className="bg-transparent text-white font-bold focus:outline-none cursor-pointer"
              >
                <option value="ALL" className="bg-gray-900">GLOBAL</option>
                {opzioniFiltri.paesi.map(({ valore, quanti }) => (
                  <option key={valore} value={valore} className="bg-gray-900">
                    {valore.toUpperCase()}
                    {PAESI[valore.toUpperCase()] ? ` \u2014 ${PAESI[valore.toUpperCase()]}` : ''} ({quanti})
                  </option>
                ))}
              </select>
            </div>

            <div className="flex items-center gap-1 bg-black/60 border border-gray-800 px-2 py-0.5 rounded-md text-[10px]">
              <span className="text-gray-500">CATEGORY:</span>
              <select
                value={selectedCategory}
                onChange={(e) => setSelectedCategory(e.target.value)}
                className="bg-transparent text-white font-bold focus:outline-none cursor-pointer"
              >
                <option value="ALL" className="bg-gray-900">ALL</option>
                {opzioniFiltri.categorie.map(({ valore, quanti }) => (
                  <option key={valore} value={valore} className="bg-gray-900">
                    {valore.toUpperCase()} ({quanti})
                  </option>
                ))}
              </select>
            </div>
          </div>
        </section>

        {/* Directory Table */}
        <section id="directory-table" className="bg-[#070A10] border border-gray-800 rounded-xl overflow-hidden shadow-2xl">
          <div className="p-2.5 px-3 border-b border-gray-800 font-mono text-xs text-gray-400 flex flex-wrap justify-between items-center gap-2 bg-black/40">
            <div className="flex items-center gap-2">
              <span className="flex items-center gap-1">
                {(['charting', 'archive'] as Vista[]).map((v) => (
                  <button
                    key={v}
                    onClick={() => { setIsLoading(true); setVista(v); }}
                    className={`px-2 py-0.5 rounded border text-[10px] cursor-pointer ${vista === v ? 'text-black bg-[#00E5FF] border-[#00E5FF]' : 'text-cyan-300 border-cyan-500/30 bg-cyan-950/40'}`}
                  >
                    {v === 'charting' ? 'CHARTING NOW' : 'FULL ARCHIVE'}
                  </button>
                ))}
              </span>
              <span>
                <strong className="text-white">{filteredPosts.length.toLocaleString('en-US')}</strong> videos, by views{' '}
                <Link href="/outliers" className="text-[#00E5FF] hover:underline ml-1">
                  browse by country and category
                </Link>
              </span>
            </div>

            <button
              onClick={exportToCSV}
              className="flex items-center gap-1.5 bg-gray-900 hover:bg-gray-800 border border-gray-700 text-cyan-300 hover:text-white px-2.5 py-1 rounded text-[10px] font-mono transition-colors cursor-pointer"
            >
              <Download className="w-3 h-3 text-[#00E5FF]" />
              <span>Export Dataset (.CSV)</span>
            </button>
          </div>

          <div className="divide-y divide-gray-800/60">
            {isLoading ? (
              <VPILoader />
            ) : filteredPosts.length > 0 ? (
              postsVisibili.map((post, indiceLocale) => {
                const index = primoIndice + indiceLocale;
                const formattedVpi = formatVPI(post.vpi_ratio);
                return (
                  <div
                    key={post.id || index}
                    className="p-3 flex flex-col md:flex-row md:items-center justify-between gap-3 hover:bg-gray-900/40 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <div className="font-mono text-gray-600 font-bold text-xs w-12 min-w-[3rem]">
                        #{index + 1}
                      </div>

                      <div className="w-14 h-11 rounded-lg bg-black border border-cyan-500/30 flex flex-col items-center justify-center font-mono font-black text-sm text-[#00E5FF] shadow-lg shadow-cyan-950/40 shrink-0">
                        {formattedVpi}
                        <span className="text-[7px] text-gray-500 font-normal -mt-0.5">
                          VPI
                        </span>
                      </div>

                      <div>
                        <div className="flex items-center gap-1.5 mb-0.5 flex-wrap">
                          <span className="text-[8px] font-mono px-1.5 py-0.2 rounded bg-gray-900 text-gray-300 border border-gray-800 uppercase font-bold">
                            {post.platform || 'YOUTUBE'}
                          </span>
                          <span className="text-[8px] font-mono px-1.5 py-0.2 rounded bg-gray-900 text-gray-400 border border-gray-800 uppercase font-bold">
                            {post.format === 'LONG' ? 'Long' : 'Short'}
                          </span>
                          <span className="text-[8px] font-mono px-1.5 py-0.2 rounded bg-cyan-950/60 text-[#00E5FF] border border-cyan-500/30 font-bold">
                            {(post.countries || [post.country]).filter(Boolean).join(' ') || 'GLOBAL'}
                          </span>
                          <span
                            className="text-[8px] font-mono px-1.5 py-0.5 rounded font-bold uppercase border"
                            style={stileBadge(livelloDiRecord(post).colore)}
                          >
                            {post.vpi_level_name || livelloDiRecord(post).nome}
                          </span>
                        </div>

                        <h3 className="font-bold text-xs text-white mb-0.5 font-sans leading-tight">
                          {post.content_text ||
                            post.content_title ||
                            post.title ||
                            'Observed Public Metric Data'}
                        </h3>

                        <p className="text-[10px] text-gray-400 font-mono">
                          Creator:{' '}
                          <span className="text-white font-bold">
                            {post.author_handle || post.author_name}
                          </span>{' '}
                          | Baseline:{' '}
                          {post.baseline_score
                            ? formatCount(Number(post.baseline_score))
                            : 'N/A'}{' '}
                          | Views:{' '}
                          <span className="text-[#00E5FF] font-bold">
                            {post.engagement_score
                              ? formatCount(Number(post.engagement_score))
                              : 'N/A'}
                          </span>{' '}
                          | Peak VPI: {formatVPI(post.vpi_max)}{' '}
                          | Days in Most Popular: {post.days_charting ?? 1}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 justify-end pt-2 md:pt-0 border-t md:border-t-0 border-gray-800">
                      <a
                        href={`/claim/${post.claim_token}`}
                        className="flex items-center gap-1.5 bg-[#00E5FF] hover:bg-cyan-400 text-black font-mono font-bold text-xs px-3 py-1.5 rounded-lg transition-colors shadow-lg shadow-cyan-950/50"
                      >
                        <BarChart3 className="w-3.5 h-3.5" /> View Analysis
                      </a>
                      {post.post_url && (
                        <a
                          href={post.post_url}
                          target="_blank"
                          rel="noreferrer"
                          className="p-1.5 text-gray-400 hover:text-white border border-gray-800 hover:border-gray-700 rounded-lg bg-black/40 transition-colors"
                        >
                          <ExternalLink className="w-3.5 h-3.5" />
                        </a>
                      )}
                    </div>
                  </div>
                );
              })
            ) : (
              <div className="p-8 text-center text-gray-500 font-mono text-xs">
                NO RECORDS MATCH YOUR SEARCH OR FILTERS.
              </div>
            )}
          </div>

          {filteredPosts.length > PER_PAGINA && (
            <div className="flex items-center justify-between gap-3 px-3 py-3 border-t border-gray-800/60 font-mono text-[11px]">
              <button
                onClick={() => {
                  setPagina(paginaCorrente - 1);
                  document.getElementById('directory-table')?.scrollIntoView({ behavior: 'smooth' });
                }}
                disabled={paginaCorrente <= 1}
                className="px-3 py-1.5 rounded-lg border border-gray-800 text-gray-300 disabled:opacity-30 disabled:cursor-not-allowed hover:border-cyan-500/40 hover:text-white transition-colors"
              >
                Previous
              </button>

              <span className="text-gray-500">
                {primoIndice + 1}&ndash;{Math.min(primoIndice + PER_PAGINA, filteredPosts.length)}{' '}
                of {filteredPosts.length.toLocaleString('en-US')}
                <span className="hidden sm:inline">
                  {' '}&middot; page {paginaCorrente} of {pagineTotali}
                </span>
              </span>

              <button
                onClick={() => {
                  setPagina(paginaCorrente + 1);
                  document.getElementById('directory-table')?.scrollIntoView({ behavior: 'smooth' });
                }}
                disabled={paginaCorrente >= pagineTotali}
                className="px-3 py-1.5 rounded-lg border border-gray-800 text-gray-300 disabled:opacity-30 disabled:cursor-not-allowed hover:border-cyan-500/40 hover:text-white transition-colors"
              >
                Next
              </button>
            </div>
          )}
        </section>

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
                Every day at 23:59 UTC we read every Most Popular category chart of 34 countries through the official YouTube Data API v3, Shorts and long-form alike. A video enters the index the first day we observe it in a chart.
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
              <h3 className="font-bold text-xs text-white mb-1 font-mono">3. Insights & Rankings</h3>
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
              An independent, self-funded research project with no profit purpose, measuring how short-form content performs against each channel&apos;s own baseline.
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