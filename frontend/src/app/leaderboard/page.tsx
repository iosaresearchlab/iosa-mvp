'use client';

import React, { useState, useEffect } from "react";
import Link from "next/link";
import {
  Trophy,
  TrendingUp,
  HelpCircle,
  Info,
  ArrowLeft,
  Globe,
  Award,
  ExternalLink,
  ShieldCheck,
  X,
  Users,
  Flame
} from "lucide-react";

interface Post {
  id: string;
  claim_token: string;
  author_handle: string;
  author_name: string;
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

interface CreatorRank {
  author_handle: string;
  author_name: string;
  spikesCount: number;
  avgVpi: number;
  totalViews: number;
  country: string;
  category: string;
  claim_token: string;
}

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

const NA_COUNTRIES = [
  { code: "ALL", label: "All NA Countries" },
  { code: "US", label: "United States (US)" },
  { code: "CA", label: "Canada (CA)" },
  { code: "MX", label: "Mexico (MX)" },
];

const EU_COUNTRIES = [
  { code: "ALL", label: "All EU Countries" },
  { code: "GB", label: "United Kingdom (GB)" },
  { code: "DE", label: "Germany (DE)" },
  { code: "FR", label: "France (FR)" },
  { code: "ES", label: "Spain (ES)" },
  { code: "IT", label: "Italy (IT)" },
  { code: "NL", label: "Netherlands (NL)" },
  { code: "SE", label: "Sweden (SE)" },
];

const ASIA_COUNTRIES = [
  { code: "ALL", label: "All Asia/Other" },
  { code: "JP", label: "Japan (JP)" },
  { code: "IN", label: "India (IN)" },
  { code: "KR", label: "South Korea (KR)" },
  { code: "BR", label: "Brazil (BR)" },
  { code: "AU", label: "Australia (AU)" },
];

const CATEGORIES = [
  "ALL",
  "Gaming",
  "Entertainment",
  "Tech",
  "Education",
  "Music",
  "News & Politics",
  "Film & Animation"
];

type ModalType = 'faq' | 'methodology' | null;

export default function LeaderboardPage() {
  const [timeframe, setTimeframe] = useState<"24h" | "7d" | "15d">("7d");
  
  // Independent filters per box
  const [worldCountry, setWorldCountry] = useState<string>("ALL");
  const [worldCategory, setWorldCategory] = useState<string>("ALL");

  const [naCountry, setNaCountry] = useState<string>("ALL");
  const [naCategory, setNaCategory] = useState<string>("ALL");

  const [euCountry, setEuCountry] = useState<string>("ALL");
  const [euCategory, setEuCategory] = useState<string>("ALL");

  const [asiaCountry, setAsiaCountry] = useState<string>("ALL");
  const [asiaCategory, setAsiaCategory] = useState<string>("ALL");

  const [allPosts, setAllPosts] = useState<Post[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [activeModal, setActiveModal] = useState<ModalType>(null);

  useEffect(() => {
    document.title = 'IOSA — Top 10 Creator Leaderboard';
  }, []);

  useEffect(() => {
    fetchAllPosts();
  }, [timeframe]);

const fetchAllPosts = async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        timeframe: timeframe,
        limit: "300"
      });

      const res = await fetch(`${BACKEND_URL}/api/analytics/top10?${params.toString()}`);
      if (!res.ok) {
        throw new Error(`Error ${res.status}: ${res.statusText}`);
      }
      const data = await res.json();
      setAllPosts(data.top10 || []);
    } catch (err: any) {
      console.error("Failed to load leaderboard posts:", err);
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

  const aggregateCreators = (posts: Post[]): CreatorRank[] => {
    const map = new Map<string, {
      author_handle: string;
      author_name: string;
      vpiSum: number;
      viewsSum: number;
      count: number;
      country: string;
      category: string;
      claim_token: string;
    }>();

    for (const p of posts) {
      const key = p.author_handle || p.author_name || "unknown_creator";
      if (!map.has(key)) {
        map.set(key, {
          author_handle: p.author_handle || "@Creator",
          author_name: p.author_name || p.author_handle || "Creator",
          vpiSum: Number(p.vpi_ratio) || 1.0,
          viewsSum: Number(p.engagement_score) || 0,
          count: 1,
          country: p.country || "US",
          category: p.category || "General",
          claim_token: p.claim_token || ""
        });
      } else {
        const entry = map.get(key)!;
        entry.vpiSum += Number(p.vpi_ratio) || 1.0;
        entry.viewsSum += Number(p.engagement_score) || 0;
        entry.count += 1;
      }
    }

    const result: CreatorRank[] = [];
    map.forEach((val) => {
      result.push({
        author_handle: val.author_handle,
        author_name: val.author_name,
        spikesCount: val.count,
        avgVpi: Number((val.vpiSum / val.count).toFixed(1)),
        totalViews: val.viewsSum,
        country: val.country,
        category: val.category,
        claim_token: val.claim_token
      });
    });

    result.sort((a, b) => b.avgVpi - a.avgVpi);
    return result.slice(0, 10);
  };

  // Filter helpers
  const filterWorld = allPosts.filter(p => {
    if (worldCountry !== "ALL" && p.country !== worldCountry) return false;
    if (worldCategory !== "ALL" && p.category !== worldCategory) return false;
    return true;
  });

  const naList = ["US", "CA", "MX"];
  const filterNa = allPosts.filter(p => {
    if (!naList.includes(p.country)) return false;
    if (naCountry !== "ALL" && p.country !== naCountry) return false;
    if (naCategory !== "ALL" && p.category !== naCategory) return false;
    return true;
  });

  const euList = ["GB", "DE", "FR", "ES", "IT", "NL", "SE", "NO", "FI", "DK", "CH", "AT", "BE", "PT", "IE"];
  const filterEu = allPosts.filter(p => {
    if (!euList.includes(p.country)) return false;
    if (euCountry !== "ALL" && p.country !== euCountry) return false;
    if (euCategory !== "ALL" && p.category !== euCategory) return false;
    return true;
  });

  const filterAsia = allPosts.filter(p => {
    if (naList.includes(p.country) || euList.includes(p.country)) return false;
    if (asiaCountry !== "ALL" && p.country !== asiaCountry) return false;
    if (asiaCategory !== "ALL" && p.category !== asiaCategory) return false;
    return true;
  });

  const worldCreators = aggregateCreators(filterWorld);
  const naCreators = aggregateCreators(filterNa);
  const euCreators = aggregateCreators(filterEu);
  const asiaCreators = aggregateCreators(filterAsia);

  const renderCreatorBox = (
    title: string,
    subtitle: string,
    creators: CreatorRank[],
    countryVal: string,
    setCountryVal: (val: string) => void,
    categoryVal: string,
    setCategoryVal: (val: string) => void,
    countryList: { code: string; label: string }[],
    icon: React.ReactNode
  ) => (
    <div className="bg-[#070A10] border border-gray-800 rounded-2xl p-5 shadow-xl flex flex-col justify-between">
      <div>
        {/* Box Header */}
        <div className="flex items-center justify-between mb-4 pb-3 border-b border-gray-800">
          <div className="flex items-center gap-2.5">
            <div className="p-2 bg-cyan-950/60 border border-cyan-500/30 rounded-xl text-[#00E5FF]">
              {icon}
            </div>
            <div>
              <h2 className="text-base font-black font-mono text-white tracking-tight">{title}</h2>
              <p className="text-[11px] text-gray-400 font-sans">{subtitle}</p>
            </div>
          </div>
        </div>

        {/* Local Dropdowns */}
        <div className="grid grid-cols-2 gap-2 mb-4 font-mono text-xs">
          <div>
            <label className="block text-[9px] font-semibold uppercase tracking-wider text-gray-400 mb-1">Country</label>
            <select
              value={countryVal}
              onChange={(e) => setCountryVal(e.target.value)}
              className="w-full bg-black border border-gray-800 text-gray-200 text-[11px] rounded-lg p-2 focus:ring-1 focus:ring-[#00E5FF] focus:outline-none cursor-pointer"
            >
              {countryList.map((c) => (
                <option key={c.code} value={c.code} className="bg-gray-900">{c.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-[9px] font-semibold uppercase tracking-wider text-gray-400 mb-1">Category</label>
            <select
              value={categoryVal}
              onChange={(e) => setCategoryVal(e.target.value)}
              className="w-full bg-black border border-gray-800 text-gray-200 text-[11px] rounded-lg p-2 focus:ring-1 focus:ring-[#00E5FF] focus:outline-none cursor-pointer"
            >
              {CATEGORIES.map((cat) => (
                <option key={cat} value={cat} className="bg-gray-900">{cat === "ALL" ? "All Categories" : cat}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Creators Top 10 List */}
        {loading ? (
          <div className="py-12 flex justify-center items-center">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-[#00E5FF]"></div>
          </div>
        ) : creators.length === 0 ? (
          <div className="py-10 text-center text-gray-500 font-mono text-xs">
            No creators found for these filters.
          </div>
        ) : (
          <div className="space-y-2.5">
            {creators.map((creator, idx) => {
              const rank = idx + 1;
              return (
                <div
                  key={creator.author_handle + idx}
                  className="flex items-center justify-between p-3 bg-black/50 hover:bg-black border border-gray-800/80 rounded-xl transition-all"
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <span className={`w-6 h-6 rounded-lg flex items-center justify-center font-mono font-black text-xs shrink-0 ${
                      rank === 1 ? "bg-[#00E5FF] text-black" :
                      rank === 2 ? "bg-gray-300 text-black" :
                      rank === 3 ? "bg-amber-700 text-white" : "bg-gray-800 text-gray-400"
                    }`}>
                      {rank}
                    </span>
                    <div className="min-w-0">
                      <div className="flex items-center gap-1.5 font-mono">
                        <span className="text-xs font-bold text-white truncate max-w-[120px] sm:max-w-[150px]">
                          {creator.author_name}
                        </span>
                        <span className="text-[9px] text-cyan-400 bg-cyan-950/60 px-1.5 py-0.5 rounded border border-cyan-500/30">
                          {creator.country}
                        </span>
                      </div>
                      <div className="flex items-center gap-2 text-[10px] text-gray-400 font-mono mt-0.5">
                        <span className="flex items-center gap-0.5 text-amber-400 font-bold">
                          <Flame className="w-2.5 h-2.5" /> {creator.spikesCount} spikes
                        </span>
                        <span>• {formatNumber(creator.totalViews)} views</span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 shrink-0 font-mono">
                    <div className="text-right">
                      <div className="text-xs font-black text-[#00E5FF]">+{creator.avgVpi}x</div>
                      <div className="text-[8px] text-gray-500 uppercase">Avg VPI</div>
                    </div>
                    {creator.claim_token && (
                      <Link
                        href={`/claim/${creator.claim_token}`}
                        className="p-1.5 bg-cyan-950 hover:bg-cyan-900 text-[#00E5FF] rounded-lg border border-cyan-500/40 transition-colors"
                        title="View Creator Report"
                      >
                        <ExternalLink className="w-3 h-3" />
                      </Link>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div className="mt-4 pt-3 border-t border-gray-800/60 text-[10px] font-mono text-gray-500 flex justify-between items-center">
        <span>Updated real-time</span>
        <span className="text-[#00E5FF] font-bold">Top 10 Creators</span>
      </div>
    </div>
  );

  return (
    <main className="min-h-screen bg-[#030508] text-white font-sans relative flex flex-col justify-between">
      
      {/* Fixed Navigation Header */}
      <header className="fixed top-0 left-0 right-0 z-50 bg-[#030508]/90 backdrop-blur-md border-b border-gray-800/80 px-4 md:px-10 py-2.5 flex justify-between items-center">
        <div className="flex items-center gap-2.5">
          <svg className="h-5 w-3 text-[#00E5FF]" viewBox="0 0 18.5 32" fill="none">
            <path d="M1 26.5H6.5L14 8.5L17.5 14" stroke="currentColor" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" />
            <circle cx="14" cy="3" r="3" fill="#00E5FF" />
          </svg>
          <div className="flex flex-col">
            <span className="font-mono font-black text-base tracking-tighter text-white leading-none">IOSA</span>
            <span className="text-[7px] font-mono text-gray-400 tracking-widest uppercase opacity-80">Institute for Open Social Analytics</span>
          </div>
        </div>

        <div className="flex items-center gap-1.5 md:gap-2">
          <Link href="/leaderboard" className="flex items-center gap-1 bg-cyan-950/80 border border-cyan-500 px-2.5 py-1 rounded-full text-cyan-300 font-mono text-xs shadow-[0_0_10px_rgba(0,229,255,0.3)]">
            <Trophy className="w-3.5 h-3.5 text-[#00E5FF]" />
            <span className="hidden sm:inline">Top 10 Creators</span>
          </Link>

          <Link href="/insights" className="flex items-center gap-1 bg-gray-900 hover:bg-gray-800 border border-gray-700 px-2.5 py-1 rounded-full text-gray-200 font-mono text-xs transition-colors">
            <TrendingUp className="w-3.5 h-3.5 text-[#00E5FF]" />
            <span className="hidden sm:inline">Insights</span>
          </Link>

          <button onClick={() => setActiveModal('faq')} className="flex items-center gap-1 bg-gray-900 hover:bg-gray-800 border border-gray-700 px-2.5 py-1 rounded-full text-gray-200 font-mono text-xs transition-colors cursor-pointer">
            <HelpCircle className="w-3.5 h-3.5 text-[#00E5FF]" />
            <span className="hidden sm:inline">FAQ</span>
          </button>

          <button onClick={() => setActiveModal('methodology')} className="hidden sm:flex items-center gap-1 bg-cyan-950/40 hover:bg-cyan-900/60 border border-cyan-500/30 px-2.5 py-1 rounded-full text-cyan-300 font-mono text-xs transition-colors cursor-pointer">
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
      <div className="pt-20 pb-12 px-4 md:px-8 max-w-7xl mx-auto space-y-6 flex-grow w-full font-sans">
        
        {/* Back to Home Button - Placed below header on the left side */}
        <div className="flex justify-start">
          <Link
            href="/"
            className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-xl bg-gray-900/90 hover:bg-gray-800 border border-gray-800 text-gray-300 hover:text-[#00E5FF] transition-all font-mono text-xs shadow-md group"
          >
            <ArrowLeft className="w-4 h-4 text-[#00E5FF] group-hover:-translate-x-0.5 transition-transform" />
            <span>Back to Home</span>
          </Link>
        </div>

        {/* Header Section */}
        <div className="bg-gradient-to-b from-[#0B101B] to-[#070A10] border border-gray-800 rounded-2xl p-6 relative shadow-xl flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div className="absolute inset-0 rounded-2xl overflow-hidden pointer-events-none">
            <div className="absolute top-0 right-0 w-64 h-64 bg-[#00E5FF]/10 rounded-full blur-3xl" />
          </div>

          <div className="relative z-10">
            <div className="inline-flex items-center gap-1.5 text-[10px] font-mono text-cyan-300 bg-cyan-950/50 border border-cyan-500/30 px-3 py-0.5 rounded-full mb-2">
              <Users className="w-3 h-3 text-[#00E5FF]" />
              <span>Creator Viral Velocity Rankings</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-black font-mono tracking-tight text-white">
              Top 10 Creator Leaderboards
            </h1>
            <p className="text-gray-400 mt-1 text-xs sm:text-sm font-sans max-w-xl">
              Discover top-performing creators across global and regional sectors ranked by viral spikes count and average VPI.
            </p>
          </div>

          {/* Global Timeframe Switch */}
          <div className="inline-flex p-1 bg-black/80 border border-gray-800 rounded-xl self-start md:self-auto font-mono relative z-10">
            <button
              onClick={() => setTimeframe("24h")}
              className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-all cursor-pointer ${
                timeframe === "24h" ? "bg-[#00E5FF] text-black shadow-lg shadow-cyan-950/50" : "text-gray-400 hover:text-white"
              }`}
            >
              24h
            </button>
            <button
              onClick={() => setTimeframe("7d")}
              className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-all cursor-pointer ${
                timeframe === "7d" ? "bg-[#00E5FF] text-black shadow-lg shadow-cyan-950/50" : "text-gray-400 hover:text-white"
              }`}
            >
              7 Days
            </button>
            <button
              onClick={() => setTimeframe("15d")}
              className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-all cursor-pointer ${
                timeframe === "15d" ? "bg-[#00E5FF] text-black shadow-lg shadow-cyan-950/50" : "text-gray-400 hover:text-white"
              }`}
            >
              15 Days
            </button>
          </div>
        </div>

        {/* Dashboard Grid of Boxes (World & Areas) */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          
          {/* Box 1: World Overall */}
          {renderCreatorBox(
            "World Overall Top 10",
            "Global top performing creators across all territories",
            worldCreators,
            worldCountry,
            setWorldCountry,
            worldCategory,
            setWorldCategory,
            [{ code: "ALL", label: "All Countries" }, ...NA_COUNTRIES.slice(1), ...EU_COUNTRIES.slice(1)],
            <Globe className="w-4 h-4" />
          )}

          {/* Box 2: North America */}
          {renderCreatorBox(
            "North America (NA)",
            "Top outlier creators in US, Canada, and Mexico",
            naCreators,
            naCountry,
            setNaCountry,
            naCategory,
            setNaCategory,
            NA_COUNTRIES,
            <Trophy className="w-4 h-4" />
          )}

          {/* Box 3: Europe */}
          {renderCreatorBox(
            "Europe (EU)",
            "Top outlier creators across European territories",
            euCreators,
            euCountry,
            setEuCountry,
            euCategory,
            setEuCategory,
            EU_COUNTRIES,
            <Award className="w-4 h-4" />
          )}

          {/* Box 4: Asia & Rest of World */}
          {renderCreatorBox(
            "Asia & Global Markets",
            "Top outlier creators in Asia and emerging regions",
            asiaCreators,
            asiaCountry,
            setAsiaCountry,
            asiaCategory,
            setAsiaCategory,
            ASIA_COUNTRIES,
            <TrendingUp className="w-4 h-4" />
          )}

        </div>
      </div>

      {/* Modali Governance */}
      {activeModal && (
        <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in">
          <div className="bg-[#0B101B] border border-cyan-500/50 rounded-2xl max-w-xl w-full p-5 max-h-[85vh] overflow-y-auto relative shadow-2xl">
            <button onClick={() => setActiveModal(null)} className="absolute top-4 right-4 p-1 text-gray-400 hover:text-white font-mono cursor-pointer">
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
                    <h3 className="font-bold text-white text-sm font-mono mb-1">How are Top Creators ranked?</h3>
                    <p className="text-gray-300 leading-relaxed font-mono text-[11px]">
                      Creators are aggregated from detected viral spikes. Ranking is based on their average VPI ratio across spikes, total views, and spike frequency.
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
              <button onClick={() => setActiveModal(null)} className="bg-[#00E5FF] hover:bg-cyan-400 text-black font-mono font-bold text-xs px-4 py-2 rounded-lg transition-colors cursor-pointer">
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Footer */}
      <footer className="w-full bg-[#020305] border-t border-gray-800/80 pt-5 pb-5 px-6 md:px-12 mt-10 text-xs font-mono text-gray-400">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row justify-between items-center gap-3 text-[10px] text-gray-400">
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