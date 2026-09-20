"""Incolla la targa IOSA vera sul foglio bianco di una foto generata.

Nessun generatore di immagini riproduce la targa: inventa i numeri, l'handle
e il QR. Quindi la foto si fa con un foglio BIANCO in mano, e la targa vera ci
finisce sopra qui, con una trasformazione prospettica.

L'illuminazione del foglio originale viene riportata sulla targa: senza quel
passaggio si vede che e' incollata, perche' la carta ha un'ombra e la targa no.

    python componi_targa.py foto.png targa_a4.png uscita.png \
        --angoli 812,430 1290,388 1352,1090 866,1148

Gli angoli sono i quattro vertici del foglio nella foto, in pixel, in ordine:
alto-sinistra, alto-destra, basso-destra, basso-sinistra. Si leggono aprendo
la foto in qualunque visualizzatore che mostri le coordinate del puntatore.
Con --marca l'immagine esce con i quattro punti segnati, per controllarli
prima di comporre.
"""
import argparse

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


def coefficienti(sorgente, destinazione):
    """Gli 8 coefficienti che PIL vuole per una trasformazione prospettica.

    PIL mappa la DESTINAZIONE verso la SORGENTE, quindi il sistema va scritto
    al contrario rispetto a come viene istintivo.
    """
    A, b = [], []
    for (xs, ys), (xd, yd) in zip(sorgente, destinazione):
        A.append([xd, yd, 1, 0, 0, 0, -xs * xd, -xs * yd])
        A.append([0, 0, 0, xd, yd, 1, -ys * xd, -ys * yd])
        b += [xs, ys]
    return np.linalg.solve(np.asarray(A, float), np.asarray(b, float))


def mappa_luce(foto, maschera, sfocatura=28):
    """Quanto e' chiaro ogni punto del foglio, normalizzato sul suo massimo.

    Serve a riportare sulla targa l'ombra, la piega e il gradiente che la carta
    ha gia' nella foto.
    """
    grigi = np.asarray(foto.convert("L"), float)
    m = np.asarray(maschera, float) / 255.0
    if m.sum() < 10:
        return np.ones_like(grigi)
    riferimento = np.percentile(grigi[m > 0.5], 92) or 255.0
    luce = np.clip(grigi / max(riferimento, 1.0), 0.35, 1.15)
    return np.asarray(
        Image.fromarray((luce * 255).astype(np.uint8)).filter(
            ImageFilter.GaussianBlur(sfocatura)
        ), float
    ) / 255.0


def componi(foto_path, targa_path, uscita, angoli, ammorbidisci=2.0, forza_luce=0.85):
    foto = Image.open(foto_path).convert("RGB")
    targa = Image.open(targa_path).convert("RGB")
    L, A = foto.size

    sorgente = [(0, 0), (targa.width, 0), (targa.width, targa.height), (0, targa.height)]
    c = coefficienti(sorgente, angoli)

    deformata = targa.transform((L, A), Image.PERSPECTIVE, c, Image.BICUBIC)

    maschera = Image.new("L", (L, A), 0)
    ImageDraw.Draw(maschera).polygon(angoli, fill=255)
    if ammorbidisci > 0:
        maschera = maschera.filter(ImageFilter.GaussianBlur(ammorbidisci))

    luce = mappa_luce(foto, maschera)
    luce = 1.0 - forza_luce * (1.0 - luce)          # quanto pesa l'ombra
    arr = np.asarray(deformata, float) * luce[:, :, None]
    deformata = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))

    foto.paste(deformata, (0, 0), maschera)
    foto.save(uscita)
    return uscita


def marca(foto_path, uscita, angoli):
    foto = Image.open(foto_path).convert("RGB")
    d = ImageDraw.Draw(foto)
    d.polygon(angoli, outline=(255, 0, 85), width=4)
    for i, (x, y) in enumerate(angoli):
        d.ellipse([x - 12, y - 12, x + 12, y + 12], fill=(0, 229, 255))
        d.text((x + 16, y - 10), "ABCD"[i], fill=(255, 0, 85))
    foto.save(uscita)
    return uscita


def _punto(testo):
    x, y = testo.split(",")
    return (float(x), float(y))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("foto")
    ap.add_argument("targa", nargs="?")
    ap.add_argument("uscita")
    ap.add_argument("--angoli", nargs=4, type=_punto, required=True,
                    metavar=("AS", "AD", "BD", "BS"),
                    help="alto-sx alto-dx basso-dx basso-sx, ognuno x,y")
    ap.add_argument("--marca", action="store_true",
                    help="segna solo i quattro punti, non compone")
    ap.add_argument("--forza-luce", type=float, default=0.85)
    a = ap.parse_args()

    if a.marca:
        print(marca(a.foto, a.uscita, a.angoli))
    else:
        print(componi(a.foto, a.targa, a.uscita, a.angoli, forza_luce=a.forza_luce))
