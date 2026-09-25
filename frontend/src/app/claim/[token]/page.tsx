'use client';

import { use, useState, useEffect, useCallback } from 'react';
import { livelloDaRatio, NESSUN_LIVELLO, stileBadge } from '@/lib/vpi-scale';
import Link from 'next/link';
import { formatVPI, formatCount, formatVPIFull, formatCountFull } from '@/lib/format';
import { WaitlistForm } from '@/components/WaitlistForm';
import { createClient } from '@supabase/supabase-js';
import { ShieldCheck, CheckCircle2, Timer, Calendar, Loader2, Sparkles, ArrowLeft, CupSoda, Award, Download, Heart } from 'lucide-react';
import ClaimForm from './ClaimForm';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
// Deve corrispondere a ENABLE_ORDERS nel backend. Default acceso.
const ORDERS_ENABLED = process.env.NEXT_PUBLIC_ENABLE_ORDERS === 'true';
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || '';
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || '';
const supabase = createClient(supabaseUrl, supabaseAnonKey);



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

  const [tokenWindow, setTokenWindow] = useState({ start: '', end: '', days: 0 });
  const [timeLeft, setTimeLeft] = useState<{ days: number; hours: number; minutes: number; seconds: number } | null>(null);
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
          .maybeSingle();

        // I record v1 sono usciti da posts il 25/09/2026 (docs/02 §3.6): un
        // token gia' inviato si risolve nell'archivio, solo per token.
        let record = data;
        if (!record) {
          const archived = await supabase
            .rpc('claim_record_v1', { p_token: token })
            .maybeSingle();
          record = archived.data;
        }

        setPost(record || null);
      } catch {
        setPost(null);
      } finally {
        setLoading(false);
      }
    }

    if (token) {
      fetchPost();
    }
  }, [token]);

  // Chi sta guardando non e' sempre una persona: Googlebot & c. eseguono il
  // JavaScript della pagina esattamente come un browser, quindi facevano
  // scattare il conteggio. Non li escludiamo, li marchiamo: sapere quanto i
  // motori ci passano sopra e' un'informazione, ma non e' interesse di un
  // creator per la sua misurazione.
  const passaggioAutomatico = useCallback(() => {
    try {
      if ((navigator as Navigator & { webdriver?: boolean }).webdriver) return true;
      return /bot|crawl|spider|slurp|mediapartners|bingpreview|headless|facebookexternalhit|embedly|preview/i
        .test(navigator.userAgent || '');
    } catch {
      return false;
    }
  }, []);

  // Registra il passaggio sulla pagina.
  //
  // Serve a sapere se i creator che contattiamo aprono davvero la loro
  // misurazione: finora si poteva solo contare chi rispondeva, che e' il
  // segnale piu' debole e piu' raro. Si scrive dal browser con la chiave
  // anon, non dal backend, perche' il backend va in sospensione e una visita
  // non deve dipendere dal fatto che sia sveglio.
  //
  // Niente IP, niente user agent per esteso: solo il dominio di provenienza e
  // se lo schermo e' stretto. Basta a capire da quale canale arrivano.
  useEffect(() => {
    if (!token || !post?.id) return;

    // Una sola registrazione per sessione del browser: ricaricare la pagina
    // o cambiare scheda non deve gonfiare il conteggio.
    const chiave = `iosa_visita_${token}`;
    try {
      if (sessionStorage.getItem(chiave)) return;
      sessionStorage.setItem(chiave, '1');
    } catch {
      // Storage negato (navigazione privata, cookie bloccati): si registra
      // comunque, meglio un conteggio un po' alto che nessun dato.
    }

    let provenienza: string | null = null;
    try {
      provenienza = document.referrer ? new URL(document.referrer).hostname : null;
    } catch {
      provenienza = null;
    }

    supabase
      .from('claim_visite')
      .insert({
        claim_token: token,
        post_id: post.id,
        provenienza,
        schermo: window.innerWidth < 768 ? 'mobile' : 'desktop',
        automatico: passaggioAutomatico(),
      })
      .then(() => {}, () => {});   // una visita non registrata non rompe la pagina
  }, [token, post?.id, passaggioAutomatico]);

  // Registra un gesto compiuto sulla pagina (per ora: lo scarico della targa).
  //
  // Vercel sul piano gratuito non offre eventi personalizzati, quindi se li
  // vogliamo dobbiamo registrarli noi. Stessa prudenza delle visite: si
  // scrive dal browser con la chiave pubblica, senza IP e senza user agent,
  // e un errore non deve mai bloccare il gesto dell'utente.
  const registraAzione = useCallback((azione: string) => {
    if (!token) return;

    // Un conteggio per sessione del browser: chi clicca due volte sullo
    // stesso pulsante ha comunque compiuto il gesto una volta sola.
    const chiave = `iosa_${azione}_${token}`;
    try {
      if (sessionStorage.getItem(chiave)) return;
      sessionStorage.setItem(chiave, '1');
    } catch {
      // Storage negato: si registra comunque.
    }

    let provenienza: string | null = null;
    try {
      provenienza = document.referrer ? new URL(document.referrer).hostname : null;
    } catch {
      provenienza = null;
    }

    supabase
      .from('claim_eventi')
      .insert({
        claim_token: token,
        post_id: post?.id ?? null,
        azione,
        provenienza,
        schermo: window.innerWidth < 768 ? 'mobile' : 'desktop',
        automatico: passaggioAutomatico(),
      })
      .then(() => {}, () => {});
  }, [token, post?.id, passaggioAutomatico]);

  useEffect(() => {
    // La finestra del claim e' calcolata dal backend (docs/02 §6.4):
    // entered_on + CLAIM_DAYS, dal primo giorno osservato. La misurazione non
    // scade; scade solo il token. Qui si disegna solo il conto alla rovescia.
    if (!post || !token) return;
    let timer: ReturnType<typeof setInterval> | undefined;
    let annullato = false;
    fetch(`${BACKEND_URL}/api/claim/${encodeURIComponent(token)}/window`)
      .then((r) => (r.ok ? r.json() : null))
      .then((w) => {
        if (annullato || !w || !w.expires_on) return;
        const inizio = new Date(`${w.start}T00:00:00Z`);
        const fine = new Date(`${w.expires_on}T00:00:00Z`);
        const fmt = (d: Date) => d.toLocaleDateString('en-US', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });
        setTokenWindow({ start: fmt(inizio), end: fmt(fine), days: w.claim_days });
        setIsExpired(Boolean(w.expired));
        const aggiorna = () => {
          const diff = fine.getTime() - Date.now();
          if (diff <= 0) {
            setIsExpired(true);
            setTimeLeft({ days: 0, hours: 0, minutes: 0, seconds: 0 });
            return;
          }
          setTimeLeft({
            days: Math.floor(diff / 86_400_000),
            hours: Math.floor((diff / 3_600_000) % 24),
            minutes: Math.floor((diff / 60_000) % 60),
            seconds: Math.floor((diff / 1000) % 60),
          });
        };
        aggiorna();
        timer = setInterval(aggiorna, 1000);
      })
      .catch(() => {});
    return () => {
      annullato = true;
      if (timer) clearInterval(timer);
    };
  }, [post, token]);

  if (loading) {
    return (
      <main className="min-h-screen bg-[#030508] text-white font-mono flex items-center justify-center p-6">
        <div className="text-xs text-[#00E5FF] animate-pulse font-mono tracking-widest flex items-center gap-2">
          <Loader2 className="w-4 h-4 animate-spin text-[#00E5FF]" /> RETRIEVING MEASUREMENT DATA...
        </div>
      </main>
    );
  }

  if (!post) {
    return (
      <main className="min-h-screen bg-[#030508] text-white font-mono flex items-center justify-center p-6">
        <div className="max-w-md w-full bg-[#070A10] border border-amber-500/30 rounded-xl p-8 text-center shadow-2xl flex flex-col items-center gap-4">
          <h1 className="text-xl font-bold text-amber-400">MEASUREMENT NOT FOUND</h1>
          <p className="text-xs text-gray-400 leading-relaxed">
            No record carries this link. Records are never deleted, so the link
            is probably mistyped: check it against the one you received, or
            search your channel on the index.
          </p>
          <div className="flex flex-col sm:flex-row gap-2 mt-2">
            <Link
              href="/outliers"
              className="inline-flex items-center justify-center gap-2 text-xs font-mono text-black bg-[#00E5FF] hover:bg-cyan-400 px-4 py-2 rounded-full transition-all"
            >
              Browse the index
            </Link>
            <Link
              href="/"
              className="inline-flex items-center justify-center gap-2 text-xs font-mono text-white bg-gray-900 hover:bg-gray-800 border border-gray-700 hover:border-[#00E5FF]/50 px-4 py-2 rounded-full transition-all"
            >
              <ArrowLeft className="w-3.5 h-3.5 text-[#00E5FF]" /> Search your channel
            </Link>
          </div>
        </div>
      </main>
    );
  }

  // Il valore pubblicato e' il VPI piu' alto osservato, sempre con le views e
  // i giorni in Most Popular (docs/01 §4.1). I record v1 non hanno vpi_max.
  const vpiPubblicato = post.vpi_max ?? post.vpi_ratio;
  const viewsPubblicate = post.views_max ?? post.engagement_score ?? post.e_act;
  const giorniInClassifica: number | null = post.days_charting ?? null;
  const livelloPubblicato = livelloDaRatio(vpiPubblicato) ?? NESSUN_LIVELLO;
  const formattedVpi = formatVPI(vpiPubblicato);
  const postTitle = post.content_text || post.title || post.content_title || 'Measured Video';

  const trophyPayload = {
    author: post.author_handle || 'Creator',
    vpi_ratio: formatVPIFull(Number(vpiPubblicato || 0)),
    level_name: livelloPubblicato.livello ? livelloPubblicato.nome : '',
    content_title: postTitle,
    date_str: post.created_at
      ? new Date(post.created_at).toISOString().split('T')[0]
      : '2026-08-20',
    e_act: formatCountFull(Number(viewsPubblicate)),
    e_base: formatCountFull(Number(post.baseline_score ?? post.e_base)),
  };

  const mugMockupUrl = `${BACKEND_URL}/api/trophy/preview-mug?author=${encodeURIComponent(trophyPayload.author)}&vpi=${encodeURIComponent(trophyPayload.vpi_ratio)}`;
  const plaquePreviewUrl = `${BACKEND_URL}/api/trophy/preview?claim_token=${encodeURIComponent(token)}&recorded_date=${encodeURIComponent(trophyPayload.date_str)}&author=${encodeURIComponent(trophyPayload.author)}&vpi=${encodeURIComponent(trophyPayload.vpi_ratio)}&e_act=${encodeURIComponent(trophyPayload.e_act)}&e_base=${encodeURIComponent(trophyPayload.e_base)}&content_title=${encodeURIComponent(trophyPayload.content_title)}&title=${encodeURIComponent(trophyPayload.content_title)}&level_name=${encodeURIComponent(trophyPayload.level_name)}`;

  const currentPreviewUrl = activeTab === 'plaque' ? plaquePreviewUrl : mugMockupUrl;

  const formattedDetectedDate = post.entered_on
    ? new Date(`${post.entered_on}T00:00:00Z`).toLocaleDateString('en-US', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC' })
    : post.detected_at 
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
          <span className="text-[9px] sm:text-[11px] font-bold tracking-wider">INDEPENDENT MEASUREMENT</span>
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
              <h3 className="font-mono font-bold text-xs text-emerald-300">ORDER CONFIRMED</h3>
              <p className="text-[11px] text-gray-300 font-sans mt-0.5">
                Payment verified. Your commemorative item for <span className="font-bold text-white">{post.author_handle}</span> is queued for production.
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
            <span className="text-gray-400 block text-[9px] mb-0.5">
              CLAIM WINDOW{tokenWindow.days ? ` (${tokenWindow.days} DAYS FROM FIRST OBSERVATION)` : ''}
            </span>
            <span className="text-white font-bold text-[11px]">
              {tokenWindow.start ? `${tokenWindow.start} - ${tokenWindow.end}` : '\u2014'}
            </span>
            <span className="text-gray-500 block text-[9px] mt-0.5">The measurement never expires; the claim token does.</span>
          </div>
        </div>

        <div className={`bg-gradient-to-r ${isExpired ? 'from-red-950/40 via-red-950/20 to-red-950/40 border-amber-500/30 text-red-400' : 'from-amber-950/40 via-red-950/20 to-amber-950/40 border-amber-500/30 text-amber-300'} border rounded-xl p-3 flex items-center gap-3 shadow-md`}>
          <Timer className={`w-3.5 h-3.5 ${isExpired ? 'text-red-400' : 'text-amber-400 animate-pulse'} shrink-0`} />
          <div>
            <span className="opacity-80 block text-[9px] mb-0.5">CLAIM TOKEN EXPIRES IN</span>
            <span className="font-bold text-[11px]">
              {isExpired
                ? 'EXPIRED'
                : timeLeft
                  ? `${timeLeft.days}d ${timeLeft.hours}h ${timeLeft.minutes}m ${timeLeft.seconds}s`
                  : '\u2014'}
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
                    onClick={() => registraAzione('download_targa')}
                    className="w-full py-2 px-3 bg-[#00E5FF] hover:bg-[#00B4D8] text-black font-mono font-bold text-xs rounded-lg shadow-xl flex items-center justify-center gap-2 transition-all backdrop-blur-md"
                  >
                    <Download className="w-3.5 h-3.5" /> Download Digital Plaque (.PNG)
                  </a>
                </div>
              )}
            </div>

            <p className="text-[10px] font-mono text-gray-400 mb-2 flex items-center justify-center gap-1">
              <CheckCircle2 className="w-3 h-3 text-cyan-400 shrink-0" /> Includes a QR code linking back to this measurement page.
            </p>

            <span
              className="text-[11px] font-mono px-2.5 py-0.5 rounded-full font-bold uppercase mb-1.5 border"
              style={stileBadge(livelloPubblicato.colore)}
            >
              {livelloPubblicato.nome}
            </span>

            <h2 className="text-3xl sm:text-4xl font-black font-mono tracking-tight text-white mb-1">
              {formattedVpi} <span className="text-[#00E5FF]">VPI</span>
            </h2>
            <p className="text-[11px] font-mono text-gray-400">Peak VPI observed in Most Popular &mdash; independent measurement</p>
            <div className="mt-2 grid grid-cols-3 gap-2 w-full font-mono text-[10px]" data-plaque-figures>
              <div className="bg-black/50 border border-gray-800 rounded-lg p-2">
                <span className="block text-gray-500">PEAK VPI</span>
                <span className="text-[#00E5FF] font-bold">{formattedVpi}</span>
              </div>
              <div className="bg-black/50 border border-gray-800 rounded-lg p-2">
                <span className="block text-gray-500">VIEWS</span>
                <span className="text-white font-bold">{formatCount(viewsPubblicate)}</span>
              </div>
              <div className="bg-black/50 border border-gray-800 rounded-lg p-2">
                <span className="block text-gray-500">DAYS IN MOST POPULAR</span>
                <span className="text-white font-bold">{giorniInClassifica ?? '\u2014'}</span>
              </div>
            </div>
          </div>

          {/* Post Metrics Details */}
          <div className="w-full mt-auto border-t border-gray-800/80 pt-3 text-left space-y-2 font-mono text-xs text-gray-300 bg-black/40 p-3 rounded-xl border border-gray-800/60">
            <div className="flex flex-col gap-1 pb-2 border-b border-gray-800/60">
              <span className="text-[9px] text-gray-500 uppercase tracking-wider">MEASURED POST TITLE:</span>
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
              <span className="text-[#00E5FF]">FIRST OBSERVED:</span>
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
              <span className="text-gray-500">VIEWS (E_act):</span>
              <span className="text-[#00E5FF] font-bold">{formatCount(viewsPubblicate)}</span>
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
                Digital plaques and reports are <span className="text-white font-semibold">100% free forever</span>. Ordering a physical item is entirely optional: the proceeds cover servers, API quota and development.
              </p>
            </div>

            {!ORDERS_ENABLED ? (
              <WaitlistForm
                claimToken={token}
                authorHandle={post.author_handle || undefined}
              />
            ) : isExpired ? (
              <div className="bg-red-950/40 border border-red-500/50 rounded-xl p-4 text-center text-xs font-mono text-red-400 shadow-inner">
                This claim token has expired: the {tokenWindow.days || ''}-day claim window from first observation has closed. The measurement stays published.
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
          <strong className="text-gray-400">PROJECT DISCLAIMER:</strong> IOSA (Institute for Open Social Analytics) is an independent, self-funded research project with no profit purpose. Commemorative items are optional and their proceeds cover servers, API quota and development. VPI is our own measurement, not a certification issued by any authority. Not affiliated with, endorsed by, sponsored by, or associated with YouTube, Google LLC, TikTok, or any other platform.
        </p>
      </footer>
    </main>
  );
}