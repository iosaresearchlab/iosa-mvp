'use client';

import { use, useState, useEffect } from 'react';
import Link from 'next/link';
import { createClient } from '@supabase/supabase-js';
import { ShieldCheck, CheckCircle2, Timer, Calendar, Loader2, Sparkles, ArrowLeft, CupSoda, Award, Download, Heart } from 'lucide-react';
import ClaimForm from './ClaimForm';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || '';
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || '';
const supabase = createClient(supabaseUrl, supabaseAnonKey);

function formatCount(val: any): string {
  if (val === null || val === undefined) return 'N/A';
  let num: number;
  if (typeof val === 'number') {
    num = val;
  } else if (typeof val === 'string') {
    const cleaned = val.replace(/,/g, '').trim();
    num = Number(cleaned);
    if (isNaN(num)) return val;
  } else {
    return String(val);
  }

  if (num >= 1_000_000) {
    return `${(num / 1_000_000).toFixed(1)}M`;
  } else if (num >= 1_000) {
    return `${(num / 1_000).toFixed(1)}K`;
  }
  return Number.isInteger(num) ? String(num) : String(num);
}

function getBadgeStyle(levelName?: string, vpiScore?: any): string {
  let lvl = 0;
  if (levelName) {
    const match = levelName.match(/LVL\s*(\d+)/i);
    if (match) lvl = parseInt(match[1], 10);
  }
  if (!lvl && vpiScore) {
    const v = parseFloat(String(vpiScore).replace(/[^\d.]/g, '')) || 0;
    if (v >= 100) lvl = 10;
    else if (v >= 50) lvl = 9;
    else if (v >= 25) lvl = 8;
    else if (v >= 15) lvl = 7;
    else if (v >= 10) lvl = 6;
    else if (v >= 5) lvl = 5;
    else if (v >= 3) lvl = 4;
    else if (v >= 2) lvl = 3;
    else if (v >= 1.5) lvl = 2;
    else lvl = 1;
  }

  if (lvl >= 10) {
    return 'bg-gradient-to-r from-amber-500/20 via-yellow-500/20 to-amber-500/20 text-yellow-300 border border-yellow-400/50 shadow-[0_0_15px_rgba(234,179,8,0.3)]';
  } else if (lvl >= 8) {
    return 'bg-purple-500/20 text-purple-300 border border-purple-400/40 shadow-[0_0_15px_rgba(168,85,247,0.3)]';
  } else if (lvl >= 5) {
    return 'bg-amber-500/20 text-amber-300 border border-amber-500/30 shadow-[0_0_15px_rgba(245,158,11,0.2)]';
  } else if (lvl >= 3) {
    return 'bg-cyan-500/20 text-cyan-300 border border-cyan-400/40 shadow-[0_0_15px_rgba(6,182,212,0.3)]';
  }
  return 'bg-slate-500/20 text-slate-300 border border-slate-400/40 shadow-[0_0_10px_rgba(148,163,184,0.2)]';
}

const MOCK_POSTS: Record<string, any> = {
  'REC_8F9A2B': {
    author_handle: '@TEARDOWNMAYHEM',
    vpi_ratio: 8.7,
    vpi_level_name: 'LVL 5 — OUTLIER',
    title: 'Rick Astley - Never Gonna Give You Up',
    created_at: '2026-08-20',
    detected_at: '2026-08-21',
    platform: 'youtube',
    baseline_score: '10.0K',
    engagement_score: '87.2K',
  },
};

export default function ClaimPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const resolvedParams = use(params);
  const token = resolvedParams.token;

  const [post, setPost] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [artifactLoading, setArtifactLoading] = useState(true);
  
  // Tab state switcher
  const [activeTab, setActiveTab] = useState<'plaque' | 'mug'>('plaque');

  const [tokenWindow, setTokenWindow] = useState({ start: '', end: '' });
  const [timeLeft, setTimeLeft] = useState({ days: 14, hours: 23, minutes: 59, seconds: 59 });
  const [isExpired, setIsExpired] = useState(false);
  const [isOrderSuccess, setIsOrderSuccess] = useState(false);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const urlParams = new URLSearchParams(window.location.search);
      if (urlParams.get('status') === 'success') {
        setIsOrderSuccess(true);
      }
    }
  }, []);

  useEffect(() => {
    async function fetchPost() {
      try {
        const { data } = await supabase
          .from('posts')
          .select('*')
          .eq('claim_token', token)
          .single();

        let currentPost = data;
        if (!currentPost && MOCK_POSTS[token]) {
          currentPost = MOCK_POSTS[token];
        }

        setPost(currentPost || null);
      } catch {
        setPost(MOCK_POSTS[token] || null);
      } finally {
        setLoading(false);
      }
    }

    if (token) {
      fetchPost();
    }
  }, [token]);

  useEffect(() => {
    if (!post || !post.created_at) return;

    const createdAt = new Date(post.created_at);
    const expiresAt = new Date(createdAt.getTime() + 15 * 24 * 60 * 60 * 1000);

    setTokenWindow({
      start: createdAt.toLocaleDateString('en-US', { day: 'numeric', month: 'short', year: 'numeric' }),
      end: expiresAt.toLocaleDateString('en-US', { day: 'numeric', month: 'short', year: 'numeric' }),
    });

    const updateCountdown = () => {
      const now = new Date();
      const diff = expiresAt.getTime() - now.getTime();

      if (diff <= 0) {
        setIsExpired(true);
        setTimeLeft({ days: 0, hours: 0, minutes: 0, seconds: 0 });
      } else {
        const days = Math.floor(diff / (1000 * 60 * 60 * 24));
        const hours = Math.floor((diff / (1000 * 60 * 60)) % 24);
        const minutes = Math.floor((diff / 1000 / 60) % 60);
        const seconds = Math.floor((diff / 1000) % 60);
        setTimeLeft({ days, hours, minutes, seconds });
      }
    };

    updateCountdown();
    const timer = setInterval(updateCountdown, 1000);
    return () => clearInterval(timer);
  }, [post]);

  if (loading) {
    return (
      <main className="min-h-screen bg-[#030508] text-white font-mono flex items-center justify-center p-6">
        <div className="text-xs text-[#00E5FF] animate-pulse font-mono tracking-widest flex items-center gap-2">
          <Loader2 className="w-4 h-4 animate-spin text-[#00E5FF]" /> RETRIEVING ACCREDITATION PARAMETERS...
        </div>
      </main>
    );
  }

  if (!post) {
    return (
      <main className="min-h-screen bg-[#030508] text-white font-mono flex items-center justify-center p-6">
        <div className="max-w-md w-full bg-[#070A10] border border-red-500/30 rounded-xl p-8 text-center shadow-2xl flex flex-col items-center gap-4">
          <h1 className="text-xl font-bold text-red-400">404 — INVALID TOKEN</h1>
          <p className="text-xs text-gray-400">
            This verification link does not exist or has expired from the active evaluation window.
          </p>
          <Link 
            href="/" 
            className="inline-flex items-center gap-2 text-xs font-mono text-white bg-gray-900 hover:bg-gray-800 border border-gray-700 hover:border-[#00E5FF]/50 px-4 py-2 rounded-full transition-all mt-2"
          >
            <ArrowLeft className="w-3.5 h-3.5 text-[#00E5FF]" /> Return to Home
          </Link>
        </div>
      </main>
    );
  }

  const formattedVpi = Number(post.vpi_ratio || 0).toFixed(1);
  const postTitle = post.content_text || post.title || post.content_title || 'Viral Video Accreditation';

  const trophyPayload = {
    author: post.author_handle || 'Creator',
    vpi_ratio: `+${formattedVpi}x`,
    level_name: post.vpi_level_name || 'LVL 5 — OUTLIER',
    content_title: postTitle,
    date_str: post.created_at
      ? new Date(post.created_at).toISOString().split('T')[0]
      : '2026-08-20',
    e_act: formatCount(post.engagement_score ?? post.e_act),
    e_base: formatCount(post.baseline_score ?? post.e_base),
  };

  const mugMockupUrl = `${BACKEND_URL}/api/trophy/preview-mug?author=${encodeURIComponent(trophyPayload.author)}&vpi=${encodeURIComponent(trophyPayload.vpi_ratio)}`;
  
  // Pass all dynamic parameters in the query string to render real breakdown data
  const plaquePreviewUrl = `${BACKEND_URL}/api/trophy/preview?author=${encodeURIComponent(trophyPayload.author)}&vpi=${encodeURIComponent(trophyPayload.vpi_ratio)}&e_act=${encodeURIComponent(trophyPayload.e_act)}&e_base=${encodeURIComponent(trophyPayload.e_base)}&content_title=${encodeURIComponent(trophyPayload.content_title)}&title=${encodeURIComponent(trophyPayload.content_title)}&level_name=${encodeURIComponent(trophyPayload.level_name)}&date_str=${encodeURIComponent(trophyPayload.date_str)}`;

  const currentPreviewUrl = activeTab === 'plaque' ? plaquePreviewUrl : mugMockupUrl;

  const formattedDetectedDate = post.detected_at 
    ? new Date(post.detected_at).toLocaleDateString('en-US', { day: '2-digit', month: 'short', year: 'numeric' })
    : (post.created_at ? new Date(post.created_at).toLocaleDateString('en-US', { day: '2-digit', month: 'short', year: 'numeric' }) : 'N/A');

  return (
    <main className="min-h-screen bg-[#030508] text-white font-sans p-3 sm:p-4 md:p-6 pt-0 sm:pt-0 md:pt-0 relative overflow-x-hidden flex flex-col">
      
      {/* Fixed Header Container */}
      <header className="sticky top-0 z-50 bg-[#030508]/90 backdrop-blur-md max-w-5xl mx-auto w-full border-b border-gray-800/80 py-3 mb-3 flex flex-row justify-between items-center gap-4">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-3">
            <div className="flex items-end gap-1.5">
              <svg className="h-6 w-3.5 text-[#00E5FF]" viewBox="0 0 18.5 32" fill="none">
                <path d="M1 26.5H6.5L14 8.5L17.5 14" stroke="currentColor" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round"/>
                <circle cx="14" cy="3" r="3" fill="#00E5FF"/>
              </svg>
              <span className="font-mono font-black text-lg tracking-tighter text-white leading-none">OSA</span>
            </div>
          </div>
          <span className="text-[8px] font-mono text-gray-400 tracking-widest uppercase opacity-90">
            Institute for Open Social Analytics
          </span>
        </div>

        {/* Badge: Clean Verified Accreditation Status */}
        <div className="flex items-center gap-2 text-xs font-mono text-[#00E5FF] bg-cyan-950/40 border border-cyan-500/30 px-3 py-1 rounded-full shadow-sm">
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-400 shrink-0" /> 
          <span className="text-[9px] sm:text-[11px] font-bold tracking-wider">VERIFIED ACCREDITATION</span>
        </div>
      </header>

      {/* Navigation Return Link */}
      <div className="max-w-5xl mx-auto w-full mb-3">
        <Link 
          href="/" 
          className="inline-flex items-center gap-2 text-[10px] font-mono text-gray-400 hover:text-white transition-colors group"
        >
          <ArrowLeft className="w-3 h-3 text-[#00E5FF] group-hover:-translate-x-1 transition-transform" /> 
          RETURN TO HOME
        </Link>
      </div>

      {/* Confirmation Order Banner */}
      {isOrderSuccess && (
        <div className="max-w-5xl mx-auto w-full mb-3 bg-emerald-950/60 border border-emerald-500/50 rounded-xl p-4 shadow-xl backdrop-blur-md flex flex-col md:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-emerald-500/20 border border-emerald-500/40 rounded-full flex items-center justify-center shrink-0">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            </div>
            <div>
              <h3 className="font-mono font-bold text-xs text-emerald-300">ACCREDITATION ORDER CONFIRMED</h3>
              <p className="text-[11px] text-gray-300 font-sans mt-0.5">
                Payment verified. Your commemorative metric award for <span className="font-bold text-white">{post.author_handle}</span> is queued for production.
              </p>
            </div>
          </div>
          <span className="text-[9px] font-mono bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 px-2.5 py-0.5 rounded-full uppercase tracking-wider shrink-0">
            In Production
          </span>
        </div>
      )}

      {/* Validity Banner */}
      <div className="max-w-5xl mx-auto w-full mb-3 grid grid-cols-1 md:grid-cols-2 gap-3 font-mono text-xs">
        <div className="bg-gradient-to-r from-cyan-950/40 via-blue-950/20 to-cyan-950/40 border border-cyan-500/30 rounded-xl p-3 flex items-center gap-3 shadow-md">
          <Calendar className="w-3.5 h-3.5 text-[#00E5FF] shrink-0" />
          <div>
            <span className="text-gray-400 block text-[9px] mb-0.5">POST VALIDITY WINDOW (15 DAYS)</span>
            <span className="text-white font-bold text-[11px]">{tokenWindow.start} - {tokenWindow.end}</span>
          </div>
        </div>

        <div className={`bg-gradient-to-r ${isExpired ? 'from-red-950/40 via-red-950/20 to-red-950/40 border-red-500/30 text-red-400' : 'from-amber-950/40 via-red-950/20 to-amber-950/40 border-amber-500/30 text-amber-300'} border rounded-xl p-3 flex items-center gap-3 shadow-md`}>
          <Timer className={`w-3.5 h-3.5 ${isExpired ? 'text-red-400' : 'text-amber-400 animate-pulse'} shrink-0`} />
          <div>
            <span className="opacity-80 block text-[9px] mb-0.5">CLAIM TOKEN EXPIRES IN</span>
            <span className="font-bold text-[11px]">
              {isExpired ? 'EXPIRED' : `${timeLeft.days}d ${timeLeft.hours}h ${timeLeft.minutes}m ${timeLeft.seconds}s`}
            </span>
          </div>
        </div>
      </div>

      <div className="max-w-5xl mx-auto w-full grid grid-cols-1 lg:grid-cols-2 gap-4 items-stretch pb-2">
        
        {/* Left Showcase Box */}
        <div className="bg-[#070A10] border border-gray-800 rounded-xl p-4 flex flex-col justify-between items-center text-center shadow-xl relative overflow-hidden">
          <div className="absolute -right-12 -top-12 w-32 h-32 bg-[#00E5FF]/10 rounded-full blur-2xl pointer-events-none" />

          {/* Switcher Tab */}
          <div className="flex items-center gap-2 p-1 bg-black/60 border border-gray-800 rounded-xl mb-3 w-full">
            <button
              onClick={() => { setActiveTab('plaque'); setArtifactLoading(true); }}
              className={`flex-1 flex items-center justify-center gap-2 py-2 px-3 rounded-lg text-xs font-mono whitespace-nowrap transition-all ${
                activeTab === 'plaque' 
                  ? 'bg-[#00E5FF]/10 text-[#00E5FF] border border-[#00E5FF]/40 font-bold shadow-sm' 
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              <Award className="w-4 h-4 shrink-0" /> Digital Plaque
            </button>
            <button
              onClick={() => { setActiveTab('mug'); setArtifactLoading(true); }}
              className={`flex-1 flex items-center justify-center gap-2 py-2 px-3 rounded-lg text-xs font-mono whitespace-nowrap transition-all ${
                activeTab === 'mug' 
                  ? 'bg-[#00E5FF]/10 text-[#00E5FF] border border-[#00E5FF]/40 font-bold shadow-sm' 
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              <CupSoda className="w-4 h-4 shrink-0" /> Physical Artifact
            </button>
          </div>

          <div className="w-full flex flex-col items-center flex-grow justify-center mb-2">
            
            {/* Download and Preview Viewport */}
            <div className="w-full mx-auto h-[240px] sm:h-[270px] rounded-xl bg-black/50 border border-[#00E5FF]/30 flex flex-col items-center justify-center mb-2 overflow-hidden relative group shadow-lg p-2">
              {artifactLoading && (
                <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/80 z-10 font-mono text-[10px] text-[#00E5FF] gap-2">
                  <Loader2 className="w-5 h-5 animate-spin text-[#00E5FF]" />
                  <span>RENDERING PREVIEW...</span>
                </div>
              )}
              <img 
                key={currentPreviewUrl}
                src={currentPreviewUrl}
                alt={activeTab === 'plaque' ? "Accreditation Plaque Preview" : "IOSA Physical Artifact Sample"}
                onLoad={() => setArtifactLoading(false)}
                onError={(e) => {
                  setArtifactLoading(false);
                  (e.target as HTMLElement).style.display = 'none';
                }}
                className={`w-full h-full object-contain transform group-hover:scale-105 transition-transform duration-300 ${artifactLoading ? 'opacity-0' : 'opacity-100'}`}
              />

              {activeTab === 'plaque' && !artifactLoading && (
                <div className="absolute bottom-2 inset-x-2 flex flex-col items-center z-20">
                  <a
                    href={plaquePreviewUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    download={`${trophyPayload.author}_VPI_Plaque.png`}
                    className="w-full py-2 px-3 bg-[#00E5FF] hover:bg-[#00B4D8] text-black font-mono font-bold text-xs rounded-lg shadow-xl flex items-center justify-center gap-2 transition-all backdrop-blur-md"
                  >
                    <Download className="w-3.5 h-3.5" /> Download Digital Plaque (.PNG)
                  </a>
                </div>
              )}
            </div>

            <p className="text-[10px] font-mono text-gray-400 mb-2 flex items-center justify-center gap-1">
              <CheckCircle2 className="w-3 h-3 text-cyan-400 shrink-0" /> Includes verified QR code for instant authenticity proof.
            </p>

            <span className={`text-[11px] font-mono px-2.5 py-0.5 rounded-full font-bold uppercase mb-1.5 ${getBadgeStyle(post.vpi_level_name, post.vpi_ratio)}`}>
              {post.vpi_level_name}
            </span>

            <h2 className="text-3xl sm:text-4xl font-black font-mono tracking-tight text-white mb-1">
              +{formattedVpi}x <span className="text-[#00E5FF]">VPI</span>
            </h2>
            <p className="text-[11px] font-mono text-gray-400">Viral Performance Index Accredited</p>
          </div>

          {/* Post Metrics Details */}
          <div className="w-full mt-auto border-t border-gray-800/80 pt-3 text-left space-y-2 font-mono text-xs text-gray-300 bg-black/40 p-3 rounded-xl border border-gray-800/60">
            <div className="flex flex-col gap-1 pb-2 border-b border-gray-800/60">
              <span className="text-[9px] text-gray-500 uppercase tracking-wider">ACCREDITED POST TITLE:</span>
              <span className="font-bold text-white text-[11px] leading-snug">{postTitle}</span>
            </div>

            <div className="flex justify-between items-center text-[11px]">
              <span className="text-gray-500">CREATOR:</span>
              <span className="font-bold text-white">{post.author_handle}</span>
            </div>

            <div className="flex justify-between items-center text-[11px]">
              <span className="text-gray-500">PUBLISHED DATE:</span>
              <span className="text-gray-300 font-medium">
                {post.created_at ? new Date(post.created_at).toLocaleDateString('en-US', { day: '2-digit', month: 'short', year: 'numeric' }) : 'N/A'}
              </span>
            </div>

            <div className="flex justify-between items-center text-[11px]">
              <span className="text-[#00E5FF]">DETECTION DATE:</span>
              <span className="text-[#00E5FF] font-medium">
                {formattedDetectedDate}
              </span>
            </div>

            <div className="flex justify-between items-center text-[11px]">
              <span className="text-gray-500">PLATFORM:</span>
              <span className="uppercase text-cyan-400 font-bold">{post.platform || 'YOUTUBE'}</span>
            </div>

            <div className="flex justify-between items-center text-[11px]">
              <span className="text-gray-500">BASELINE (E_base):</span>
              <span>{formatCount(post.baseline_score ?? post.e_base)}</span>
            </div>

            <div className="flex justify-between items-center text-[11px]">
              <span className="text-gray-500">ACTUAL VIEWS (E_act):</span>
              <span className="text-[#00E5FF] font-bold">{formatCount(post.engagement_score ?? post.e_act)}</span>
            </div>
          </div>
        </div>

        {/* Right Column: Order Form with Single Consolidated Support Notice */}
        <div className="bg-[#070A10]/90 border border-gray-800 rounded-xl p-4 sm:p-5 shadow-xl flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2 mb-3">
              <Heart className="w-5 h-5 text-[#00E5FF]" />
              <h1 className="text-xl font-extrabold font-mono">Support IOSA Research</h1>
            </div>

            {/* Consolidated Support Box */}
            <div className="bg-black/60 border border-gray-800 rounded-xl p-4 mb-4 font-mono space-y-2">
              <div className="flex items-center gap-2 text-[#00E5FF] font-bold text-xs tracking-wide">
                <Sparkles className="w-4 h-4 shrink-0 text-cyan-400" />
                <span>100% OPTIONAL SUPPORT</span>
              </div>
              <p className="text-sm font-sans text-gray-300 leading-relaxed">
                Digital plaques and analytical reports are <span className="text-white font-semibold">100% free forever</span>. Ordering a physical trophy is completely optional and directly powers our open-source tracking nodes and algorithm audits.
              </p>
            </div>

            {isExpired ? (
              <div className="bg-red-950/40 border border-red-500/50 rounded-xl p-4 text-center text-xs font-mono text-red-400 shadow-inner">
                This claim token has expired. The 15-day validity window from publication has closed.
              </div>
            ) : (
              <ClaimForm 
                claimToken={token} 
                postData={trophyPayload} 
                buttonText="Support IOSA: Order Trophy ($19.00)"
                buttonSubtext="100% optional. Thank you for supporting open data analytics!"
              />
            )}
          </div>

          <p className="text-[9px] text-gray-500 font-mono text-center mt-4 pt-3 border-t border-gray-800/60 flex items-center justify-center gap-1.5">
            <CheckCircle2 className="w-3 h-3 text-cyan-400" /> Powered by OSA Open Data Standard
          </p>
        </div>
      </div>

      {/* Footer Disclaimer */}
      <footer className="max-w-5xl mx-auto w-full mt-2 pt-2 border-t border-gray-800/60 text-[10px] text-gray-500 font-mono text-center leading-relaxed">
        <p>
          <strong className="text-gray-400">PROJECT DISCLAIMER:</strong> IOSA (Institute for Open Social Analytics) is an independent non-profit data research initiative. This platform and its metric certifications (VPI) are not affiliated with, endorsed by, sponsored by, or associated with YouTube, Google LLC, or any other third-party social media platform.
        </p>
      </footer>
    </main>
  );
}