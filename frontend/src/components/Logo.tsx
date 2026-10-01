/**
 * Il marchio IOSA come un'unica immagine (UI-4, 01/10/2026): la "I" a punta,
 * "OSA" e "Institute for Open Social Analytics". Prodotto da
 * res/IOSA Logo Trasp.png (nessuna sorgente vettoriale): PNG e WebP a 1x e
 * 2x in public/brand, ritagliati sul contenuto, rapporto 3255:2203.
 * Mai piu' la punta disegnata accanto al testo: si leggeva "IIOSA".
 */
const RAPPORTO = 3255 / 2203;

export function Logo({ altezza = 48, className = '' }: { altezza?: number; className?: string }) {
  const larghezza = Math.round(altezza * RAPPORTO);
  return (
    <picture>
      <source type="image/webp" srcSet="/brand/iosa-logo@1x.webp 1x, /brand/iosa-logo@2x.webp 2x" />
      <img
        src="/brand/iosa-logo@1x.png"
        srcSet="/brand/iosa-logo@1x.png 1x, /brand/iosa-logo@2x.png 2x"
        width={larghezza}
        height={altezza}
        alt="IOSA - Institute for Open Social Analytics"
        className={`block ${className}`}
        style={{ width: larghezza, height: altezza }}
        decoding="async"
      />
    </picture>
  );
}
