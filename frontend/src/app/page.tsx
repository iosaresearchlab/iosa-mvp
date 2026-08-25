'use client';

import { useState, useEffect, useMemo } from 'react';
import Link from 'next/link';
import { createClient } from '@supabase/supabase-js';
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
  Calculator,
  CheckCircle2,
  Building2,
} from 'lucide-react';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || '';
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || '';
const supabase = createClient(supabaseUrl, supabaseAnonKey);

// English comment: Define active modal state type for transparent user policy dialogs
type ModalType = 'faq' | 'privacy' | 'terms' | 'methodology' | null;

// English comment: Level badge styling aligned strictly with the 10-tier high-contrast VPI color hierarchy
function getBadgeStyle(levelName?: string, vpiScore?: any): string {
  let lvl = 0;
  if (levelName) {
    const match = levelName.match(/LVL\s*(\d+)/i);
    if (match) lvl = parseInt(match[1], 10);
  }
  if (!lvl && vpiScore) {
    const v = parseFloat(String(vpiScore).replace(/[^\d.]/g, '')) || 0;
    if (v >= 50.0) lvl = 10;
    else if (v >= 25.0) lvl = 9;
    else if (v >= 15.0) lvl = 8;
    else if (v >= 10.0) lvl = 7;
    else if (v >= 7.5) lvl = 6;
    else if (v >= 5.0) lvl = 5;
    else if (v >= 3.0) lvl = 4;
    else if (v >= 2.0) lvl = 3;
    else if (v >= 1.5) lvl = 2;
    else lvl = 1;
  }

  switch (lvl) {
    case 10:
      // Mythic Gold
      return 'bg-amber-950/60 text-amber-300 border border-amber-300 shadow-[0_0_15px_rgba(255,215,0,0.6)]';
    case 9:
      // Electric Cyan
      return 'bg-cyan-950/50 text-cyan-300 border border-cyan-400 shadow-[0_0_15px_rgba(6,182,212,0.5)]';
    case 8:
      // Deep Violet
      return 'bg-purple-950/70 text-purple-400 border border-purple-700 shadow-[0_0_15px_rgba(124,58,237,0.5)]';
    case 7:
      // Light Pink
      return 'bg-pink-950/50 text-pink-300 border border-pink-400 shadow-[0_0_15px_rgba(244,114,182,0.4)]';
    case 6:
      // Crimson Red
      return 'bg-red-950/50 text-red-400 border border-red-500 shadow-[0_0_15px_rgba(239,68,68,0.4)]';
    case 5:
      // Vibrant Orange
      return 'bg-orange-950/50 text-orange-400 border border-orange-500 shadow-[0_0_15px_rgba(249,115,22,0.4)]';
    case 4:
      // Canary Yellow
      return 'bg-yellow-950/50 text-yellow-400 border border-yellow-500 shadow-[0_0_15px_rgba(234,179,8,0.4)]';
    case 3:
      // Neon Lime
      return 'bg-lime-950/50 text-lime-400 border border-lime-500 shadow-[0_0_15px_rgba(132,204,22,0.4)]';
    case 2:
      // Forest Green
      return 'bg-green-950/80 text-green-500 border border-green-700 shadow-[0_0_15px_rgba(21,128,61,0.4)]';
    case 1:
    default:
      // Slate Gray
      return 'bg-slate-950/50 text-slate-400 border border-slate-600 shadow-[0_0_10px_rgba(100,116,139,0.3)]';
  }
}

export default function Home() {
  const [posts, setPosts] = useState<any[]>([]);
  const [selectedPlatform, setSelectedPlatform] = useState<string>('ALL');
  const [selectedCountry, setSelectedCountry] = useState<string>('ALL');
  const [selectedCategory, setSelectedCategory] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [lastUpdated, setLastUpdated] = useState<string>('');

  const [campaignDates, setCampaignDates] = useState({ start: '', end: '' });
  
  // English comment: Modal management state for transparent governance popups
  const [activeModal, setActiveModal] = useState<ModalType>(null);

  // English comment: State for floating scroll-to-top button visibility
  const [showScrollTop, setShowScrollTop] = useState<boolean>(false);

  useEffect(() => {
    document.title = 'IOSA — Viral Performance Index';
  }, []);

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

  const scrollToTop = () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  useEffect(() => {
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
        .eq('status', 'ACTIVE')
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
      if (post.status && post.status !== 'ACTIVE') return false;
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

  const exportToCSV = () => {
    if (!filteredPosts || filteredPosts.length === 0) return;
    const headers = ['Rank', 'Platform', 'Country', 'Category', 'Creator Handle', 'Creator Name', 'VPI Ratio', 'Baseline Score', 'Recorded Score', 'Post URL', 'Record ID'];
    const rows = filteredPosts.map((post, idx) => [
      idx + 1,
      `"${post.platform || ''}"`,
      `"${post.country || ''}"`,
      `"${post.category || ''}"`,
      `"${(post.author_handle || '').replace(/"/g, '""')}"`,
      `"${(post.author_name || '').replace(/"/g, '""')}"`,
      post.vpi_ratio || 0,
      post.baseline_score || 0,
      post.engagement_score || 0,
      `"${post.post_url || ''}"`,
      `"${post.claim_token || ''}"`
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
      {/* Fixed Navigation Header */}
      <header className="fixed top-0 left-0 right-0 z-50 bg-[#030508]/90 backdrop-blur-md border-b border-gray-800/80 px-4 md:px-10 py-2.5 flex justify-between items-center">
        <div className="flex items-center gap-2.5">
          <svg className="h-6 w-3.5 text-[#00E5FF]" viewBox="0 0 18.5 32" fill="none">
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
            <span className="font-mono font-black text-lg tracking-tighter text-white leading-none">
              IOSA
            </span>
            <span className="text-[8px] font-mono text-gray-400 tracking-widest uppercase opacity-80">
              Institute for Open Social Analytics
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2 md:gap-3">
          <button
            onClick={() => setActiveModal('faq')}
            className="flex items-center gap-1.5 bg-gray-900 hover:bg-gray-800 border border-gray-700 px-3 py-1 rounded-full text-gray-200 font-mono text-xs transition-colors cursor-pointer"
          >
            <HelpCircle className="w-3.5 h-3.5 text-[#00E5FF]" />
            <span className="hidden sm:inline">FAQ & Governance</span>
            <span className="sm:hidden">FAQ</span>
          </button>

          <button
            onClick={scrollToHowItWorks}
            className="flex items-center gap-1.5 bg-cyan-950/40 hover:bg-cyan-900/60 border border-cyan-500/30 px-3 py-1 rounded-full text-cyan-300 font-mono text-xs transition-colors cursor-pointer"
          >
            <Info className="w-3.5 h-3.5 text-[#00E5FF]" />
            <span>How it works</span>
          </button>

          <div className="hidden md:flex items-center gap-2 bg-emerald-950/40 border border-emerald-500/30 px-3 py-1 rounded-full text-emerald-400 font-mono text-xs">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
            </span>
            <span className="font-bold text-[10px] tracking-wider">LIVE MONITORING</span>
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
            The Institute for Open Social Analytics (IOSA) is an independent, non-profit data research initiative dedicated to auditing public social media metrics against statistical baselines. We provide open-access trend data and digital metric verifications. IOSA is fully independent and is not affiliated, endorsed, associated, or partnered with YouTube, TikTok, Instagram, X (Twitter), or Meta.
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
              <span>Rolling Window: <strong className="text-white">{campaignDates.start} — {campaignDates.end}</strong></span>
            </div>

            <h1 className="text-xl md:text-2xl font-black font-mono tracking-tight text-white mb-1 leading-tight">
              Did Your Content Outperform Statistical Baselines?
            </h1>

            <p className="text-gray-400 text-xs md:text-xs leading-relaxed mb-3 font-sans max-w-2xl mx-auto">
              Search handle or URL to view observed public metric data within active 15-day window.
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
                      {filteredPosts.slice(0, 5).map((post, idx) => (
                        <div key={idx} className="py-1.5 flex items-center justify-between text-xs hover:bg-black/40 px-1 rounded transition-colors">
                          <div className="truncate mr-2">
                            <span className="font-bold text-white font-mono text-[11px]">{post.author_handle || post.author_name}</span>
                            <p className="text-[9px] text-gray-400 truncate">{post.content_text || post.title}</p>
                          </div>
                          <span className="font-mono text-[#00E5FF] font-bold text-[10px] bg-cyan-950/60 px-1.5 py-0.5 rounded border border-cyan-500/30 shrink-0">
                            +{Number(post.vpi_ratio || 0).toFixed(1)}x
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
                <div className="text-[9px] text-gray-400 uppercase tracking-wider mb-0.5">INDEXED OUTLIERS</div>
                <div className="text-sm md:text-base font-black text-white">{posts.length}</div>
              </div>

              <div className="flex flex-col justify-center items-center border-r border-gray-800/80 pr-2">
                <div className="text-[9px] text-gray-400 uppercase tracking-wider mb-0.5">AVG SPIKE RATIO</div>
                <div className="text-sm md:text-base font-black text-[#00E5FF]">{avgSpike}</div>
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
                <option value="youtube" className="bg-gray-900">YOUTUBE</option>
                <option value="tiktok" className="bg-gray-900">TIKTOK</option>
                <option value="instagram" className="bg-gray-900">INSTAGRAM</option>
                <option value="x" className="bg-gray-900">X / TWITTER</option>
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
                <option value="US" className="bg-gray-900">US</option>
                <option value="IT" className="bg-gray-900">IT</option>
                <option value="GB" className="bg-gray-900">UK</option>
                <option value="DE" className="bg-gray-900">DE</option>
                <option value="JP" className="bg-gray-900">JP</option>
                <option value="IN" className="bg-gray-900">IN</option>
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
        <section id="directory-table" className="bg-[#070A10] border border-gray-800 rounded-xl overflow-hidden shadow-2xl">
          <div className="p-2.5 px-3 border-b border-gray-800 font-mono text-xs text-gray-400 flex flex-wrap justify-between items-center gap-2 bg-black/40">
            <div className="flex items-center gap-2">
              <span>
                ACTIVE INDEX: <strong className="text-white">{filteredPosts.length} OUTLIERS</strong>
              </span>
              <span className="text-[10px] text-cyan-400 bg-cyan-950/50 px-2 py-0.5 rounded border border-cyan-500/30">
                15-DAY ROLLING
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
            {filteredPosts.length > 0 ? (
              filteredPosts.map((post, index) => {
                const formattedVpi = Number(post.vpi_ratio || 0).toFixed(1);
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
                        +{formattedVpi}x
                        <span className="text-[7px] text-gray-500 font-normal -mt-0.5">
                          VPI RATIO
                        </span>
                      </div>

                      <div>
                        <div className="flex items-center gap-1.5 mb-0.5 flex-wrap">
                          <span className="text-[8px] font-mono px-1.5 py-0.2 rounded bg-gray-900 text-gray-300 border border-gray-800 uppercase font-bold">
                            {post.platform || 'YOUTUBE'}
                          </span>
                          <span className="text-[8px] font-mono px-1.5 py-0.2 rounded bg-cyan-950/60 text-[#00E5FF] border border-cyan-500/30 font-bold">
                            {post.country || 'GLOBAL'}
                          </span>
                          <span className={`text-[8px] font-mono px-1.5 py-0.5 rounded font-bold uppercase ${getBadgeStyle(post.vpi_level_name, post.vpi_ratio)}`}>
                            {post.vpi_level_name || 'LVL 5 — OUTLIER'}
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
                NO STATISTICAL OUTLIERS MATCHING YOUR SEARCH/FILTERS.
              </div>
            )}
          </div>
        </section>

        {/* How It Works Section */}
        <section id="how-it-works" className="pt-2">
          <div className="text-center mb-2.5">
            <h2 className="text-[9px] font-mono tracking-widest text-[#00E5FF] uppercase font-bold mb-0.5">
              INDEPENDENT ANALYTICAL FRAMEWORK
            </h2>
            <p className="text-sm md:text-base font-extrabold font-mono text-white">
              From Algorithmic Surge to Open Statistical Analysis
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5">
            <div className="bg-[#070A10] border border-gray-800 p-3 rounded-xl relative overflow-hidden">
              <Zap className="w-4 h-4 text-[#00E5FF] mb-1.5" />
              <h3 className="font-bold text-xs text-white mb-1 font-mono">1. Open Data Audit</h3>
              <p className="text-[11px] text-gray-400 leading-relaxed font-sans">
                IOSA nodes process publicly available statistical signals every 15 minutes to record organic engagement anomalies against creator historical baselines.
              </p>
            </div>

            <div className="bg-[#070A10] border border-gray-800 p-3 rounded-xl relative overflow-hidden">
              <BarChart3 className="w-4 h-4 text-[#00E5FF] mb-1.5" />
              <h3 className="font-bold text-xs text-white mb-1 font-mono">2. Free Metric Summary</h3>
              <p className="text-[11px] text-gray-400 leading-relaxed font-sans">
                Outliers above threshold receive a unique Record ID valid for 15 days, providing free downloadable metric summary cards.
              </p>
            </div>

            <div className="bg-[#070A10] border border-gray-800 p-3 rounded-xl relative overflow-hidden">
              <Award className="w-4 h-4 text-[#00E5FF] mb-1.5" />
              <h3 className="font-bold text-xs text-white mb-1 font-mono">3. Unofficial Fan-Art & Souvenirs</h3>
              <p className="text-[11px] text-gray-400 leading-relaxed font-sans">
                Creators can request custom artistic mementos (purely unofficial, 100% free of YouTube/TikTok logos or trademarks) to celebrate their milestones.
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

      {/* Pop-up Dialog Modals (FAQ, Privacy, Terms, Methodology) */}
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
                      VPI = Actual Views / Historical Baseline Views. If a creator averages 10,000 views and a video reaches 150,000 views within 15 days, their VPI is 15.0x.
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

            {/* Privacy Policy Modal */}
            {activeModal === 'privacy' && (
              <>
                <div className="flex items-center gap-2 text-[#00E5FF] font-mono text-xs font-bold mb-1">
                  <ShieldCheck className="w-4 h-4 text-emerald-400" /> DATA GOVERNANCE & PRIVACY
                </div>

                <h2 className="text-xl font-bold font-mono text-white mb-4">
                  Privacy Policy
                </h2>

                <div className="space-y-3 font-sans text-xs text-gray-300 leading-relaxed">
                  <div className="bg-black/40 border border-gray-800 p-3.5 rounded-xl space-y-2">
                    <h3 className="font-bold text-white font-mono text-xs text-[#00E5FF]">1. Public Metric Data Processing</h3>
                    <p>
                      IOSA strictly collects and processes publicly visible metrics (view counts, channel handles, publication timestamps) provided directly by social platform APIs. No private personal data, confidential credentials, or tracking cookies are collected.
                    </p>
                  </div>

                  <div className="bg-black/40 border border-gray-800 p-3.5 rounded-xl space-y-2">
                    <h3 className="font-bold text-white font-mono text-xs text-[#00E5FF]">2. Optional Checkout Information</h3>
                    <p>
                      When ordering physical mementos, email and shipping details are processed exclusively via encrypted Stripe checkout endpoints for order fulfillment. We never sell, share, or store financial credentials on our servers.
                    </p>
                  </div>

                  <div className="bg-black/40 border border-gray-800 p-3.5 rounded-xl space-y-2">
                    <h3 className="font-bold text-white font-mono text-xs text-[#00E5FF]">3. Right to Removal & Corrections</h3>
                    <p>
                      Creators wishing to remove their public record index or update verified parameters can contact our governance desk at <a href="mailto:iosa.research.lab@gmail.com" className="text-[#00E5FF] underline">iosa.research.lab@gmail.com</a>. Requests are handled within 48 hours.
                    </p>
                  </div>
                </div>
              </>
            )}

            {/* Terms of Service Modal */}
            {activeModal === 'terms' && (
              <>
                <div className="flex items-center gap-2 text-[#00E5FF] font-mono text-xs font-bold mb-1">
                  <FileText className="w-4 h-4 text-cyan-400" /> LEGAL TERMS & CONDITIONS
                </div>

                <h2 className="text-xl font-bold font-mono text-white mb-4">
                  Terms of Service
                </h2>

                <div className="space-y-3 font-sans text-xs text-gray-300 leading-relaxed">
                  <div className="bg-black/40 border border-gray-800 p-3.5 rounded-xl space-y-2">
                    <h3 className="font-bold text-white font-mono text-xs text-[#00E5FF]">1. Open Access Public Index</h3>
                    <p>
                      IOSA provides digital accreditation records and trend indices free of charge for research, statistical monitoring, and public reference. All digital cards are released under public fair use principles.
                    </p>
                  </div>

                  <div className="bg-black/40 border border-gray-800 p-3.5 rounded-xl space-y-2">
                    <h3 className="font-bold text-white font-mono text-xs text-[#00E5FF]">2. Third-Party Platform Non-Affiliation</h3>
                    <p>
                      IOSA is an independent analytics project. All product names, logos, and brands are property of their respective owners (YouTube, Google LLC, TikTok/ByteDance, Instagram/Meta, X Corp). Their use does not imply any affiliation or endorsement.
                    </p>
                  </div>

                  <div className="bg-black/40 border border-gray-800 p-3.5 rounded-xl space-y-2">
                    <h3 className="font-bold text-white font-mono text-xs text-[#00E5FF]">3. Physical Mementos & Souvenirs</h3>
                    <p>
                      Optional physical trophies are produced independently as commemorative souvenirs covering manufacturing at cost plus shipping. Trophies do not contain trademarked platform logos or official brand badges.
                    </p>
                  </div>
                </div>
              </>
            )}

            {/* VPI Methodology Standard Modal */}
            {activeModal === 'methodology' && (
              <>
                <div className="flex items-center gap-2 text-[#00E5FF] font-mono text-xs font-bold mb-1">
                  <Calculator className="w-4 h-4 text-[#00E5FF]" /> STATISTICAL AUDIT STANDARD
                </div>

                <h2 className="text-xl font-bold font-mono text-white mb-4">
                  VPI Methodology Standard
                </h2>

                <div className="space-y-3 font-sans text-xs text-gray-300 leading-relaxed">
                  <div className="bg-black/40 border border-cyan-500/30 p-3.5 rounded-xl space-y-2">
                    <h3 className="font-bold text-[#00E5FF] font-mono text-xs">Mathematical Formulation</h3>
                    <p className="font-mono text-sm text-white bg-black p-2 rounded border border-gray-800 text-center">
                      VPI = E<sub>act</sub> / E<sub>base</sub>
                    </p>
                    <p className="text-[11px] text-gray-400">
                      Where <strong>E<sub>act</sub></strong> is the observed public view count within the evaluation window, and <strong>E<sub>base</sub></strong> is the median baseline of the creator's preceding 10 public uploads.
                    </p>
                  </div>

                  <div className="bg-black/40 border border-gray-800 p-3.5 rounded-xl space-y-2">
                    <h3 className="font-bold text-white font-mono text-xs text-[#00E5FF]">Outlier Qualification Thresholds (10 Levels)</h3>
                    <div className="space-y-1.5 font-mono text-[11px] max-h-64 overflow-y-auto pr-1">
                      
                      <div className="flex items-center justify-between p-1.5 rounded bg-amber-950/40 border border-amber-300/40">
                        <span className="flex items-center gap-2">
                          <span className="w-2.5 h-2.5 rounded-full shrink-0 bg-amber-300 shadow-[0_0_8px_rgba(255,215,0,0.8)]"></span>
                          <strong className="text-amber-300">Lvl 10 — Hyper Outlier</strong>
                        </span>
                        <span className="text-amber-300 font-bold">VPI ≥ 50.0x</span>
                      </div>

                      <div className="flex items-center justify-between p-1.5 rounded bg-cyan-950/40 border border-cyan-400/40">
                        <span className="flex items-center gap-2">
                          <span className="w-2.5 h-2.5 rounded-full shrink-0 bg-cyan-300 shadow-[0_0_8px_rgba(6,182,212,0.8)]"></span>
                          <strong className="text-cyan-300">Lvl 9 — Mega Outlier</strong>
                        </span>
                        <span className="text-cyan-300 font-bold">VPI ≥ 25.0x</span>
                      </div>

                      <div className="flex items-center justify-between p-1.5 rounded bg-purple-950/40 border border-purple-500/40">
                        <span className="flex items-center gap-2">
                          <span className="w-2.5 h-2.5 rounded-full shrink-0 bg-purple-400 shadow-[0_0_8px_rgba(124,58,237,0.8)]"></span>
                          <strong className="text-purple-300">Lvl 8 — Outlier</strong>
                        </span>
                        <span className="text-purple-300 font-bold">VPI ≥ 15.0x</span>
                      </div>

                      <div className="flex items-center justify-between p-1.5 rounded bg-pink-950/40 border border-pink-400/40">
                        <span className="flex items-center gap-2">
                          <span className="w-2.5 h-2.5 rounded-full shrink-0 bg-pink-300 shadow-[0_0_8px_rgba(244,114,182,0.8)]"></span>
                          <strong className="text-pink-300">Lvl 7 — Super Viral</strong>
                        </span>
                        <span className="text-pink-300 font-bold">VPI ≥ 10.0x</span>
                      </div>

                      <div className="flex items-center justify-between p-1.5 rounded bg-red-950/40 border border-red-500/40">
                        <span className="flex items-center gap-2">
                          <span className="w-2.5 h-2.5 rounded-full shrink-0 bg-red-400 shadow-[0_0_8px_rgba(239,68,68,0.8)]"></span>
                          <strong className="text-red-300">Lvl 6 — Viral</strong>
                        </span>
                        <span className="text-red-300 font-bold">VPI ≥ 7.5x</span>
                      </div>

                      <div className="flex items-center justify-between p-1.5 rounded bg-orange-950/40 border border-orange-500/40">
                        <span className="flex items-center gap-2">
                          <span className="w-2.5 h-2.5 rounded-full shrink-0 bg-orange-400 shadow-[0_0_8px_rgba(249,115,22,0.8)]"></span>
                          <strong className="text-orange-300">Lvl 5 — Breakout</strong>
                        </span>
                        <span className="text-orange-300 font-bold">VPI ≥ 5.0x</span>
                      </div>

                      <div className="flex items-center justify-between p-1.5 rounded bg-yellow-950/40 border border-yellow-500/40">
                        <span className="flex items-center gap-2">
                          <span className="w-2.5 h-2.5 rounded-full shrink-0 bg-yellow-400 shadow-[0_0_8px_rgba(234,179,8,0.8)]"></span>
                          <strong className="text-yellow-300">Lvl 4 — Trending</strong>
                        </span>
                        <span className="text-yellow-300 font-bold">VPI ≥ 3.0x</span>
                      </div>

                      <div className="flex items-center justify-between p-1.5 rounded bg-lime-950/40 border border-lime-500/40">
                        <span className="flex items-center gap-2">
                          <span className="w-2.5 h-2.5 rounded-full shrink-0 bg-lime-400 shadow-[0_0_8px_rgba(132,204,22,0.8)]"></span>
                          <strong className="text-lime-300">Lvl 3 — Rising</strong>
                        </span>
                        <span className="text-lime-300 font-bold">VPI ≥ 2.0x</span>
                      </div>

                      <div className="flex items-center justify-between p-1.5 rounded bg-green-950/40 border border-green-600/40">
                        <span className="flex items-center gap-2">
                          <span className="w-2.5 h-2.5 rounded-full shrink-0 bg-green-500 shadow-[0_0_8px_rgba(21,128,61,0.8)]"></span>
                          <strong className="text-green-300">Lvl 2 — Moderate</strong>
                        </span>
                        <span className="text-green-300 font-bold">VPI ≥ 1.5x</span>
                      </div>

                      <div className="flex items-center justify-between p-1.5 rounded bg-slate-950/40 border border-slate-600/40">
                        <span className="flex items-center gap-2">
                          <span className="w-2.5 h-2.5 rounded-full shrink-0 bg-slate-400 shadow-[0_0_8px_rgba(100,116,139,0.5)]"></span>
                          <strong className="text-slate-300">Lvl 1 — Standard</strong>
                        </span>
                        <span className="text-slate-300 font-bold">VPI &lt; 1.5x</span>
                      </div>

                    </div>
                  </div>

                  <div className="bg-black/40 border border-gray-800 p-3.5 rounded-xl space-y-2">
                    <h3 className="font-bold text-white font-mono text-xs text-[#00E5FF]">15-Day Rolling Audit Window</h3>
                    <p>
                      Posts are monitored continuously across active 15-day windows. Indices are recalculated automatically to ensure baseline integrity against artificial spikes. Content with VPI ≤ 1.0x is excluded from indexing.
                    </p>
                  </div>
                </div>
              </>
            )}

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
              An independent, third-party community research project dedicated to open-source algorithmic monitoring and transparent viral metric analytics.
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
                <button 
                  onClick={() => setActiveModal('privacy')} 
                  className="hover:text-[#00E5FF] transition-colors flex items-center gap-1.5 cursor-pointer text-left"
                >
                  <ShieldCheck className="w-3 h-3 text-cyan-400" /> Privacy Policy
                </button>
              </li>
              <li>
                <button 
                  onClick={() => setActiveModal('terms')} 
                  className="hover:text-[#00E5FF] transition-colors flex items-center gap-1.5 cursor-pointer text-left"
                >
                  <FileText className="w-3 h-3 text-cyan-400" /> Terms of Service
                </button>
              </li>
              <li>
                <button 
                  onClick={() => setActiveModal('methodology')} 
                  className="hover:text-[#00E5FF] transition-colors flex items-center gap-1.5 cursor-pointer text-left"
                >
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
            © 2026 Institute for Open Social Analytics (IOSA). Independent research initiative.
          </p>
          <p className="text-center md:text-right font-sans text-gray-400 max-w-xl">
            Disclaimer: IOSA is an independent analytics project and is not affiliated, endorsed, or partnered with YouTube, TikTok, Instagram, X (Twitter), or Meta.
          </p>
        </div>
      </footer>
    </main>
  );
}