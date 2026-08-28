"use client";

import React, { useState, useEffect } from "react";

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

export default function InsightsPage() {
  const [insights, setInsights] = useState<InsightsData | null>(null);
  const [keywords, setKeywords] = useState<KeywordItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [minVpiFilter, setMinVpiFilter] = useState<number>(5.0);
  const [error, setError] = useState<string | null>(null);

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
    <div className="min-h-screen bg-slate-950 text-slate-100 py-10 px-4 sm:px-6 lg:px-8 font-sans">
      <div className="max-w-7xl mx-auto space-y-12">
        
        {/* Header Section */}
        <div className="border-b border-slate-800 pb-6">
          <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-white flex items-center gap-3">
            📊 Macro Insights & Analytics
          </h1>
          <p className="text-slate-400 mt-2 text-sm sm:text-base">
            Global Viral Performance Index (VPI) distribution, regional benchmarks, category density, and keyword mining.
          </p>
        </div>

        {loading ? (
          <div className="flex flex-col items-center justify-center py-24 bg-slate-900/40 rounded-2xl border border-slate-800">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-amber-500 mb-4"></div>
            <p className="text-slate-400 text-sm">Aggregating global VPI dataset & running keyword mining...</p>
          </div>
        ) : error ? (
          <div className="bg-red-950/40 border border-red-800 text-red-300 p-6 rounded-xl text-center">
            {error}
          </div>
        ) : (
          <>
            {/* SEZIONE 1: BENCHMARK REGIONALI & COUNTRY */}
            <section className="space-y-6">
              <div className="flex items-center justify-between">
                <h2 className="text-xl font-bold text-white flex items-center gap-2">
                  <span>🌍</span> Sezione 1 — Macro-Region & Country Benchmarks
                </h2>
              </div>

              {/* Macro-Regions Cards */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                {insights &&
                  Object.entries(insights.macro_regions || {}).map(([region, stat]) => (
                    <div
                      key={region}
                      className="bg-slate-900/70 border border-slate-800 rounded-2xl p-5 hover:border-slate-700 transition-all"
                    >
                      <div className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1">
                        {region}
                      </div>
                      <div className="flex items-baseline justify-between mt-2">
                        <span className="text-3xl font-black text-amber-400">
                          +{stat.avg_vpi.toFixed(1)}x
                        </span>
                        <span className="text-xs font-medium text-slate-400 bg-slate-800 px-2.5 py-1 rounded-full border border-slate-700">
                          {stat.outlier_count} Outliers
                        </span>
                      </div>
                      <p className="text-xs text-slate-500 mt-3">Average VPI Multiplier across region</p>
                    </div>
                  ))}
              </div>

              {/* Top Countries Table */}
              <div className="bg-slate-900/40 border border-slate-800 rounded-2xl p-6">
                <h3 className="text-sm font-bold uppercase tracking-wider text-slate-300 mb-4">
                  Country VPI Performance Breakdown
                </h3>
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
                  {insights &&
                    Object.entries(insights.by_country || {})
                      .sort((a, b) => b[1].avg_vpi - a[1].avg_vpi)
                      .map(([country, stat]) => (
                        <div key={country} className="bg-slate-950 p-3 rounded-xl border border-slate-800/80">
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-xs font-bold text-slate-200">{country}</span>
                            <span className="text-[10px] text-slate-500">{stat.outlier_count} posts</span>
                          </div>
                          <div className="text-lg font-black text-amber-400">
                            +{stat.avg_vpi.toFixed(1)}x
                          </div>
                        </div>
                      ))}
                </div>
              </div>
            </section>

            {/* SEZIONE 2: DISTRIBUZIONE CATEGORIE */}
            <section className="space-y-6">
              <h2 className="text-xl font-bold text-white flex items-center gap-2">
                <span>🏷️</span> Sezione 2 — Category Virality Density
              </h2>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {insights &&
                  Object.entries(insights.by_category || {})
                    .sort((a, b) => b[1].outlier_count - a[1].outlier_count)
                    .map(([cat, stat]) => (
                      <div
                        key={cat}
                        className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 flex items-center justify-between"
                      >
                        <div>
                          <h3 className="text-base font-bold text-white">{cat}</h3>
                          <p className="text-xs text-slate-400 mt-0.5">
                            Total Detected: <strong className="text-slate-200">{stat.outlier_count}</strong>
                          </p>
                        </div>
                        <div className="text-right">
                          <div className="text-2xl font-black text-amber-400">
                            +{stat.avg_vpi.toFixed(1)}x
                          </div>
                          <div className="text-[10px] text-slate-500 uppercase tracking-wider">Avg Velocity</div>
                        </div>
                      </div>
                    ))}
              </div>
            </section>

            {/* SEZIONE 3: VIRAL KEYWORD CLOUD / RANKER */}
            <section className="space-y-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                  <h2 className="text-xl font-bold text-white flex items-center gap-2">
                    <span>🔥</span> Sezione 3 — Viral Keyword Mining & Ranker
                  </h2>
                  <p className="text-xs text-slate-400 mt-1">
                    Most recurrent high-performing terms extracted from high-VPI content titles.
                  </p>
                </div>

                {/* Min VPI Filter Selector */}
                <div className="flex items-center gap-2 bg-slate-900 p-1.5 rounded-xl border border-slate-800 self-start sm:self-auto">
                  <span className="text-xs text-slate-400 pl-2 font-medium">Min VPI Threshold:</span>
                  {[3.0, 5.0, 8.0].map((val) => (
                    <button
                      key={val}
                      onClick={() => setMinVpiFilter(val)}
                      className={`px-3 py-1 text-xs font-bold rounded-lg transition-all ${
                        minVpiFilter === val
                          ? "bg-amber-500 text-slate-950"
                          : "text-slate-400 hover:text-white"
                      }`}
                    >
                      +{val.toFixed(1)}x
                    </button>
                  ))}
                </div>
              </div>

              {/* Word Cloud Representation */}
              <div className="bg-slate-900/50 border border-slate-800 rounded-2xl p-6">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-4">
                  Viral Keyword Cloud
                </h3>
                <div className="flex flex-wrap gap-2.5 items-center justify-center py-4">
                  {keywords.map((kw) => {
                    const sizeClass =
                      kw.viral_velocity >= 10
                        ? "text-xl px-4 py-2 bg-amber-500/20 text-amber-300 border-amber-500/40"
                        : kw.viral_velocity >= 6
                        ? "text-base px-3 py-1.5 bg-slate-800 text-amber-400 border-slate-700"
                        : "text-xs px-2.5 py-1 bg-slate-950 text-slate-300 border-slate-800";

                    return (
                      <span
                        key={kw.keyword}
                        className={`font-bold rounded-xl border transition-transform hover:scale-105 inline-flex items-center gap-1.5 ${sizeClass}`}
                      >
                        #{kw.keyword}
                        <span className="text-[10px] opacity-75 font-normal">
                          (+{kw.viral_velocity.toFixed(1)}x)
                        </span>
                      </span>
                    );
                  })}
                </div>
              </div>

              {/* Keyword Analytics Table */}
              <div className="bg-slate-900/40 border border-slate-800 rounded-2xl overflow-hidden">
                <div className="px-6 py-4 border-b border-slate-800 font-bold text-sm text-slate-200">
                  Term Frequency & Velocity Ranker
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs text-slate-300">
                    <thead className="bg-slate-950 text-slate-400 uppercase tracking-wider font-semibold border-b border-slate-800">
                      <tr>
                        <th className="px-6 py-3">Keyword / Term</th>
                        <th className="px-6 py-3 text-center">Frequency (Occurrences)</th>
                        <th className="px-6 py-3 text-right">Avg Viral Velocity</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60">
                      {keywords.slice(0, 15).map((kw, i) => (
                        <tr key={kw.keyword} className="hover:bg-slate-800/30 transition-colors">
                          <td className="px-6 py-3.5 font-bold text-white flex items-center gap-2">
                            <span className="text-slate-500 text-[10px] w-4">#{i + 1}</span>
                            <span>{kw.keyword}</span>
                          </td>
                          <td className="px-6 py-3.5 text-center font-medium text-slate-300">
                            {kw.frequency}
                          </td>
                          <td className="px-6 py-3.5 text-right font-black text-amber-400">
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
    </div>
  );
}