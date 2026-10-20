/**
 * FIX-1d (20/10/2026): the link preview of a record, 1200x630.
 *
 * A claim link sent in a DM, or any record link on X, Bluesky or Threads,
 * used to preview as the site logo. This card carries the record instead,
 * the breakout card's content: "Usually X views. This one: Y (as of D)", the
 * multiple in its level colour, the title, the handle and the IOSA mark.
 *
 * The figures are the ones the page shows (record-status.ts: the VPI of the
 * day while charting, the highest observed after it left, with its views).
 * The date is the day of our reading of those views, always (owner, 10/10):
 * whoever clicks through sees a different live count.
 *
 * Rendered by next/og (Satori + Resvg, on Vercel): no Chromium. Titles come
 * in 34 countries' scripts, so the glyphs a title needs are fetched from
 * Google Fonts for that text only (Latin, Greek and Cyrillic ship with the app).
 */
// Satori draws <img>, not next/image.
/* eslint-disable @next/next/no-img-element */
import { readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { ImageResponse } from 'next/og';
import { formatCountFull, formatVPI } from '@/lib/format';
import { inClassifica, livelloPubblicato, motivoSenzaVpi, viewsPubblicate, vpiPubblicato } from '@/lib/record-status';
import { supabaseServer } from '@/lib/supabase-server';

export const OG_SIZE = { width: 1200, height: 630 };
export const OG_CONTENT_TYPE = 'image/png';
// Static per record version, no ISR write (the Hobby ISR-writes limit paused
// the site on 17/10, OPS-1): the route is dynamic and the CDN and browsers
// keep the image a day.
export const OG_HEADERS = { 'Cache-Control': 'public, max-age=86400, immutable' };

export type OgRecord = {
  id?: string | null;
  method_version?: string | null;
  status?: string | null;
  author_handle?: string | null;
  content_text?: string | null;
  engagement_score?: number | string | null;
  baseline_score?: number | string | null;
  baseline_rule?: string | null;
  vpi_ratio?: number | string | null;
  vpi_max?: number | string | null;
  vpi_max_on?: string | null;
  views_max?: number | string | null;
  day_n?: number | null;
  days_charting?: number | null;
  entered_on?: string | null;
  left_on?: string | null;
  detected_at?: string | null;
};

const CAMPI =
  'id,method_version,status,author_handle,content_text,engagement_score,baseline_score,baseline_rule,vpi_ratio,vpi_max,vpi_max_on,views_max,day_n,days_charting,entered_on,left_on,detected_at';

/** The record of a claim token: the same two reads as the claim page. */
export async function recordDelToken(token: string): Promise<OgRecord | null> {
  // A failed read throws: the route answers 500, which no cache keeps; the
  // site card is for a token that resolves to nothing.
  const { data, error } = await supabaseServer.from('public_records').select(CAMPI).eq('claim_token', token).maybeSingle();
  if (error) throw new Error(`public_records: ${error.message}`);
  if (data) return data as OgRecord;
  const archived = await supabaseServer.rpc('claim_record_v1', { p_token: token }).maybeSingle();
  if (archived.error) throw new Error(`claim_record_v1: ${archived.error.message}`);
  return (archived.data as OgRecord) ?? null;
}

/**
 * The day of the reading the shown views come from. After the exit the views
 * are those of the peak, read on vpi_max_on. While charting, the latest
 * daily reading. A v1 archive record: the day it was measured.
 */
export async function giornoDellaLettura(r: OgRecord): Promise<string | null> {
  if (r.method_version !== 'v2') return r.detected_at ? String(r.detected_at).slice(0, 10) : null;
  if (!inClassifica(r)) return r.vpi_max_on ? String(r.vpi_max_on).slice(0, 10) : null;
  if (!r.id) return null;
  const { data, error } = await supabaseServer
    .from('post_daily')
    .select('day')
    .eq('post_id', r.id)
    .order('day', { ascending: false })
    .limit(1)
    .maybeSingle();
  if (error) throw new Error(`post_daily: ${error.message}`);
  return (data as { day?: string } | null)?.day ?? null;
}

/** "9 Oct", as in the social texts. */
function giornoBreve(iso: string | null): string | null {
  if (!iso) return null;
  const d = new Date(`${iso.slice(0, 10)}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return null;
  const mesi = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  return `${d.getUTCDate()} ${mesi[d.getUTCMonth()]}`;
}

// Latin, Greek, Cyrillic and Vietnamese: Noto Sans, subset to those scripts
// and shipped with the app (src/assets/og, OFL), read once per instance.
// Other scripts: the Google Fonts family, for the title's text only, in the
// order Satori falls back through them. A cold instance pays no font
// download for four titles in five (FIX-1d, 20/10: 21% of the v2 titles
// carry a character outside Latin, symbols and emoji).
const FAMIGLIE: ReadonlyArray<readonly [RegExp, string]> = [
  [/[\u3040-\u30ff\u3400-\u9fff\uf900-\ufaff\uff00-\uffef]/, 'Noto Sans JP'],
  [/[\uac00-\ud7af\u1100-\u11ff\u3130-\u318f]/, 'Noto Sans KR'],
  [/[\u0e00-\u0e7f]/, 'Noto Sans Thai'],
  [/[\u0900-\u097f]/, 'Noto Sans Devanagari'],
  [/[\u0980-\u09ff]/, 'Noto Sans Bengali'],
  [/[\u0b80-\u0bff]/, 'Noto Sans Tamil'],
  [/[\u0c00-\u0c7f]/, 'Noto Sans Telugu'],
  [/[\u0c80-\u0cff]/, 'Noto Sans Kannada'],
  [/[\u0d00-\u0d7f]/, 'Noto Sans Malayalam'],
  [/[\u0a80-\u0aff]/, 'Noto Sans Gujarati'],
  [/[\u0a00-\u0a7f]/, 'Noto Sans Gurmukhi'],
  [/[\u0600-\u06ff\u0750-\u077f]/, 'Noto Sans Arabic'],
  [/[\u1780-\u17ff]/, 'Noto Sans Khmer'],
  [/[\u0590-\u05ff]/, 'Noto Sans Hebrew'],
];

type Font = { name: string; data: ArrayBuffer | Buffer; weight: 400 | 700; style: 'normal' };

const ASSETS = join(process.cwd(), 'src/assets/og');
const NOTO_LOCALE: Promise<Font[]> = Promise.all([
  readFile(join(ASSETS, 'NotoSans-Regular-subset.ttf')),
  readFile(join(ASSETS, 'NotoSans-Bold-subset.ttf')),
]).then(([r, b]) => [
  { name: 'Noto Sans', data: r, weight: 400, style: 'normal' },
  { name: 'Noto Sans', data: b, weight: 700, style: 'normal' },
]);

async function fontGoogle(famiglia: string, testo: string): Promise<Font[]> {
  const url = `https://fonts.googleapis.com/css2?family=${encodeURIComponent(famiglia)}:wght@400;700&text=${encodeURIComponent(testo)}`;
  const risposta = await fetch(url);
  if (!risposta.ok) throw new Error(`Google Fonts ${famiglia}: ${risposta.status}`);
  const css = await risposta.text();
  const blocchi = css.match(/@font-face\s*{[^}]*}/g) || [];
  return Promise.all(
    blocchi.flatMap((b) => {
      const src = /src:\s*url\(([^)]+)\)\s*format\('(?:opentype|truetype)'\)/.exec(b);
      const peso = /font-weight:\s*(\d+)/.exec(b);
      if (!src) return [];
      return [
        fetch(src[1]).then(async (r) => {
          if (!r.ok) throw new Error(`Google Fonts file ${famiglia}: ${r.status}`);
          return r;
        }).then(async (r) => ({
          name: famiglia,
          data: await r.arrayBuffer(),
          weight: (peso && Number(peso[1]) >= 600 ? 700 : 400) as 400 | 700,
          style: 'normal' as const,
        })),
      ];
    })
  );
}

/** The fonts for this text: Noto Sans always, then only the scripts it uses. */
async function fontPer(testo: string): Promise<Font[]> {
  const altre = FAMIGLIE.filter(([re]) => re.test(testo)).map(([, f]) => f);
  const caratteri = Array.from(new Set(Array.from(testo))).join('');
  const lotti = await Promise.all([
    NOTO_LOCALE,
    ...altre.map((f) => fontGoogle(f, caratteri)), // a failed font is a 500, not a card of empty boxes kept a day
  ]);
  return lotti.flat();
}

const LOGO: Promise<string> = readFile(join(process.cwd(), 'public/brand/iosa-logo@2x.png'), 'base64').then(
  (b) => `data:image/png;base64,${b}`
);

function tronca(s: string, n: number): string {
  const c = Array.from(s);
  return c.length > n ? `${c.slice(0, n - 1).join('').trimEnd()}…` : s;
}

/** The texts of the card, from the record. Exported for the test. */
export function testiDellaCard(r: OgRecord, giorno: string | null) {
  const vpi = vpiPubblicato(r);
  const senzaVpi = vpi === null || vpi === undefined;
  const livello = livelloPubblicato(r);
  const views = formatCountFull(viewsPubblicate(r) ?? r.engagement_score);
  const quando = giornoBreve(giorno);
  const questo = `This one: ${views}${quando ? ` (as of ${quando})` : ''}`;
  const usuale = r.baseline_score !== null && r.baseline_score !== undefined && !senzaVpi
    ? `Usually ${formatCountFull(r.baseline_score)} views.`
    : null;
  const charting = r.method_version === 'v2' && inClassifica(r);
  const n = r.day_n ?? r.days_charting ?? null;
  const stato = r.method_version !== 'v2'
    ? 'Archive record'
    : charting
      ? `In Most Popular${n ? ` · day ${n}` : ''} · VPI of the day`
      : `Left Most Popular${n ? ` · ${n} day${n === 1 ? '' : 's'}` : ''} · highest VPI observed`;
  return {
    usuale,
    questo: usuale ? questo : `${views} views${quando ? ` (as of ${quando})` : ''}`,
    multiplo: senzaVpi ? null : formatVPI(vpi),
    livello: senzaVpi ? (motivoSenzaVpi(r) ?? livello.nome) : livello.nome,
    colore: livello.colore,
    titolo: tronca(r.content_text || 'Measured video', 110),
    handle: r.author_handle || '',
    stato,
  };
}

/** The card. `r` null: the site card (a link to nothing still previews). */
export async function cardDelRecord(r: OgRecord | null): Promise<ImageResponse> {
  const marchio = await LOGO;
  if (!r) {
    const fonts = await fontPer('IOSA How far a YouTube video beat its own channel usual views');
    return new ImageResponse(
      (
        <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'center', padding: 72, background: '#030508', color: '#fff', fontFamily: 'Noto Sans' }}>
          <img src={marchio} width={142} height={96} alt="" />
          <div style={{ fontSize: 52, fontWeight: 700, marginTop: 40, lineHeight: 1.2 }}>How far a YouTube video beat its own channel&apos;s usual views</div>
        </div>
      ),
      { ...OG_SIZE, fonts, headers: OG_HEADERS }
    );
  }
  const t = testiDellaCard(r, await giornoDellaLettura(r));
  const fonts = await fontPer([t.usuale, t.questo, t.multiplo, t.livello, t.titolo, t.handle, t.stato, 'iosaresearch.org'].join(' '));
  return new ImageResponse(
    (
      <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', background: '#030508', color: '#fff', fontFamily: 'Noto Sans', padding: '56px 64px', borderTop: `12px solid ${t.colore}` }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', fontSize: 24, color: '#9ca3af', letterSpacing: 1 }}>{t.stato}</div>
          <img src={marchio} width={106} height={72} alt="" />
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', marginTop: 20, flexShrink: 0 }}>
          {t.usuale ? <div style={{ display: 'flex', fontSize: 44, color: '#d1d5db' }}>{t.usuale}</div> : null}
          <div style={{ display: 'flex', fontSize: 52, fontWeight: 700, marginTop: 6 }}>{t.questo}</div>
        </div>
        <div style={{ display: 'flex', alignItems: 'baseline', marginTop: 18, flexShrink: 0 }}>
          {t.multiplo ? (
            <div style={{ display: 'flex', fontSize: 104, fontWeight: 700, color: t.colore, lineHeight: 1 }}>{t.multiplo}</div>
          ) : null}
          <div style={{ display: 'flex', fontSize: 30, color: t.colore, marginLeft: t.multiplo ? 28 : 0 }}>{t.livello}</div>
        </div>
        <div style={{ display: 'flex', flexGrow: 1 }} />
        <div style={{ display: 'flex', fontSize: 34, lineHeight: 1.25, maxHeight: 86, overflow: 'hidden', marginTop: 16, flexShrink: 0 }}>{t.titolo}</div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 14, fontSize: 26, color: '#9ca3af', flexShrink: 0 }}>
          <div style={{ display: 'flex' }}>{t.handle}</div>
          <div style={{ display: 'flex', color: '#00E5FF' }}>iosaresearch.org</div>
        </div>
      </div>
    ),
    { ...OG_SIZE, fonts, headers: OG_HEADERS }
  );
}
