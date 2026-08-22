'use client';

import { use, useState, useEffect } from 'react';
import Link from 'next/link';
import { createClient } from '@supabase/supabase-js';
import { ShieldCheck, CheckCircle2, Timer, Calendar, Loader2, Sparkles, ArrowLeft, CupSoda, Award } from 'lucide-react';
import ClaimForm from './ClaimForm';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || '';
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || '';
const supabase = createClient(supabaseUrl, supabaseAnonKey);

const MOCK_POSTS: Record<string, any> = {
  'REC_8F9A2B': {
    author_handle: '@TEARDOWNMAYHEM',
    vpi_ratio: 8.7,
    vpi_level_name: 'LVL 5 — OUTLIER',
    title: 'Rick Astley - Never Gonna Give You Up',
    created_at: '2026-08-20',
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
  
  // Toggle between Digital Plaque (default on left) and Physical Artifact (on right)
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
  };

  const mugMockupUrl = `${BACKEND_URL}/api/trophy/preview-mug?author=${encodeURIComponent(trophyPayload.author)}&vpi=${encodeURIComponent(trophyPayload.vpi_ratio)}`;
  const plaquePreviewUrl = `${BACKEND_URL}/api/trophy/preview?author=${encodeURIComponent(trophyPayload.author)}&vpi=${encodeURIComponent(trophyPayload.vpi_ratio)}`;

  const currentPreviewUrl = activeTab === 'plaque' ? plaquePreviewUrl : mugMockupUrl;

  return (
    <main className="min-h-screen bg-[#030508] text-white font-sans p-4 sm:p-6 md:p-8 relative overflow-hidden flex flex-col">
      
      {/* Integrated Compact Header */}
      <header className="max-w-5xl mx-auto w-full border-b border-gray-800/80 pb-4 mb-4 flex flex-row justify-between items-center gap-4">
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-3">
            <div className="flex items-end gap-1.5">
              <svg className="h-7 w-4 text-[#00E5FF]" viewBox="0 0 18.5 32" fill="none">
                <path d="M1 26.5H6.5L14 8.5L17.5 14" stroke="currentColor" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round"/>
                <circle cx="14" cy="3" r="3" fill="#00E5FF"/>
              </svg>
              <span className="font-mono font-black text-xl tracking-tighter text-white leading-none">OSA</span>
            </div>
          </div>
          <span className="text-[9px] font-mono text-gray-400 tracking-widest uppercase opacity-90">
            Institute for Open Social Analytics
          </span>
        </div>

        {/* Verified Accreditation Badge with Green Shield */}
        <div className="flex items-center gap-2 text-xs font-mono text-[#00E5FF] bg-cyan-950/40 border border-cyan-500/30 px-3 py-1.5 rounded-full shadow-sm">
          <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" /> 
          <span className="text-[10px] sm:text-xs font-bold tracking-wider">VERIFIED ACCREDITATION</span>
        </div>
      </header>

      {/* Relocated Navigation Element */}
      <div className="max-w-5xl mx-auto w-full mb-5">
        <Link 
          href="/" 
          className="inline-flex items-center gap-2 text-[11px] font-mono text-gray-400 hover:text-white transition-colors group"
        >
          <ArrowLeft className="w-3.5 h-3.5 text-[#00E5FF] group-hover:-translate-x-1 transition-transform" /> 
          RETURN TO HOME
        </Link>
      </div>

      {/* Order Confirmation Banner */}
      {isOrderSuccess && (
        <div className="max-w-5xl mx-auto w-full mb-5 bg-emerald-950/60 border border-emerald-500/50 rounded-2xl p-5 shadow-2xl backdrop-blur-md flex flex-col md:flex-row items-center justify-between gap-4 animate-in fade-in slide-in-from-top-4 duration-500">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 bg-emerald-500/20 border border-emerald-500/40 rounded-full flex items-center justify-center shrink-0">
              <CheckCircle2 className="w-5 h-5 text-emerald-400" />
            </div>
            <div>
              <h3 className="font-mono font-bold text-sm text-emerald-300">ACCREDITATION ORDER CONFIRMED</h3>
              <p className="text-xs text-gray-300 font-sans mt-0.5">
                Payment verified. Your official metric award for <span className="font-bold text-white">{post.author_handle}</span> is now queued for production and dispatch.
              </p>
            </div>
          </div>
          <span className="text-[10px] font-mono bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 px-3 py-1 rounded-full uppercase tracking-wider shrink-0">
            Status: In Production
          </span>
        </div>
      )}

      {/* Temporal Validity Info */}
      <div className="max-w-5xl mx-auto w-full mb-6 grid grid-cols-1 md:grid-cols-2 gap-4 font-mono text-xs">
        <div className="bg-gradient-to-r from-cyan-950/40 via-blue-950/20 to-cyan-950/40 border border-cyan-500/30 rounded-xl p-3.5 flex items-center gap-3 shadow-lg">
          <Calendar className="w-4 h-4 text-[#00E5FF] shrink-0" />
          <div>
            <span className="text-gray-400 block text-[10px] mb-0.5">POST VALIDITY WINDOW (15 DAYS)</span>
            <span className="text-white font-bold">{tokenWindow.start} - {tokenWindow.end}</span>
          </div>
        </div>

        <div className={`bg-gradient-to-r ${isExpired ? 'from-red-950/40 via-red-950/20 to-red-950/40 border-red-500/30 text-red-400' : 'from-amber-950/40 via-red-950/20 to-amber-950/40 border-amber-500/30 text-amber-300'} border rounded-xl p-3.5 flex items-center gap-3 shadow-lg`}>
          <Timer className={`w-4 h-4 ${isExpired ? 'text-red-400' : 'text-amber-400 animate-pulse'} shrink-0`} />
          <div>
            <span className="opacity-80 block text-[10px] mb-0.5">CLAIM TOKEN EXPIRES IN</span>
            <span className="font-bold">
              {isExpired ? 'EXPIRED' : `${timeLeft.days}d ${timeLeft.hours}h ${timeLeft.minutes}m ${timeLeft.seconds}s`}
            </span>
          </div>
        </div>
      </div>

      <div className="max-w-5xl mx-auto w-full grid grid-cols-1 lg:grid-cols-2 gap-6 items-stretch pb-10">
        
        {/* Left Column: Showcase Container */}
        <div className="h-full bg-[#070A10] border border-gray-800 rounded-2xl p-5 md:p-6 flex flex-col justify-between items-center text-center shadow-2xl relative overflow-hidden">
          <div className="absolute -right-12 -top-12 w-40 h-40 bg-[#00E5FF]/10 rounded-full blur-3xl pointer-events-none" />

          {/* Tab Selector */}
          <div className="flex items-center gap-1.5 p-1 bg-black/60 border border-gray-800 rounded-xl mb-6 w-full max-w-[320px]">
            <button
              onClick={() => { setActiveTab('plaque'); setArtifactLoading(true); }}
              className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 px-3 rounded-lg text-xs font-mono transition-all ${
                activeTab === 'plaque' 
                  ? 'bg-[#00E5FF]/10 text-[#00E5FF] border border-[#00E5FF]/40 font-bold shadow-sm' 
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              <Award className="w-3.5 h-3.5" /> Digital Plaque
            </button>
            <button
              onClick={() => { setActiveTab('mug'); setArtifactLoading(true); }}
              className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 px-3 rounded-lg text-xs font-mono transition-all ${
                activeTab === 'mug' 
                  ? 'bg-[#00E5FF]/10 text-[#00E5FF] border border-[#00E5FF]/40 font-bold shadow-sm' 
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              <CupSoda className="w-3.5 h-3.5" /> Physical Artifact
            </button>
          </div>

          <div className="w-full flex flex-col items-center flex-grow justify-center mb-6">
            
            {/* Aspect Square Artifact Preview Box */}
            <div className="w-full max-w-[450px] mx-auto aspect-square max-h-[450px] rounded-2xl bg-[#070A10] border border-[#00E5FF]/30 flex items-center justify-center mb-6 overflow-hidden relative group shadow-xl shadow-cyan-950/50">
              {artifactLoading && (
                <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/80 z-10 font-mono text-[10px] text-[#00E5FF] gap-2">
                  <Loader2 className="w-6 h-6 animate-spin text-[#00E5FF]" />
                  <span>RENDERING PREVIEW...</span>
                </div>
              )}
              <img 
                src={currentPreviewUrl}
                alt={activeTab === 'plaque' ? "Official Accreditation Badge" : "IOSA Physical Artifact Sample"}
                onLoad={() => setArtifactLoading(false)}
                onError={(e) => {
                  setArtifactLoading(false);
                  (e.target as HTMLElement).style.display = 'none';
                }}
                className={`object-contain w-full h-full transform group-hover:scale-105 transition-transform duration-300 ${artifactLoading ? 'opacity-0' : 'opacity-100'}`}
              />
            </div>

            <span className="text-xs font-mono px-3 py-1 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/30 font-bold uppercase mb-3">
              {post.vpi_level_name}
            </span>

            <h2 className="text-4xl sm:text-5xl font-black font-mono tracking-tight text-white mb-2">
              +{formattedVpi}x <span className="text-[#00E5FF]">VPI</span>
            </h2>
            <p className="text-xs font-mono text-gray-400">Viral Performance Index Accredited</p>
          </div>

          {/* Accredited Post Details */}
          <div className="w-full mt-auto border-t border-gray-800/80 pt-5 text-left space-y-3 font-mono text-xs text-gray-300 bg-black/40 p-4 rounded-xl border border-gray-800/60">
            <div className="flex flex-col gap-1.5 pb-2.5 border-b border-gray-800/60">
              <span className="text-[10px] text-gray-500 uppercase tracking-wider">ACCREDITED POST TITLE:</span>
              <span className="font-bold text-white text-xs leading-snug">{postTitle}</span>
            </div>

            <div className="flex justify-between items-center">
              <span className="text-gray-500 text-[11px]">CREATOR:</span>
              <span className="font-bold text-white">{post.author_handle}</span>
            </div>

            <div className="flex justify-between items-center">
              <span className="text-gray-500 text-[11px]">PUBLISHED DATE:</span>
              <span className="text-gray-300 font-medium">
                {post.created_at ? new Date(post.created_at).toLocaleDateString('en-US', { day: '2-digit', month: 'short', year: 'numeric' }) : 'N/A'}
              </span>
            </div>

            <div className="flex justify-between items-center">
              <span className="text-gray-500 text-[11px]">PLATFORM:</span>
              <span className="uppercase text-cyan-400 font-bold">{post.platform || 'YOUTUBE'}</span>
            </div>

            <div className="flex justify-between items-center">
              <span className="text-gray-500 text-[11px]">BASELINE (E_base):</span>
              <span>{post.baseline_score}</span>
            </div>

            <div className="flex justify-between items-center">
              <span className="text-gray-500 text-[11px]">ACTUAL VIEWS (E_act):</span>
              <span className="text-[#00E5FF] font-bold">{post.engagement_score}</span>
            </div>
          </div>
        </div>

        {/* Right Column: Claim Form */}
        <div className="h-full bg-[#070A10]/80 border border-gray-800 rounded-2xl p-6 shadow-2xl flex flex-col justify-between">
          <div>
            <h1 className="text-2xl font-extrabold mb-3 font-mono">Claim Physical Award</h1>
            <p className="text-xs text-gray-400 leading-relaxed mb-6">
              Congratulations <span className="text-white font-semibold">{post.author_handle}</span>! Your post was indexed with a performance spike of <span className="text-[#00E5FF] font-bold">+{formattedVpi}x</span> over baseline. Claim your custom ceramic mug trophy directly from OSA.
            </p>

            <div className="bg-black/60 border border-gray-800 rounded-xl p-4 mb-6 text-xs font-mono space-y-2.5">
              <div className="flex items-center gap-2 text-[#00E5FF] font-bold">
                <Sparkles className="w-4 h-4 shrink-0 text-cyan-400" />
                <span>Instant High-Res Customization</span>
              </div>
              <p className="text-gray-400 font-sans text-[11px] leading-relaxed">
                Your award mug has been rendered dynamically with your handle and accredited score. Proceed to checkout to verify your shipping details and order your physical trophy.
              </p>
            </div>

            {isExpired ? (
              <div className="bg-red-950/40 border border-red-500/50 rounded-xl p-5 text-center text-xs font-mono text-red-400 shadow-inner">
                This claim token has expired. The 15-day validity window from publication has closed.
              </div>
            ) : (
              <ClaimForm claimToken={token} postData={trophyPayload} />
            )}
          </div>

          <p className="text-[10px] text-gray-500 font-mono text-center mt-6 pt-4 border-t border-gray-800/60 flex items-center justify-center gap-1.5">
            <CheckCircle2 className="w-3 h-3 text-cyan-400" /> Powered by OSA Open Data Standard
          </p>
        </div>
      </div>
    </main>
  );
}