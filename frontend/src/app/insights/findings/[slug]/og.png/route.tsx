// SOC-W1 (24/10/2026): the link preview of a Findings story, 1200x630: its title and its
// leading figure. Generated at build time for each published story, like the record
// cards (next/og, src/lib/og-card.tsx); a draft has no image.
/* eslint-disable @next/next/no-img-element */
import { ImageResponse } from 'next/og';
import { notFound } from 'next/navigation';
import { figuraPrincipale, formatValore, storia, storiePubblicate, dataLunga } from '@/lib/findings';
import { fontPer, marchioIosa, OG_SIZE } from '@/lib/og-card';

export const dynamicParams = false;

export function generateStaticParams() {
  return storiePubblicate().map((m) => ({ slug: m.slug }));
}

export async function GET(_req: Request, { params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const s = storia(slug);
  if (!s) notFound();
  const figura = figuraPrincipale(s.data);
  const valore = formatValore(figura.value, s.data.unit);
  const marchio = await marchioIosa();
  const fonts = await fontPer([s.meta.og_title, valore, figura.label, s.data.measure, dataLunga(s.data.reading_date), 'IOSA Findings iosaresearch.org'].join(' '));
  return new ImageResponse(
    (
      <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', background: '#030508', color: '#fff', fontFamily: 'Noto Sans', padding: '56px 64px', borderTop: '12px solid #00E5FF' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', fontSize: 24, color: '#67e8f9', letterSpacing: 2 }}>IOSA FINDINGS</div>
          <img src={marchio} width={106} height={72} alt="" />
        </div>
        <div style={{ display: 'flex', fontSize: 54, fontWeight: 700, lineHeight: 1.15, marginTop: 24, maxHeight: 190, overflow: 'hidden' }}>
          {s.meta.og_title}
        </div>
        <div style={{ display: 'flex', flexGrow: 1 }} />
        <div style={{ display: 'flex', alignItems: 'baseline' }}>
          <div style={{ display: 'flex', fontSize: 96, fontWeight: 700, color: '#00E5FF', lineHeight: 1 }}>{valore}</div>
          <div style={{ display: 'flex', fontSize: 30, color: '#d1d5db', marginLeft: 24, maxWidth: 640 }}>{figura.label}</div>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 18, fontSize: 24, color: '#9ca3af' }}>
          <div style={{ display: 'flex' }}>{`${s.data.measure} · reading of ${dataLunga(s.data.reading_date)}`}</div>
          <div style={{ display: 'flex', color: '#00E5FF' }}>iosaresearch.org</div>
        </div>
      </div>
    ),
    { ...OG_SIZE, fonts }
  );
}
