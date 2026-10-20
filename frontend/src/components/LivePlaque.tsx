'use client';

// FIX-1a (owner, 20/10/2026): the claim page shows the plaque at once, every
// time. The backend sends the plaque's HTML (/api/trophy/live, a few KB, no
// Chromium): the same page Chromium screenshots for the PNG, so what the
// visitor sees is the PNG by construction. It is shown in a sandboxed iframe
// (no script runs in it) scaled to the width available. "Download" serves the
// archived PNG when there is one, otherwise makes it here at full size.

import { useCallback, useEffect, useRef, useState } from 'react';
import { Download, Loader2 } from 'lucide-react';
import { toPng } from 'html-to-image';

export type LivePlaqueData = {
  html: string;
  width: number;
  height: number;
  file: string;
  png_url: string | null;
};

// The @font-face rules the plaque uses, with their files inlined, for
// html-to-image: it cannot read the Google Fonts stylesheet of the iframe
// (cross-origin), and without the fonts the PNG falls back to other ones.
// Only the faces whose unicode-range covers a character of the plaque.
async function plaqueFontCSS(doc: Document): Promise<string> {
  const cps = new Set<number>();
  for (const ch of doc.body.innerText || '') cps.add(ch.codePointAt(0) as number);
  const covers = (range: string) =>
    range.split(',').some((part) => {
      const m = part.trim().replace(/^U\+/i, '');
      let lo: number;
      let hi: number;
      if (m.includes('-')) {
        const [a, b] = m.split('-');
        lo = parseInt(a, 16);
        hi = parseInt(b, 16);
      } else if (m.includes('?')) {
        lo = parseInt(m.replace(/\?/g, '0'), 16);
        hi = parseInt(m.replace(/\?/g, 'F'), 16);
      } else {
        lo = hi = parseInt(m, 16);
      }
      for (const c of cps) if (c >= lo && c <= hi) return true;
      return false;
    });
  const toDataUrl = (blob: Blob) =>
    new Promise<string>((resolve) => {
      const fr = new FileReader();
      fr.onload = () => resolve(fr.result as string);
      fr.readAsDataURL(blob);
    });
  const out: string[] = [];
  const links = Array.from(doc.querySelectorAll<HTMLLinkElement>('link[rel="stylesheet"]'));
  for (const link of links) {
    const css = await (await fetch(link.href)).text();
    for (const block of css.match(/@font-face\s*{[^}]*}/g) || []) {
      const range = /unicode-range:\s*([^;]+);/.exec(block);
      if (range && !covers(range[1])) continue;
      const url = /url\(([^)]+)\)/.exec(block);
      if (!url) continue;
      const data = await toDataUrl(await (await fetch(url[1].replace(/["']/g, ''))).blob());
      out.push(block.replace(url[0], `url(${data})`));
    }
  }
  return out.join('\n');
}

export function LivePlaque({
  data,
  fileName,
  onDownload,
}: {
  data: LivePlaqueData;
  fileName: string;
  onDownload?: () => void;
}) {
  const boxRef = useRef<HTMLDivElement>(null);
  const frameRef = useRef<HTMLIFrameElement>(null);
  const [scale, setScale] = useState(0);
  const [making, setMaking] = useState(false);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const box = boxRef.current;
    if (!box) return;
    const fit = () => setScale(box.clientWidth / data.width);
    fit();
    const ro = new ResizeObserver(fit);
    ro.observe(box);
    return () => ro.disconnect();
  }, [data.width]);

  const download = useCallback(async () => {
    onDownload?.();
    if (data.png_url) {
      window.open(data.png_url, '_blank', 'noopener');
      return;
    }
    const doc = frameRef.current?.contentDocument;
    if (!doc) return;
    setMaking(true);
    setFailed(false);
    try {
      await doc.fonts?.ready;
      const fontEmbedCSS = await plaqueFontCSS(doc);
      const url = await toPng(doc.documentElement, {
        fontEmbedCSS,
        width: data.width,
        height: data.height,
        pixelRatio: 1,
        canvasWidth: data.width,
        canvasHeight: data.height,
      });
      const a = document.createElement('a');
      a.href = url;
      a.download = fileName;
      a.click();
    } catch {
      setFailed(true);
    } finally {
      setMaking(false);
    }
  }, [data, fileName, onDownload]);

  return (
    <div className="w-full flex flex-col items-center gap-2">
      <div
        ref={boxRef}
        className="w-full relative overflow-hidden rounded-lg"
        style={{ height: scale ? data.height * scale : undefined, aspectRatio: scale ? undefined : `${data.width} / ${data.height}` }}
      >
        {scale > 0 && (
          <iframe
            ref={frameRef}
            title="Accreditation Plaque"
            srcDoc={data.html}
            sandbox="allow-same-origin"
            scrolling="no"
            style={{
              width: data.width,
              height: data.height,
              border: 0,
              transform: `scale(${scale})`,
              transformOrigin: 'top left',
              position: 'absolute',
              top: 0,
              left: 0,
            }}
          />
        )}
      </div>
      <button
        type="button"
        onClick={download}
        disabled={making}
        className="w-full py-2 px-3 bg-[#00E5FF] hover:bg-[#00B4D8] disabled:opacity-60 text-black font-mono font-bold text-xs rounded-lg shadow-xl flex items-center justify-center gap-2 transition-all"
      >
        {making ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}
        Download Digital Plaque (.PNG)
      </button>
      {failed && (
        <p className="text-[10px] font-mono text-gray-400">
          The download did not work in this browser: try again, or open this page in another browser.
        </p>
      )}
    </div>
  );
}
