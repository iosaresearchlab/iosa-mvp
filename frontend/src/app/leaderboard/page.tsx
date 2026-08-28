'use client';

import React, { useState, useEffect } from "react";
import Link from "next/link";
import {
  Trophy,
  TrendingUp,
  HelpCircle,
  Info,
  ArrowLeft,
  Search,
  Globe,
  Award,
  ExternalLink,
  BarChart3,
  Mail,
  ShieldCheck,
  FileText,
  X
} from "lucide-react";

interface Post {
  id: string;
  claim_token: string;
  author_handle: string;
  content_text: string;
  vpi_ratio: number;
  vpi_level_name: string;
  engagement_score: number;
  baseline_score: number;
  country: string;
  category: string;
  url?: string;
  created_at: string;
}

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

const COUNTRIES = [
  { code: "ALL", label: "All Countries" },
  { code: "US", label: "United States (US)" },
  { code: "GB", label: "United Kingdom (GB)" },
  { code: "DE", label: "Germany (DE)" },
  { code: "FR", label: "France (FR)" },
  { code: "ES", label: "Spain (ES)" },
  { code: "IT", label: "Italy (IT)" },
  { code: "BR", label: "Brazil (BR)" },
  { code: "IN", label: "India (IN)" },
  { code: "JP", label: "Japan (JP)" },
];

const CATEGORIES = [
  "ALL",
  "Gaming",
  "Entertainment",
  "Tech & Science",
  "Education",
  "Lifestyle",
  "Music",
  "News & Politics"
];

type ModalType = 'faq' | 'privacy' | 'terms' | 'methodology' | null;

export default function LeaderboardPage() {
  const [timeframe, setTimeframe] = useState<"24h" | "7d">("24h");
  const [selectedCountry, setSelectedCountry] = useState<string>("ALL");
  const [selectedCategory, setSelectedCategory] = useState<string>("ALL");
  
  const [topPosts, setTopPosts] = useState<Post[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [activeModal, setActiveModal] = useState<ModalType>(null);

  useEffect(() => {
    document.title = 'IOSA — Top 10 Outlier Leaderboard';
  }, []);

  useEffect(() => {
    fetchTop10();
  }, [timeframe, selectedCountry, selectedCategory]);

  const fetchTop10 = async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        timeframe: timeframe,
      });

      if (selectedCountry !== "ALL") params.append("country", selectedCountry);
      if (selectedCategory !== "ALL") params.append("category", selectedCategory);

      const res = await fetch(`${BACKEND_URL}/api/analytics/top10?${params.toString()}`);
      if (!res.ok) {
        throw new Error(`Error ${res.status}: ${res.statusText}`);
      }
      const data = await res.json();
      setTopPosts(data.top10 || []);
    } catch (err: any) {
      console.error("Failed to load leaderboard:", err);
      setError("Unable to load leaderboard data. Please check backend connection.");
    } finally {
      setLoading(false);
    }
  };

  const formatNumber = (num: number) => {
    if (!num) return "0";
    if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
    if (num >= 1000) return `${(num / 1000).toFixed(1)}K`;
    return num.toString();
  };

  return (
    <main className="min-h-screen bg-[#030508] text-white font-sans relative flex flex-col justify-between">
      
      {/* Fixed Navigation Header - Coerente con la Landing */}
      <header className="fixed top-0 left-0 right-0 z-50 bg-[#030508]/90 backdrop-blur-md border-b border-gray-800/80 px-4 md:px-10 py-2 flex justify-between items-center">
        <div className="flex items-center gap-3">
          <Link href="/" className="flex items-center gap-1 text-gray-400 hover:text-white transition-colors">
            <ArrowLeft className="w-4 h-4 text-[#00E5FF]" />
            <span className="font-mono text-xs hidden sm:inline">Back</span>
          </Link>
          <div className="h-4 w-[1px] bg-gray-800 hidden sm:block"></div>
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
        </div>

        <div className="flex items-center gap-1.5 md:gap-2">
          <Link
            href="/leaderboard"
            className="flex items-center gap-1 bg-cyan-950/80 border border-cyan-500 px-2.5 py-1 rounded-full text-cyan-300 font-mono text-xs shadow-[0_0_10px_rgba(0,229,255,0.3)]"
          >
            <Trophy className="w-3.5 h-3.5 text-[#00E5FF]" />
            <span className="hidden sm:inline">Top 10</span>
          </Link>

          <Link
            href="/insights"
            className="flex items-center gap-1 bg-gray-900 hover:bg-gray-800 border border-gray-700 px-2.5 py-1 rounded-full text-gray-200 font-mono text-xs transition-colors"
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
            onClick={() => setActiveModal('methodology')}
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
      <div className="pt-20 pb-10 px-4 md:px-8 max-w-6xl mx-auto space-y-6 flex-grow w-full font-sans">
        
        {/* Header Section */}
        <div className="bg-gradient-to-b from-[#0B101B] to-[#070A10] border border-gray-800 rounded-2xl p-6 relative shadow-xl">
          <div className="absolute inset-0 rounded-2xl overflow-hidden pointer-events-none">
            <div className="absolute top-0 right-0 w-64 h-64 bg-[#00E5FF]/10 rounded-full blur-3xl" />
          </div>

          <div className="relative z-10 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div>
              <div className="inline-flex items-center gap-1.5 text-[10px] font-mono text-cyan-300 bg-cyan-950/50 border border-cyan-500/30 px-3 py-0.5 rounded-full mb-2">
                <Trophy className="w-3 h-3 text-[#00E5FF]" />
                <span>Real-Time Algorithmic Ranking</span>
              </div>
              <h1 className="text-2xl sm:text-3xl font-black font-mono tracking-tight text-white flex items-center gap-3">
                Outlier Leaderboard (Top 10)
              </h1>
              <p className="text-gray-400 mt-1 text-xs sm:text-sm font-sans max-w-xl">
                Top viral performers detected by the Viral Performance Index algorithm across active time windows.
              </p>
            </div>

            {/* Timeframe Switch */}
            <div className="inline-flex p-1 bg-black/80 border border-gray-800 rounded-xl self-start md:self-auto font-mono">
              <button
                onClick={() => setTimeframe("24h")}
                className={`px-4 py-2 text-xs font-bold rounded-lg transition-all cursor-pointer ${
                  timeframe === "24h"
                    ? "bg-[#00E5FF] text-black shadow-lg shadow-cyan-950/50"
                    : "text-gray-400 hover:text-white"
                }`}
              >
                Past 24 Hours
              </button>
              <button
                onClick={() => setTimeframe("7d")}
                className={`px-4 py-2 text-xs font-bold rounded-lg transition-all cursor-pointer ${
                  timeframe === "7d"
                    ? "bg-[#00E5FF] text-black shadow-lg shadow-cyan-950/50"
                    : "text-gray-400 hover:text-white"
                }`}
              >
                Past 7 Days
              </button>
            </div>
          </div>
        </div>

        {/* Filters Bar */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 bg-[#070A10] border border-gray-800 p-4 rounded-xl font-mono text-xs shadow-md">
          <div>
            <label className="block text-[10px] font-semibold uppercase tracking-wider text-gray-400 mb-1.5">
              Filter by Country
            </label>
            <select
              value={selectedCountry}
              onChange={(e) => setSelectedCountry(e.target.value)}
              className="w-full bg-black border border-gray-800 text-gray-200 text-xs rounded-lg p-2.5 focus:ring-1 focus:ring-[#00E5FF] focus:border-[#00E5FF] focus:outline-none cursor-pointer"
            >
              {COUNTRIES.map((c) => (
                <option key={c.code} value={c.code} className="bg-gray-900">
                  {c.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-[10px] font-semibold uppercase tracking-wider text-gray-400 mb-1.5">
              Filter by Category
            </label>
            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className="w-full bg-black border border-gray-800 text-gray-200 text-xs rounded-lg p-2.5 focus:ring-1 focus:ring-[#00E5FF] focus:border-[#00E5FF] focus:outline-none cursor-pointer"
            >
              {CATEGORIES.map((cat) => (
                <option key={cat} value={cat} className="bg-gray-900">
                  {cat === "ALL" ? "All Categories" : cat}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Leaderboard Table / Cards */}
        {loading ? (
          <div className="flex flex-col items-center justify-center py-20 bg-[#070A10] rounded-2xl border border-gray-800">
            <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-[#00E5FF] mb-4"></div>
            <p className="text-gray-400 text-xs font-mono">Calculating viral velocity rankings...</p>
          </div>
        ) : error ? (
          <div className="bg-red-950/40 border border-red-800 text-red-300 p-6 rounded-xl text-center font-mono text-xs">
            {error}
          </div>
        ) : topPosts.length === 0 ? (
          <div className="bg-[#070A10] border border-gray-800 text-gray-400 p-12 rounded-2xl text-center font-mono text-xs">
            <p className="text-sm font-bold text-white mb-1">No viral outliers found for the selected filters.</p>
            <p className="text-gray-500">Try resetting country or category options.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {topPosts.map((post, idx) => {
              const rank = idx + 1;

              return (
                <div
                  key={post.id || idx}
                  className={`flex flex-col md:flex-row items-start md:items-center justify-between p-4 rounded-xl border transition-all ${
                    rank === 1
                      ? "bg-cyan-950/30 border-cyan-500/60 shadow-[0_0_15px_rgba(0,229,255,0.15)]"
                      : rank === 2
                      ? "bg-[#070A10] border-gray-700"
                      : rank === 3
                      ? "bg-[#070A10] border-gray-800"
                      : "bg-[#070A10]/60 border-gray-800/80"
                  }`}
                >
                  <div className="flex items-start gap-3.5 mb-3 md:mb-0 w-full md:w-auto">
                    <div
                      className={`flex-shrink-0 w-9 h-9 rounded-xl flex items-center justify-center font-mono font-black text-sm ${
                        rank === 1
                          ? "bg-[#00E5FF] text-black shadow-lg shadow-cyan-950/50"
                          : rank === 2
                          ? "bg-gray-300 text-black"
                          : rank === 3
                          ? "bg-amber-700 text-white"
                          : "bg-gray-800 text-gray-400"
                      }`}
                    >
                      #{rank}
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5 flex-wrap mb-1 font-mono">
                        <span className="text-[11px] font-bold text-[#00E5FF]">
                          {post.author_handle || "@Creator"}
                        </span>
                        <span className="text-gray-600">•</span>
                        <span className="text-[9px] bg-black text-gray-300 px-2 py-0.5 rounded border border-gray-800 uppercase font-bold">
                          {post.country || "Global"}
                        </span>
                        <span className="text-[9px] bg-cyan-950/50 text-cyan-300 px-2 py-0.5 rounded border border-cyan-500/30 uppercase font-bold">
                          {post.category || "General"}
                        </span>
                      </div>

                      <h3 className="text-xs sm:text-sm font-bold text-white line-clamp-1 pr-2 font-sans">
                        {post.content_text || "Untitled Outlier Content"}
                      </h3>

                      <div className="flex items-center gap-3 mt-1.5 text-[10px] text-gray-400 font-mono">
                        <span>Actual: <strong className="text-white">{formatNumber(post.engagement_score)}</strong></span>
                        <span>Baseline: <strong className="text-white">{formatNumber(post.baseline_score)}</strong></span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center justify-between md:justify-end gap-5 w-full md:w-auto border-t md:border-t-0 border-gray-800 pt-3 md:pt-0">
                    <div className="text-left md:text-right font-mono">
                      <div className="text-lg font-black text-[#00E5FF] tracking-tight">
                        +{Number(post.vpi_ratio || 1.0).toFixed(1)}x
                      </div>
                      <div className="text-[9px] font-semibold tracking-wider text-gray-500 uppercase">
                        {post.vpi_level_name || "Lvl 2 Outlier"}
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      {post.claim_token && (
                        <Link
                          href={`/claim/${post.claim_token}`}
                          className="px-3 py-1.5 text-[11px] font-bold font-mono rounded-lg bg-[#00E5FF] hover:bg-cyan-400 text-black transition-colors shadow-md shadow-cyan-950/50"
                        >
                          View Analysis
                        </Link>
                      )}
                      {post.url && (
                        <a
                          href={post.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="p-1.5 text-xs font-semibold rounded-lg bg-black hover:bg-gray-800 text-gray-300 border border-gray-800 transition-colors"
                          title="Watch Source Video"
                        >
                          <ExternalLink className="w-3.5 h-3.5" />
                        </a>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Modali Governance (FAQ / Metodologia) */}
      {activeModal && (
        <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in">
          <div className="bg-[#0B101B] border border-cyan-500/50 rounded-2xl max-w-xl w-full p-5 max-h-[85vh] overflow-y-auto relative shadow-2xl">
            <button
              onClick={() => setActiveModal(null)}
              className="absolute top-4 right-4 p-1 text-gray-400 hover:text-white font-mono cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>

            {activeModal === 'faq' && (
              <>
                <div className="flex items-center gap-2 text-[#00E5FF] font-mono text-xs font-bold mb-1">
                  <ShieldCheck className="w-4 h-4" /> TRANSPARENCY & GOVERNANCE FAQ
                </div>
                <h2 className="text-xl font-bold font-mono text-white mb-4">Frequently Asked Questions</h2>
                <div className="space-y-4 font-sans text-xs">
                  <div className="bg-black/40 border border-gray-800 p-3.5 rounded-xl">
                    <h3 className="font-bold text-white text-sm font-mono mb-1">How is the VPI Ratio calculated?</h3>
                    <p className="text-gray-300 leading-relaxed font-mono text-[11px]">
                      VPI = Actual Views / Historical Baseline Views. If a creator averages 10,000 views and a video reaches 150,000 views within 15 days, their VPI is 15.0x.
                    </p>
                  </div>
                </div>
              </>
            )}

            {activeModal === 'methodology' && (
              <>
                <div className="flex items-center gap-2 text-[#00E5FF] font-mono text-xs font-bold mb-1">
                  <Info className="w-4 h-4 text-[#00E5FF]" /> STATISTICAL AUDIT STANDARD
                </div>
                <h2 className="text-xl font-bold font-mono text-white mb-4">VPI Methodology Standard</h2>
                <div className="space-y-3 font-sans text-xs text-gray-300 leading-relaxed">
                  <div className="bg-black/40 border border-cyan-500/30 p-3.5 rounded-xl space-y-2">
                    <h3 className="font-bold text-[#00E5FF] font-mono text-xs">Mathematical Formulation</h3>
                    <p className="font-mono text-sm text-white bg-black p-2 rounded border border-gray-800 text-center">
                      VPI = E<sub>act</sub> / E<sub>base</sub>
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
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Footer */}
      <footer className="w-full bg-[#020305] border-t border-gray-800/80 pt-5 pb-5 px-6 md:px-12 mt-10 text-xs font-mono text-gray-400">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row justify-between items-center gap-3 text-[10px] text-gray-400">
          <p className="text-center md:text-left font-sans">
            © 2026 Institute for Open Social Analytics (IOSA). Independent research initiative.
          </p>
          <div className="flex items-center gap-4">
            <Link href="/" className="hover:text-[#00E5FF] transition-colors">Home Landing</Link>
            <Link href="/insights" className="hover:text-[#00E5FF] transition-colors">Macro Insights</Link>
          </div>
        </div>
      </footer>
    </main>
  );
}