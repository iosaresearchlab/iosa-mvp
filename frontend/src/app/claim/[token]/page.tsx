'use client';

import { use, useState, useEffect } from 'react';
import { createClient } from '@supabase/supabase-js';
import { ShieldCheck, CheckCircle2, Timer, Calendar, Loader2, Sparkles, ExternalLink, CheckCircle } from 'lucide-react';
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
  const [trophyLoading, setTrophyLoading] = useState(true);
  const [productInitializing, setProductInitializing] = useState(true);
  const [productReady, setProductReady] = useState(false);
  const [printifyProductId, setPrintifyProductId] = useState<string>('');

  const [tokenWindow, setTokenWindow] = useState({ start: '', end: '' });
  const [timeLeft, setTimeLeft] = useState({ days: 14, hours: 23, minutes: 59, seconds: 59 });
  const [isExpired, setIsExpired] = useState(false);
  const [isOrderSuccess, setIsOrderSuccess] = useState(false);

  // Rileva lo stato di successo dal re-indirizzamento di Stripe (?status=success)
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const urlParams = new URLSearchParams(window.location.search);
      if (urlParams.get('status') === 'success') {
        setIsOrderSuccess(true);
      }
    }
  }, []);

  useEffect(() => {
    async function fetchPostAndInitialize() {
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

        if (currentPost) {
          setPost(currentPost);

          try {
            setProductInitializing(true);
            const res = await fetch(`${BACKEND_URL}/api/claim/initialize/${token}`, {
              method: 'POST',
            });
            if (res.ok) {
              const initData = await res.json();
              if (initData && initData.printify_product_id) {
                setPrintifyProductId(initData.printify_product_id);
              }
              setProductReady(true);
            }
          } catch (err) {
            console.error("Errore di inizializzazione prodotto Printify:", err);
          } finally {
            setProductInitializing(false);
          }

        } else {
          setPost(null);
        }
      } catch {
        if (MOCK_POSTS[token]) {
          setPost(MOCK_POSTS[token]);
          setProductReady(true);
        } else {
          setPost(null);
        }
      } finally {
        setLoading(false);
        setProductInitializing(false);
      }
    }

    if (token) {
      fetchPostAndInitialize();
    }
  }, [token]);

  useEffect(() => {
    if (!post || !post.created_at) return;

    const createdAt = new Date(post.created_at);
    const expiresAt = new Date(createdAt.getTime() + 15 * 24 * 60 * 60 * 1000);

    setTokenWindow({
      start: createdAt.toLocaleDateString('it-IT', { day: 'numeric', month: 'short', year: 'numeric' }),
      end: expiresAt.toLocaleDateString('it-IT', { day: 'numeric', month: 'short', year: 'numeric' }),
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
        <div className="max-w-md w-full bg-[#070A10] border border-red-500/30 rounded-xl p-8 text-center shadow-2xl">
          <h1 className="text-xl font-bold text-red-400 mb-2">404 — INVALID TOKEN</h1>
          <p className="text-xs text-gray-400">
            This verification link does not exist or has expired from the active evaluation window.
          </p>
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

  const previewImageUrl = `${BACKEND_URL}/api/trophy/preview?author=${encodeURIComponent(trophyPayload.author)}&vpi=${encodeURIComponent(trophyPayload.vpi_ratio)}`;
  
  const activeProductId = printifyProductId || '6a8789cfa16053a90f092c49';
  const mockupUrl = `https://images.printify.com/mockup/${activeProductId}/33719/6400/iosa-official-trophy-at-${post.author_handle?.replace('@', '').toLowerCase()}.jpg?camera_label=front&s=640&use_cdn_redirect=true`;

  return (
    <main className="min-h-screen bg-[#030508] text-white font-sans p-6 md:p-12 relative overflow-hidden">
      <header className="max-w-5xl mx-auto border-b border-gray-800/80 pb-6 mb-8 flex justify-between items-center">
        <div className="flex flex-col gap-1">
          <div className="flex items-end gap-1.5">
            <svg className="h-8 w-5 text-[#00E5FF]" viewBox="0 0 18.5 32" fill="none">
              <path d="M1 26.5H6.5L14 8.5L17.5 14" stroke="currentColor" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round"/>
              <circle cx="14" cy="3" r="3" fill="#00E5FF"/>
            </svg>
            <span className="font-mono font-black text-2xl tracking-tighter text-white leading-none">OSA</span>
          </div>
          <span className="text-[10px] font-mono text-gray-400 tracking-widest uppercase opacity-90">
            Institute for Open Social Analytics
          </span>
        </div>
        <div className="flex items-center gap-2 text-xs font-mono text-[#00E5FF] bg-cyan-950/40 border border-cyan-500/30 px-3 py-1 rounded-full">
          <ShieldCheck className="w-4 h-4 text-[#00E5FF]" /> VERIFIED ACCREDITATION
        </div>
      </header>

      {/* Banner di Successo Ordine */}
      {isOrderSuccess && (
        <div className="max-w-5xl mx-auto mb-8 bg-emerald-950/60 border border-emerald-500/50 rounded-2xl p-6 shadow-2xl backdrop-blur-md flex flex-col md:flex-row items-center justify-between gap-4 animate-in fade-in slide-in-from-top-4 duration-500">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-emerald-500/20 border border-emerald-500/40 rounded-full flex items-center justify-center shrink-0">
              <CheckCircle className="w-6 h-6 text-emerald-400" />
            </div>
            <div>
              <h3 className="font-mono font-bold text-base text-emerald-300">ACCREDITATION ORDER CONFIRMED</h3>
              <p className="text-xs text-gray-300 font-sans mt-0.5">
                Payment verified. Your official metric award for <span className="font-bold text-white">{post.author_handle}</span> is now queued for production and dispatch.
              </p>
            </div>
          </div>
          <span className="text-[10px] font-mono bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 px-3 py-1.5 rounded-full uppercase tracking-wider shrink-0">
            Status: In Production
          </span>
        </div>
      )}

      <div className="max-w-5xl mx-auto mb-8 grid grid-cols-1 md:grid-cols-2 gap-4 font-mono text-xs">
        <div className="bg-gradient-to-r from-cyan-950/40 via-blue-950/20 to-cyan-950/40 border border-cyan-500/30 rounded-xl p-3.5 flex items-center gap-3 shadow-lg">
          <Calendar className="w-4 h-4 text-[#00E5FF] shrink-0" />
          <div>
            <span className="text-gray-400 block text-[10px]">POST VALIDITY WINDOW (15 DAYS)</span>
            <span className="text-white font-bold">{tokenWindow.start} - {tokenWindow.end}</span>
          </div>
        </div>

        <div className={`bg-gradient-to-r ${isExpired ? 'from-red-950/40 via-red-950/20 to-red-950/40 border-red-500/30 text-red-400' : 'from-amber-950/40 via-red-950/20 to-amber-950/40 border-amber-500/30 text-amber-300'} border rounded-xl p-3.5 flex items-center gap-3 shadow-lg`}>
          <Timer className={`w-4 h-4 ${isExpired ? 'text-red-400' : 'text-amber-400 animate-pulse'} shrink-0`} />
          <div>
            <span className="opacity-80 block text-[10px]">CLAIM TOKEN EXPIRES IN</span>
            <span className="font-bold">
              {isExpired ? 'EXPIRED' : `${timeLeft.days}d ${timeLeft.hours}h ${timeLeft.minutes}m ${timeLeft.seconds}s`}
            </span>
          </div>
        </div>
      </div>

      <div className="max-w-5xl mx-auto grid grid-cols-1 md:grid-cols-2 gap-8 items-start">
        {/* Left Column: Trophy Preview & Compact Full Info */}
        <div className="bg-[#070A10] border border-gray-800 rounded-2xl p-6 md:p-8 flex flex-col items-center text-center shadow-2xl relative overflow-hidden">
          <div className="absolute -right-12 -top-12 w-40 h-40 bg-[#00E5FF]/10 rounded-full blur-3xl pointer-events-none" />

          <div className="w-full flex flex-col items-center">
            <div 
              className="w-full max-w-[320px] aspect-[27/11] rounded-2xl bg-black border border-[#00E5FF]/30 flex items-center justify-center mb-5 overflow-hidden relative group shadow-xl shadow-cyan-950/50 cursor-pointer"
              onClick={() => window.open(previewImageUrl, '_blank')}
              title="Click to open image in a new tab"
            >
              {trophyLoading && (
                <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/80 z-10 font-mono text-[10px] text-[#00E5FF] gap-2">
                  <Loader2 className="w-6 h-6 animate-spin text-[#00E5FF]" />
                  <span>RETRIEVING ARTIFACT...</span>
                </div>
              )}
              <img 
                src={previewImageUrl}
                alt="IOSA Official Trophy Preview"
                onLoad={() => setTrophyLoading(false)}
                onError={(e) => {
                  setTrophyLoading(false);
                  (e.target as HTMLElement).style.display = 'none';
                }}
                className={`object-cover w-full h-full transform group-hover:scale-105 transition-transform duration-300 ${trophyLoading ? 'opacity-0' : 'opacity-100'}`}
              />
              <div className="absolute bottom-2 right-2 bg-black/70 backdrop-blur-sm px-2 py-1 rounded text-[9px] font-mono text-[#00E5FF] opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1">
                <span>Open Full Image</span> <ExternalLink className="w-3 h-3" />
              </div>
            </div>

            <span className="text-xs font-mono px-3 py-1 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/30 font-bold uppercase mb-2">
              {post.vpi_level_name}
            </span>

            <h2 className="text-4xl font-black font-mono tracking-tight text-white mb-1">
              +{formattedVpi}x <span className="text-[#00E5FF]">VPI</span>
            </h2>
            <p className="text-xs font-mono text-gray-400 mb-6">Viral Performance Index Accredited</p>
          </div>

          {/* Block Information (Alzata senza spazio vuoto) */}
          <div className="w-full border-t border-gray-800/80 pt-5 text-left space-y-3 font-mono text-xs text-gray-300 bg-black/40 p-4 rounded-xl border border-gray-800/60">
            <div className="flex flex-col gap-1 pb-2 border-b border-gray-800/60">
              <span className="text-[10px] text-gray-500 uppercase tracking-wider">ACCREDITED POST TITLE:</span>
              <span className="font-bold text-white text-sm leading-snug">
                {postTitle}
              </span>
            </div>

            <div className="flex justify-between items-center">
              <span className="text-gray-500 text-[11px]">CREATOR:</span>
              <span className="font-bold text-white">{post.author_handle}</span>
            </div>

            <div className="flex justify-between items-center">
              <span className="text-gray-500 text-[11px]">PUBLISHED DATE:</span>
              <span className="text-gray-300 font-medium">
                {post.created_at ? new Date(post.created_at).toLocaleDateString('it-IT', { day: '2-digit', month: 'short', year: 'numeric' }) : 'N/A'}
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
        <div className="bg-[#070A10]/80 border border-gray-800 rounded-2xl p-8 shadow-2xl flex flex-col justify-between">
          <div>
            <h1 className="text-2xl font-extrabold mb-2 font-mono">Claim Official Award</h1>
            <p className="text-xs text-gray-400 leading-relaxed mb-6">
              Congratulations <span className="text-white font-semibold">{post.author_handle}</span>! Your post was indexed with a performance spike of <span className="text-[#00E5FF] font-bold">+{formattedVpi}x</span> over baseline. Order your physical metric trophy directly from OSA.
            </p>

            <div className="bg-black/60 border border-gray-800 rounded-xl p-4 mb-6 text-xs font-mono space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-[#00E5FF] font-bold">
                  {productInitializing ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin shrink-0 text-[#00E5FF]" />
                      <span>Synchronizing Product & Mockup with Printify...</span>
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-4 h-4 shrink-0 text-cyan-400" />
                      <span>Product Ready for Secure Order & Production</span>
                    </>
                  )}
                </div>
              </div>

              <div className="flex items-center justify-between pt-1 border-t border-gray-800">
                <span className="text-gray-400 text-[11px]">Mug Product Catalog Reference</span>
                <a 
                  href={mockupUrl} 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 text-[11px] font-mono text-[#00E5FF] bg-cyan-950/60 hover:bg-cyan-900/80 border border-cyan-500/40 px-3 py-1.5 rounded-lg transition-colors"
                >
                  <ExternalLink className="w-3.5 h-3.5" /> View Printify Mockup
                </a>
              </div>

              <p className="text-gray-400 font-sans text-[11px] leading-relaxed">
                OSA operates on a rolling 15-day algorithmic evaluation cycle. Outlier metrics and tokens expire exactly 15 days after publication. When you proceed to checkout, your custom artifact is generated on-demand to guarantee absolute authenticity.
              </p>
            </div>

            {isExpired ? (
              <div className="bg-red-950/40 border border-red-500/50 rounded-xl p-4 text-center text-xs font-mono text-red-400">
                This claim token has expired. The 15-day validity window from publication has closed.
              </div>
            ) : (
              <ClaimForm claimToken={token} postData={trophyPayload} />
            )}
          </div>

          <p className="text-[10px] text-gray-500 font-mono text-center mt-6 flex items-center justify-center gap-1">
            <CheckCircle2 className="w-3 h-3 text-cyan-400" /> Powered by OSA Open Data Standard
          </p>
        </div>
      </div>
    </main>
  );
}