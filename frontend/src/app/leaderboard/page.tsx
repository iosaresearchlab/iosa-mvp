"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";

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

export default function LeaderboardPage() {
  const [timeframe, setTimeframe] = useState<"24h" | "7d">("24h");
  const [selectedCountry, setSelectedCountry] = useState<string>("ALL");
  const [selectedCategory, setSelectedCategory] = useState<string>("ALL");
  
  const [topPosts, setTopPosts] = useState<Post[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

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
    <div className="min-h-screen bg-slate-950 text-slate-100 py-10 px-4 sm:px-6 lg:px-8 font-sans">
      <div className="max-w-6xl mx-auto">
        
        {/* Header */}
        <div className="mb-8 border-b border-slate-800 pb-6">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div>
              <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-white flex items-center gap-3">
                🏆 Outlier Leaderboard
              </h1>
              <p className="text-slate-400 mt-2 text-sm sm:text-base">
                Real-time rank of top viral performers detected by the Viral Performance Index algorithm.
              </p>
            </div>

            {/* Timeframe Switch */}
            <div className="inline-flex p-1 bg-slate-900 border border-slate-800 rounded-lg self-start md:self-auto">
              <button
                onClick={() => setTimeframe("24h")}
                className={`px-4 py-2 text-sm font-semibold rounded-md transition-all ${
                  timeframe === "24h"
                    ? "bg-amber-500 text-slate-950 shadow-md"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                Past 24 Hours
              </button>
              <button
                onClick={() => setTimeframe("7d")}
                className={`px-4 py-2 text-sm font-semibold rounded-md transition-all ${
                  timeframe === "7d"
                    ? "bg-amber-500 text-slate-950 shadow-md"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                Past 7 Days
              </button>
            </div>
          </div>
        </div>

        {/* Filters Bar */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-8 bg-slate-900/60 p-4 rounded-xl border border-slate-800">
          {/* Country Filter */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
              Filter by Country
            </label>
            <select
              value={selectedCountry}
              onChange={(e) => setSelectedCountry(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 text-slate-200 text-sm rounded-lg p-2.5 focus:ring-2 focus:ring-amber-500 focus:outline-none"
            >
              {COUNTRIES.map((c) => (
                <option key={c.code} value={c.code}>
                  {c.label}
                </option>
              ))}
            </select>
          </div>

          {/* Category Filter */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
              Filter by Category
            </label>
            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 text-slate-200 text-sm rounded-lg p-2.5 focus:ring-2 focus:ring-amber-500 focus:outline-none"
            >
              {CATEGORIES.map((cat) => (
                <option key={cat} value={cat}>
                  {cat === "ALL" ? "All Categories" : cat}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Leaderboard Table / Cards */}
        {loading ? (
          <div className="flex flex-col items-center justify-center py-20 bg-slate-900/40 rounded-2xl border border-slate-800">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-amber-500 mb-4"></div>
            <p className="text-slate-400 text-sm">Calculating viral velocity rankings...</p>
          </div>
        ) : error ? (
          <div className="bg-red-950/40 border border-red-800 text-red-300 p-6 rounded-xl text-center">
            {error}
          </div>
        ) : topPosts.length === 0 ? (
          <div className="bg-slate-900/40 border border-slate-800 text-slate-400 p-12 rounded-2xl text-center">
            <p className="text-lg font-medium">No viral outliers found for the selected filters.</p>
            <p className="text-sm text-slate-500 mt-1">Try resetting country or category options.</p>
          </div>
        ) : (
          <div className="space-y-4">
            {topPosts.map((post, idx) => {
              const rank = idx + 1;
              const isTop3 = rank <= 3;

              return (
                <div
                  key={post.id || idx}
                  className={`flex flex-col md:flex-row items-start md:items-center justify-between p-5 rounded-2xl border transition-all ${
                    rank === 1
                      ? "bg-amber-950/20 border-amber-500/50 hover:border-amber-500"
                      : rank === 2
                      ? "bg-slate-900/80 border-slate-400/40 hover:border-slate-400"
                      : rank === 3
                      ? "bg-amber-900/10 border-amber-700/40 hover:border-amber-700"
                      : "bg-slate-900/40 border-slate-800 hover:border-slate-700"
                  }`}
                >
                  {/* Left Section: Rank + Info */}
                  <div className="flex items-start gap-4 mb-4 md:mb-0 w-full md:w-auto">
                    {/* Rank Badge */}
                    <div
                      className={`flex-shrink-0 w-10 h-10 rounded-xl flex items-center justify-center font-black text-lg ${
                        rank === 1
                          ? "bg-amber-500 text-slate-950 shadow-lg shadow-amber-500/20"
                          : rank === 2
                          ? "bg-slate-300 text-slate-950"
                          : rank === 3
                          ? "bg-amber-700 text-white"
                          : "bg-slate-800 text-slate-400"
                      }`}
                    >
                      #{rank}
                    </div>

                    {/* Content Details */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap mb-1">
                        <span className="text-xs font-bold text-amber-400 tracking-wide uppercase">
                          {post.author_handle || "@Creator"}
                        </span>
                        <span className="text-slate-600">•</span>
                        <span className="text-xs bg-slate-800 text-slate-300 px-2 py-0.5 rounded-full border border-slate-700">
                          {post.country || "Global"}
                        </span>
                        <span className="text-xs bg-slate-800 text-slate-300 px-2 py-0.5 rounded-full border border-slate-700">
                          {post.category || "General"}
                        </span>
                      </div>

                      <h3 className="text-base sm:text-lg font-bold text-white line-clamp-1 pr-2">
                        {post.content_text || "Untitled Outlier Content"}
                      </h3>

                      <div className="flex items-center gap-4 mt-2 text-xs text-slate-400">
                        <span>Actual: <strong className="text-slate-200">{formatNumber(post.engagement_score)}</strong></span>
                        <span>Baseline: <strong className="text-slate-200">{formatNumber(post.baseline_score)}</strong></span>
                      </div>
                    </div>
                  </div>

                  {/* Right Section: VPI Score & Actions */}
                  <div className="flex items-center justify-between md:justify-end gap-6 w-full md:w-auto border-t md:border-t-0 border-slate-800 pt-3 md:pt-0">
                    <div className="text-left md:text-right">
                      <div className="text-2xl font-black text-amber-400 tracking-tight">
                        +{Number(post.vpi_ratio || 1.0).toFixed(1)}x
                      </div>
                      <div className="text-[10px] font-semibold tracking-wider text-slate-500 uppercase">
                        {post.vpi_level_name || "Lvl 2 Outlier"}
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      {post.claim_token && (
                        <Link
                          href={`/claim/${post.claim_token}`}
                          className="px-4 py-2 text-xs font-bold rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 transition-colors shadow-sm"
                        >
                          Claim Award
                        </Link>
                      )}
                      {post.url && (
                        <a
                          href={post.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="p-2 text-xs font-semibold rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors"
                          title="Watch Source Video"
                        >
                          ↗
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
    </div>
  );
}