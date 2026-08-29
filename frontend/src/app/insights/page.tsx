'use client';

import React, { useState, useEffect } from "react";
import Link from "next/link";
import {
  TrendingUp,
  Trophy,
  HelpCircle,
  Info,
  ArrowLeft,
  ShieldCheck,
  X,
  Globe,
  Layers,
  Zap,
  Flame,
  BarChart3,
  Sparkles,
  Tag
} from "lucide-react";

interface StatDetail {
  avg_vpi: number;
  outlier_count: number;
}

interface InsightsData {
  by_country: Record<string, StatDetail>;
  by_category: Record<string, StatDetail>;
  macro_regions: Record<string, StatDetail>;
}

interface KeywordItem {
  keyword: string;
  frequency: number;
  viral_velocity: number;
}

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
type ModalType = 'faq' | 'methodology' | null;

export default function InsightsPage() {
  const [insights, setInsights] = useState<InsightsData | null>(null);
  const [keywords, setKeywords] = useState<KeywordItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [minVpiFilter, setMinVpiFilter] = useState<number>(5.0);
  const [error, setError] = useState<string | null>(null);
  const [activeModal, setActiveModal] = useState<ModalType>(null);

  useEffect(() => {
    document.title = 'IOSA — Macro Insights & Analytics';
  }, []);

  useEffect(() => {
    fetchData();
  }, []);

  useEffect(() => {
    fetchKeywords();
  }, [minVpiFilter]);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [insightsRes, keywordsRes] = await Promise.all([
        fetch(`${BACKEND_URL}/api/analytics/insights`),
        fetch(`${BACKEND_URL}/api/analytics/keywords?min_vpi=${minVpiFilter}`)
      ]);

      if (!insightsRes.ok) throw new Error("Failed to load insights data");
      if (!keywordsRes.ok) throw new Error("Failed to load viral keywords data");

      const insightsJson = await insightsRes.json();
      const keywordsJson = await keywordsRes.json();

      setInsights(insightsJson);
      setKeywords(keywordsJson.keywords || []);
    } catch (err: any) {
      console.error("Error fetching analytics insights:", err);
      setError("Unable to load macro insights. Please verify backend service.");
    } finally {
      setLoading(false);
    }
  };

  const fetchKeywords = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/analytics/keywords?min_vpi=${minVpiFilter}`);
      if (res.ok) {
        const data = await res.json();
        setKeywords(data.keywords || []);
      }
    } catch (err) {
      console.error("Error updating keywords:", err);
    }
  };

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
          <Link
            href="/leaderboard"
            className="flex items-center gap-1 bg-gray-900 hover:bg-gray-800 border border-gray-700 px-2.5 py-1 rounded-full text-gray-200 font-mono text-xs transition-colors"
          >
            <Trophy className="w-3.5 h-3.5 text-[#00E5FF]" />
            <span className="hidden sm:inline">Top 10 Creators</span>
          </Link>

          <Link
            href="/insights"
            className="flex items-center gap-1 bg-cyan-950/80 border border-cyan-500 px-2.5 py-1 rounded-full text-cyan-300 font-mono text-xs shadow-[0_0_10px_rgba(0,229,255,0.3)]"
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
        <div className="bg-gradient-to-b from-[#0B101B] to-[#070A10] border border-gray-800 rounded-2xl p-6 relative shadow-xl">
          <div className="absolute inset-0 rounded-2xl overflow-hidden pointer-events-none">
            <div className="absolute top-0 right-0 w-64 h-64 bg-[#00E5FF]/10 rounded-full blur-3xl" />
          </div>

          <div className="relative z-10">
            <div className="inline-flex items-center gap-1.5 text-[10px] font-mono text-cyan-300 bg-cyan-950/50 border border-cyan-500/30 px-3 py-0.5 rounded-full mb-2">
              <BarChart3 className="w-3 h-3 text-[#00E5FF]" />
              <span>Global Algorithmic Intelligence</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-black font-mono tracking-tight text-white flex items-center gap-3">
              Macro Insights & Analytics
            </h1>
            <p className="text-gray-400 mt-1 text-xs sm:text-sm font-sans max-w-2xl">
              Global Viral Performance Index (VPI) distribution, regional benchmarks, category density, and keyword mining.
            </p>
          </div>
        </div>

        {loading ? (
          <div className="flex flex-col items-center justify-center py-24 bg-[#070A10] rounded-2xl border border-gray-800">
            <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-[#00E5FF] mb-4"></div>
            <p className="text-gray-400 text-xs font-mono">Aggregating global VPI dataset & running keyword mining...</p>
          </div>
        ) : error ? (
          <div className="bg-red-950/40 border border-red-800 text-red-300 p-6 rounded-xl text-center font-mono text-xs">
            {error}
          </div>
        ) : (
          <>
            {/* SEZIONE 1: BENCHMARK REGIONALI & COUNTRY */}
            <section className="space-y-4">
              <div className="flex items-center justify-between pb-1 border-b border-gray-800/80">
                <h2 className="text-sm sm:text-base font-bold font-mono text-white flex items-center gap-2">
                  <Globe className="w-4 h-4 text-[#00E5FF]" />
                  <span>Macro-Region & Country Benchmarks</span>
                </h2>
                <span className="text-[10px] font-mono text-gray-500">Section 01</span>
              </div>

              {/* Macro-Regions Cards */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                {insights &&
                  Object.entries(insights.macro_regions || {}).map(([region, stat]) => (
                    <div
                      key={region}
                      className="bg-[#070A10] border border-gray-800 hover:border-cyan-500/40 transition-all rounded-2xl p-5 shadow-xl flex flex-col justify-between group"
                    >
                      <div>
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-gray-400">
                            {region}
                          </span>
                          <div className="p-1.5 bg-cyan-950/50 border border-cyan-500/20 rounded-lg text-[#00E5FF] group-hover:scale-110 transition-transform">
                            <Zap className="w-3.5 h-3.5" />
                          </div>
                        </div>
                        <div className="flex items-baseline justify-between mt-3">
                          <span className="text-2xl sm:text-3xl font-black font-mono text-[#00E5FF]">
                            +{stat.avg_vpi.toFixed(1)}x
                          </span>
                          <span className="text-[10px] font-mono text-cyan-300 bg-cyan-950/60 px-2.5 py-0.5 rounded-full border border-cyan-500/30">
                            {stat.outlier_count} Spikes
                          </span>
                        </div>
                      </div>
                      <p className="text-[10px] text-gray-500 mt-4 font-mono">Average VPI multiplier across region</p>
                    </div>
                  ))}
              </div>

              {/* Top Countries Table */}
              <div className="bg-[#070A10] border border-gray-800 rounded-2xl p-5 shadow-xl">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-gray-300 flex items-center gap-2">
                    <Flame className="w-3.5 h-3.5 text-amber-400" />
                    <span>Country VPI Performance Breakdown</span>
                  </h3>
                  <span className="text-[10px] font-mono text-gray-500">Sorted by Avg VPI</span>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
                  {insights &&
                    Object.entries(insights.by_country || {})
                      .sort((a, b) => b[1].avg_vpi - a[1].avg_vpi)
                      .map(([country, stat]) => (
                        <div
                          key={country}
                          className="bg-black/60 p-3 rounded-xl border border-gray-800 hover:border-gray-700 transition-all font-mono"
                        >
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-xs font-bold text-white">{country}</span>
                            <span className="text-[9px] text-gray-500">{stat.outlier_count} posts</span>
                          </div>
                          <div className="text-base font-black text-[#00E5FF]">
                            +{stat.avg_vpi.toFixed(1)}x
                          </div>
                        </div>
                      ))}
                </div>
              </div>
            </section>

            {/* SEZIONE 2: DISTRIBUZIONE CATEGORIE */}
            <section className="space-y-4 pt-2">
              <div className="flex items-center justify-between pb-1 border-b border-gray-800/80">
                <h2 className="text-sm sm:text-base font-bold font-mono text-white flex items-center gap-2">
                  <Layers className="w-4 h-4 text-[#00E5FF]" />
                  <span>Category Virality Density</span>
                </h2>
                <span className="text-[10px] font-mono text-gray-500">Section 02</span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {insights &&
                  Object.entries(insights.by_category || {})
                    .sort((a, b) => b[1].outlier_count - a[1].outlier_count)
                    .map(([cat, stat]) => (
                      <div
                        key={cat}
                        className="bg-[#070A10] border border-gray-800 hover:border-cyan-500/30 transition-all rounded-2xl p-4 flex items-center justify-between shadow-xl"
                      >
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <Tag className="w-3.5 h-3.5 text-[#00E5FF]" />
                            <h3 className="text-xs font-bold font-mono text-white">{cat}</h3>
                          </div>
                          <p className="text-[11px] text-gray-400 font-mono">
                            Detected Spikes: <strong className="text-white">{stat.outlier_count}</strong>
                          </p>
                        </div>
                        <div className="text-right font-mono">
                          <div className="text-lg font-black text-[#00E5FF]">
                            +{stat.avg_vpi.toFixed(1)}x
                          </div>
                          <div className="text-[8px] text-gray-500 uppercase tracking-wider">Avg Velocity</div>
                        </div>
                      </div>
                    ))}
              </div>
            </section>

            {/* SEZIONE 3: VIRAL KEYWORD CLOUD / RANKER */}
            <section className="space-y-4 pt-2">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-1 border-b border-gray-800/80">
                <div>
                  <h2 className="text-sm sm:text-base font-bold font-mono text-white flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-[#00E5FF]" />
                    <span>Viral Keyword Mining & Velocity Ranker</span>
                  </h2>
                </div>

                {/* Min VPI Filter Selector */}
                <div className="flex items-center gap-2 bg-[#070A10] p-1.5 rounded-xl border border-gray-800 self-start sm:self-auto font-mono">
                  <span className="text-[10px] text-gray-400 pl-2 font-medium">Min VPI Threshold:</span>
                  {[3.0, 5.0, 8.0].map((val) => (
                    <button
                      key={val}
                      onClick={() => setMinVpiFilter(val)}
                      className={`px-2.5 py-1 text-[11px] font-bold rounded-lg transition-all cursor-pointer ${
                        minVpiFilter === val
                          ? "bg-[#00E5FF] text-black shadow-md shadow-cyan-950/50"
                          : "text-gray-400 hover:text-white"
                      }`}
                    >
                      +{val.toFixed(1)}x
                    </button>
                  ))}
                </div>
              </div>

              {/* Word Cloud Representation */}
              <div className="bg-[#070A10] border border-gray-800 rounded-2xl p-5 shadow-xl">
                <h3 className="text-[10px] font-mono font-bold uppercase tracking-wider text-gray-400 mb-3">
                  Extracted Viral Keyword Cloud
                </h3>
                <div className="flex flex-wrap gap-2 items-center justify-center py-3">
                  {keywords.map((kw) => {
                    const sizeClass =
                      kw.viral_velocity >= 10
                        ? "text-sm px-3.5 py-1.5 bg-cyan-950/60 text-cyan-300 border-cyan-500/50 shadow-[0_0_12px_rgba(0,229,255,0.25)]"
                        : kw.viral_velocity >= 6
                        ? "text-xs px-3 py-1 bg-black text-[#00E5FF] border-gray-700 hover:border-cyan-500/40"
                        : "text-[11px] px-2.5 py-1 bg-black/80 text-gray-300 border-gray-800";

                    return (
                      <span
                        key={kw.keyword}
                        className={`font-mono font-bold rounded-xl border transition-all hover:scale-105 inline-flex items-center gap-1.5 cursor-default ${sizeClass}`}
                      >
                        #{kw.keyword}
                        <span className="text-[9px] opacity-75 font-normal">
                          (+{kw.viral_velocity.toFixed(1)}x)
                        </span>
                      </span>
                    );
                  })}
                </div>
              </div>

              {/* Keyword Analytics Table */}
              <div className="bg-[#070A10] border border-gray-800 rounded-2xl overflow-hidden shadow-xl">
                <div className="px-5 py-3 border-b border-gray-800 font-mono font-bold text-xs uppercase tracking-wider text-gray-300 flex items-center justify-between">
                  <span>Term Frequency & Velocity Ranker</span>
                  <span className="text-[10px] text-gray-500 font-normal">Top Recurrent Terms</span>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs text-gray-300 font-mono">
                    <thead className="bg-black text-gray-400 uppercase tracking-wider font-semibold border-b border-gray-800 text-[10px]">
                      <tr>
                        <th className="px-5 py-3">Keyword / Term</th>
                        <th className="px-5 py-3 text-center">Frequency (Occurrences)</th>
                        <th className="px-5 py-3 text-right">Avg Viral Velocity</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-800/60">
                      {keywords.slice(0, 15).map((kw, i) => (
                        <tr key={kw.keyword} className="hover:bg-black/60 transition-colors">
                          <td className="px-5 py-3 font-bold text-white flex items-center gap-2">
                            <span className="text-gray-500 text-[10px] w-4">#{i + 1}</span>
                            <span className="text-[#00E5FF]">#{kw.keyword}</span>
                          </td>
                          <td className="px-5 py-3 text-center font-medium text-gray-300">
                            {kw.frequency}
                          </td>
                          <td className="px-5 py-3 text-right font-black text-[#00E5FF]">
                            +{kw.viral_velocity.toFixed(1)}x
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </section>
          </>
        )}
      </div>

      {/* Modali Governance */}
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
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row justify-between items-center gap-3 text-[10px] text-gray-400">
          <p className="text-center md:text-left font-sans">
            © 2026 Institute for Open Social Analytics (IOSA). Independent research initiative.
          </p>
          <div className="flex items-center gap-4">
            <Link href="/" className="hover:text-[#00E5FF] transition-colors">Home Landing</Link>
            <Link href="/leaderboard" className="hover:text-[#00E5FF] transition-colors">Top 10 Outliers</Link>
          </div>
        </div>
      </footer>
    </main>
  );
}