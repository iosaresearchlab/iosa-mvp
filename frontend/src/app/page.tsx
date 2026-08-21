'use client';

import { useState, useEffect, useMemo } from 'react';
import { createClient } from '@supabase/supabase-js';
import {
  Award,
  ExternalLink,
  Filter,
  Globe,
  BarChart3,
  Search,
  Zap,
  Clock,
  Sparkles,
  ArrowDown,
  X,
  Calendar,
  HelpCircle,
} from 'lucide-react';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || '';
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || '';
const supabase = createClient(supabaseUrl, supabaseAnonKey);

export default function Home() {
  const [posts, setPosts] = useState<any[]>([]);
  const [selectedPlatform, setSelectedPlatform] = useState<string>('ALL');
  const [selectedCountry, setSelectedCountry] = useState<string>('ALL');
  const [selectedCategory, setSelectedCategory] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [lastUpdated, setLastUpdated] = useState<string>('');

  const [campaignDates, setCampaignDates] = useState({ start: '', end: '' });

  useEffect(() => {
    // Finestra mobile (rolling window): ultimi 15 giorni rispetto a oggi
    const updateRollingWindow = () => {
      const now = new Date();
      const past15Days = new Date(now.getTime() - 15 * 24 * 60 * 60 * 1000);

      setCampaignDates({
        start: past15Days.toLocaleDateString('it-IT', { day: 'numeric', month: 'short', year: 'numeric' }),
        end: now.toLocaleDateString('it-IT', { day: 'numeric', month: 'short', year: 'numeric' }),
      });
    };

    updateRollingWindow();
  }, []);

  const loadData = async () => {
    try {
      const { data, error } = await supabase
        .from('posts')
        .select('*')
        .gt('vpi_ratio', 1.0)
        .order('vpi_ratio', { ascending: false });

      if (!error && data) {
        setPosts(data);
        setLastUpdated(new Date().toLocaleTimeString());
      }
    } catch (e) {
      console.error('Error loading live data:', e);
    }
  };

  useEffect(() => {
    loadData();

    const interval = setInterval(loadData, 15000);

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
      clearInterval(interval);
      supabase.removeChannel(channel);
    };
  }, []);

  const filteredPosts = useMemo(() => {
    return posts.filter((post) => {
      if (!post.vpi_ratio || Number(post.vpi_ratio) <= 1.0) return false;

      const matchPlatform =
        selectedPlatform === 'ALL' ||
        (post.platform &&
          post.platform.toLowerCase() === selectedPlatform.toLowerCase());
      const matchCountry =
        selectedCountry === 'ALL' ||
        (post.country &&
          post.country.toUpperCase() === selectedCountry.toUpperCase());
      const matchCategory =
        selectedCategory === 'ALL' ||
        (post.category &&
          post.category.toLowerCase() === selectedCategory.toLowerCase());

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

  const avgSpike = useMemo(() => {
    if (posts.length === 0) return '0.0x';
    const total = posts.reduce((acc, p) => acc + Number(p.vpi_ratio || 0), 0);
    return `+${(total / posts.length).toFixed(1)}x`;
  }, [posts]);

  const scrollToDirectory = () => {
    document.getElementById('directory-table')?.scrollIntoView({ behavior: 'smooth' });
  };

  const scrollToHowItWorks = () => {
    document.getElementById('how-it-works')?.scrollIntoView({ behavior: 'smooth' });
  };

  return (
    <main className="min-h-screen bg-[#030508] text-white font-sans relative">
      {/* Header Fisso Ancorato */}
      <header className="fixed top-0 left-0 right-0 z-50 bg-[#030508]/90 backdrop-blur-md border-b border-gray-800/80 px-6 md:px-12 py-3 flex justify-between items-center">
        <div className="flex items-center gap-3">
          <svg
            className="h-7 w-4 text-[#00E5FF]"
            viewBox="0 0 18.5 32"
            fill="none"
          >
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
            <span className="font-mono font-black text-xl tracking-tighter text-white leading-none">
              OSA
            </span>
            <span className="text-[9px] font-mono text-gray-400 tracking-widest uppercase opacity-80">
              Institute for Open Social Analytics
            </span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Pulsante rapido per richiamare la sezione How it Works */}
          <button
            onClick={scrollToHowItWorks}
            className="flex items-center gap-1.5 bg-cyan-950/40 hover:bg-cyan-900/60 border border-cyan-500/30 px-3 py-1 rounded-full text-cyan-300 font-mono text-xs transition-colors cursor-pointer"
          >
            <HelpCircle className="w-3.5 h-3.5 text-[#00E5FF]" />
            <span>How it works</span>
          </button>

          <div className="flex items-center gap-2 bg-emerald-950/40 border border-emerald-500/30 px-3 py-1 rounded-full text-emerald-400 font-mono text-xs">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
            </span>
            <span className="font-bold text-[11px] tracking-wider">LIVE MONITORING</span>
          </div>
        </div>
      </header>

      {/* Spaziatura pt-24 per adattarsi all'header */}
      <div className="pt-24 pb-12 px-4 md:px-8 max-w-6xl mx-auto space-y-6">
        
        {/* Banner Periodo di Rilevazione (Rolling Window) */}
        <div className="bg-gradient-to-r from-cyan-950/40 via-blue-950/20 to-cyan-950/40 border border-cyan-500/30 rounded-xl p-3 text-center text-xs font-mono text-cyan-300 flex items-center justify-center gap-2 shadow-lg">
          <Calendar className="w-4 h-4 text-[#00E5FF] shrink-0" />
          <span>
            <strong>ROLLING MONITORING WINDOW:</strong> Active tracking period from <strong>{campaignDates.start}</strong> to <strong>{campaignDates.end}</strong> (15-day rolling validity per post).
          </span>
        </div>

        {/* Hero Banner */}
        <section className="bg-gradient-to-b from-[#0B101B] to-[#070A10] border border-gray-800 rounded-2xl p-6 md:p-8 relative shadow-2xl">
          <div className="absolute inset-0 rounded-2xl overflow-hidden pointer-events-none">
            <div className="absolute top-0 right-0 w-80 h-80 bg-[#00E5FF]/10 rounded-full blur-3xl" />
          </div>

          <div className="relative z-10 max-w-3xl mx-auto text-center">
            <div className="inline-flex items-center gap-2 text-[11px] font-mono text-[#00E5FF] bg-cyan-950/50 border border-cyan-500/30 px-3 py-1 rounded-full mb-3">
              <Sparkles className="w-3 h-3" /> OFFICIAL ALGORITHMIC OUTLIER REGISTRY
            </div>

            <h1 className="text-3xl md:text-4xl font-black font-mono tracking-tight text-white mb-2 leading-tight">
              Did Your Content Break the Algorithm?
            </h1>

            <p className="text-gray-400 text-xs md:text-sm leading-relaxed mb-6 font-sans max-w-xl mx-auto">
              Search your handle or link to verify physical metric accreditation status within the active 15-day window.
            </p>

            {/* Search Box con Dropdown ad alta priorità z-index */}
            <div className="relative max-w-xl mx-auto z-30">
              <div className="relative flex items-center bg-black/90 border border-cyan-500/50 rounded-xl p-2 shadow-2xl focus-within:border-[#00E5FF] transition-all">
                <Search className="w-5 h-5 text-[#00E5FF] ml-2 mr-2" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search handle (e.g. @MrBeast) or video link..."
                  className="w-full bg-transparent text-white placeholder-gray-500 text-sm focus:outline-none font-mono"
                />
                {searchQuery && (
                  <button
                    onClick={() => setSearchQuery('')}
                    className="p-1 text-gray-500 hover:text-white font-mono"
                  >
                    <X className="w-4 h-4" />
                  </button>
                )}
              </div>

              {/* Dropdown Live Search */}
              {searchQuery.trim().length > 0 && (
                <div className="absolute top-full left-0 right-0 mt-2 bg-[#0B101B] border border-cyan-500/50 rounded-xl shadow-2xl z-50 overflow-hidden text-left p-3 animate-in fade-in slide-in-from-top-2">
                  <div className="flex justify-between items-center pb-2 border-b border-gray-800 text-[11px] font-mono text-gray-400">
                    <span>SEARCH RESULTS: <strong className="text-[#00E5FF]">{filteredPosts.length} FOUND</strong></span>
                    <button
                      onClick={scrollToDirectory}
                      className="text-[#00E5FF] hover:underline flex items-center gap-1 font-bold"
                    >
                      Jump to table <ArrowDown className="w-3 h-3" />
                    </button>
                  </div>

                  {filteredPosts.length > 0 ? (
                    <div className="divide-y divide-gray-800/60 max-h-56 overflow-y-auto">
                      {filteredPosts.slice(0, 5).map((post, idx) => (
                        <div key={idx} className="py-2 flex items-center justify-between text-xs hover:bg-black/40 px-1 rounded transition-colors">
                          <div className="truncate mr-2">
                            <span className="font-bold text-white font-mono">{post.author_handle || post.author_name}</span>
                            <p className="text-[10px] text-gray-400 truncate">{post.content_text || post.title}</p>
                          </div>
                          <span className="font-mono text-[#00E5FF] font-bold bg-cyan-950/60 px-2 py-0.5 rounded border border-cyan-500/30 shrink-0">
                            +{Number(post.vpi_ratio || 0).toFixed(1)}x
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="py-3 text-center text-xs text-gray-500 font-mono">
                      No matching registered outliers found.
                    </div>
                  )}
                </div>
              )}
            </div>

            <div className="flex flex-wrap items-center justify-center gap-3 text-[11px] font-mono text-gray-400 mt-4">
              <div className="flex items-center gap-1.5 bg-black/40 px-3 py-1 rounded-md border border-gray-800">
                <Clock className="w-3 h-3 text-[#00E5FF]" />
                <span>LAST SCAN:</span>
                <span className="text-white font-bold">{lastUpdated || 'SYNCING...'}</span>
              </div>
              <div className="flex items-center gap-1.5 bg-black/40 px-3 py-1 rounded-md border border-gray-800">
                <BarChart3 className="w-3 h-3 text-emerald-400" />
                <span>INTERVAL:</span>
                <span className="text-emerald-400 font-bold">15-MIN CYCLES</span>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3 font-mono text-center max-w-2xl mx-auto mt-6 border-t border-gray-800/80 pt-4">
            <div>
              <div className="text-[10px] text-gray-500">INDEXED</div>
              <div className="text-lg font-black text-white mt-0.5">{posts.length}</div>
            </div>
            <div>
              <div className="text-[10px] text-gray-500">AVG SPIKE</div>
              <div className="text-lg font-black text-[#00E5FF] mt-0.5">{avgSpike}</div>
            </div>
            <div>
              <div className="text-[10px] text-gray-500">SYSTEM</div>
              <div className="text-lg font-black text-emerald-400 mt-0.5">ACTIVE</div>
            </div>
          </div>
        </section>

        {/* Filters */}
        <section className="bg-[#070A10] border border-gray-800 rounded-xl p-3 flex flex-wrap items-center justify-between gap-3 font-mono text-xs">
          <div className="flex items-center gap-2 text-gray-400 font-bold uppercase tracking-wider">
            <Filter className="w-3.5 h-3.5 text-[#00E5FF]" /> Filters:
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-1.5 bg-black/60 border border-gray-800 px-2.5 py-1 rounded-lg text-[11px]">
              <span className="text-gray-500">PLATFORM:</span>
              <select
                value={selectedPlatform}
                onChange={(e) => setSelectedPlatform(e.target.value)}
                className="bg-transparent text-white font-bold focus:outline-none cursor-pointer"
              >
                <option value="ALL" className="bg-gray-900">ALL</option>
                <option value="youtube" className="bg-gray-900">YOUTUBE</option>
                <option value="tiktok" className="bg-gray-900">TIKTOK</option>
                <option value="instagram" className="bg-gray-900">INSTAGRAM</option>
                <option value="x" className="bg-gray-900">X / TWITTER</option>
              </select>
            </div>

            <div className="flex items-center gap-1.5 bg-black/60 border border-gray-800 px-2.5 py-1 rounded-lg text-[11px]">
              <Globe className="w-3 h-3 text-gray-500" />
              <span className="text-gray-500">COUNTRY:</span>
              <select
                value={selectedCountry}
                onChange={(e) => setSelectedCountry(e.target.value)}
                className="bg-transparent text-white font-bold focus:outline-none cursor-pointer"
              >
                <option value="ALL" className="bg-gray-900">GLOBAL</option>
                <option value="US" className="bg-gray-900">US</option>
                <option value="IT" className="bg-gray-900">IT</option>
                <option value="GB" className="bg-gray-900">UK</option>
                <option value="DE" className="bg-gray-900">DE</option>
                <option value="JP" className="bg-gray-900">JP</option>
                <option value="IN" className="bg-gray-900">IN</option>
              </select>
            </div>

            <div className="flex items-center gap-1.5 bg-black/60 border border-gray-800 px-2.5 py-1 rounded-lg text-[11px]">
              <span className="text-gray-500">CATEGORY:</span>
              <select
                value={selectedCategory}
                onChange={(e) => setSelectedCategory(e.target.value)}
                className="bg-transparent text-white font-bold focus:outline-none cursor-pointer"
              >
                <option value="ALL" className="bg-gray-900">ALL</option>
                <option value="Tech" className="bg-gray-900">TECH</option>
                <option value="Gaming" className="bg-gray-900">GAMING</option>
                <option value="Music" className="bg-gray-900">MUSIC</option>
                <option value="Sports" className="bg-gray-900">SPORTS</option>
                <option value="Entertainment" className="bg-gray-900">ENTERTAINMENT</option>
                <option value="People" className="bg-gray-900">PEOPLE</option>
              </select>
            </div>
          </div>
        </section>

        {/* Directory Table */}
        <section id="directory-table" className="bg-[#070A10] border border-gray-800 rounded-2xl overflow-hidden shadow-2xl">
          <div className="p-4 border-b border-gray-800 font-mono text-xs text-gray-400 flex justify-between items-center bg-black/40">
            <span>
              ACTIVE REGISTRY ({campaignDates.start} - {campaignDates.end}): <strong className="text-white">{filteredPosts.length} OUTLIERS</strong>
            </span>
            <span className="text-[#00E5FF]">ROLLING 15-DAY WINDOW</span>
          </div>

          <div className="divide-y divide-gray-800/60">
            {filteredPosts.length > 0 ? (
              filteredPosts.map((post, index) => {
                const formattedVpi = Number(post.vpi_ratio || 0).toFixed(1);
                return (
                  <div
                    key={post.id || index}
                    className="p-5 flex flex-col md:flex-row md:items-center justify-between gap-4 hover:bg-gray-900/40 transition-colors"
                  >
                    <div className="flex items-center gap-4">
                      <div className="font-mono text-gray-600 font-bold text-sm w-6">
                        #{index + 1}
                      </div>

                      <div className="w-16 h-12 rounded-xl bg-black border border-cyan-500/30 flex flex-col items-center justify-center font-mono font-black text-base text-[#00E5FF] shadow-lg shadow-cyan-950/40 shrink-0">
                        +{formattedVpi}x
                        <span className="text-[8px] text-gray-500 font-normal -mt-1">
                          VPI RATIO
                        </span>
                      </div>

                      <div>
                        <div className="flex items-center gap-2 mb-1 flex-wrap">
                          <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-gray-900 text-gray-300 border border-gray-800 uppercase font-bold">
                            {post.platform || 'YOUTUBE'}
                          </span>
                          <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-cyan-950/60 text-[#00E5FF] border border-cyan-500/30 font-bold">
                            {post.country || 'GLOBAL'}
                          </span>
                          <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/30 font-bold uppercase">
                            {post.vpi_level_name || 'OUTLIER'}
                          </span>
                        </div>

                        <h3 className="font-bold text-sm text-white mb-0.5 font-sans">
                          {post.content_text ||
                            post.content_title ||
                            post.title ||
                            'Accredited Performance Data'}
                        </h3>

                        <p className="text-[11px] text-gray-400 font-mono">
                          Creator:{' '}
                          <span className="text-white font-bold">
                            {post.author_handle || post.author_name}
                          </span>{' '}
                          | Baseline:{' '}
                          {post.baseline_score
                            ? Number(post.baseline_score).toLocaleString()
                            : 'N/A'}{' '}
                          | Recorded:{' '}
                          <span className="text-[#00E5FF] font-bold">
                            {post.engagement_score
                              ? Number(post.engagement_score).toLocaleString()
                              : 'N/A'}
                          </span>
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 justify-end pt-2 md:pt-0 border-t md:border-t-0 border-gray-800">
                      <a
                        href={`/claim/${post.claim_token}`}
                        className="flex items-center gap-1.5 bg-[#00E5FF] hover:bg-cyan-400 text-black font-mono font-bold text-xs px-3.5 py-2 rounded-lg transition-colors shadow-lg shadow-cyan-950/50"
                      >
                        <Award className="w-3.5 h-3.5" /> Verify & Claim
                      </a>
                      {post.post_url && (
                        <a
                          href={post.post_url}
                          target="_blank"
                          rel="noreferrer"
                          className="p-2 text-gray-400 hover:text-white border border-gray-800 hover:border-gray-700 rounded-lg bg-black/40 transition-colors"
                        >
                          <ExternalLink className="w-3.5 h-3.5" />
                        </a>
                      )}
                    </div>
                  </div>
                );
              })
            ) : (
              <div className="p-12 text-center text-gray-500 font-mono text-xs">
                NO STATISTICAL OUTLIERS MATCHING YOUR SEARCH/FILTERS.
              </div>
            )}
          </div>
        </section>

        {/* How It Works Section (con ID per l'ancoraggio) */}
        <section id="how-it-works" className="pt-6">
          <div className="text-center mb-6">
            <h2 className="text-[10px] font-mono tracking-widest text-[#00E5FF] uppercase font-bold mb-1">
              HOW ACCREDITATION WORKS
            </h2>
            <p className="text-xl font-extrabold font-mono text-white">
              From Algorithmic Spike to Physical Award (15-Day Rolling Window)
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-[#070A10] border border-gray-800 p-5 rounded-xl relative overflow-hidden">
              <Zap className="w-5 h-5 text-[#00E5FF] mb-2" />
              <h3 className="font-bold text-sm text-white mb-1 font-mono">1. Automated Detection</h3>
              <p className="text-xs text-gray-400 leading-relaxed font-sans">
                IOSA engines scan traffic every 15 minutes to detect abnormal view-to-baseline engagement surges within the continuous rolling window.
              </p>
            </div>

            <div className="bg-[#070A10] border border-gray-800 p-5 rounded-xl relative overflow-hidden">
              <BarChart3 className="w-5 h-5 text-[#00E5FF] mb-2" />
              <h3 className="font-bold text-sm text-white mb-1 font-mono">2. VPI Score Indexing</h3>
              <p className="text-xs text-gray-400 leading-relaxed font-sans">
                Content is evaluated using VPI ratio. Hits above 1.0x threshold receive an official token valid for 15 days from publication.
              </p>
            </div>

            <div className="bg-[#070A10] border border-gray-800 p-5 rounded-xl relative overflow-hidden">
              <Award className="w-5 h-5 text-[#00E5FF] mb-2" />
              <h3 className="font-bold text-sm text-white mb-1 font-mono">3. Physical Trophy Claim</h3>
              <p className="text-xs text-gray-400 leading-relaxed font-sans">
                Creators verify ownership within the 15-day validity period to request their physical acrylic award manufactured on demand.
              </p>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}