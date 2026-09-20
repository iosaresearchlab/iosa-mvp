"""Mette la targa IOSA su un foglio A4, pronto da stampare.

La targa e' 2700x1120, rapporto 2,41. Un A4 e' 1,41 in orizzontale e 0,71 in
verticale: la targa non ci sta "dentro" ne' in un verso ne' nell'altro senza
lasciare bande. Quindi non la si deforma: la si impagina, con un'intestazione
sopra e una riga di verifica sotto, come un certificato stampato davvero.

    python targa_a4.py targa.png foglio_a4.png
"""
import sys
from PIL import Image, ImageDraw, ImageFont

DPI = 300
LARGA, ALTA = 2480, 3508          # A4 verticale a 300 dpi
MARGINE = 190

GHIACCIO = (247, 249, 251)
INCHIOSTRO = (13, 17, 23)
GRIGIO = (132, 150, 168)
LINEA = (214, 222, 230)


def _font(dimensione, grassetto=False):
    for percorso in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf" if grassetto
        else "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if grassetto
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        try:
            return ImageFont.truetype(percorso, dimensione)
        except OSError:
            continue
    return ImageFont.load_default()


def impagina(targa_path: str, uscita: str) -> str:
    targa = Image.open(targa_path).convert("RGB")

    foglio = Image.new("RGB", (LARGA, ALTA), GHIACCIO)
    d = ImageDraw.Draw(foglio)

    utile = LARGA - 2 * MARGINE
    scala = utile / targa.width
    targa = targa.resize((utile, int(targa.height * scala)), Image.LANCZOS)

    # Intestazione
    f_marchio = _font(74, True)
    f_sotto = _font(30)
    d.text((MARGINE, 250), "IOSA", font=f_marchio, fill=INCHIOSTRO)
    d.text((MARGINE, 345), "INSTITUTE FOR OPEN SOCIAL ANALYTICS",
           font=f_sotto, fill=GRIGIO)
    d.line([(MARGINE, 430), (LARGA - MARGINE, 430)], fill=LINEA, width=3)

    f_titolo = _font(56, True)
    d.text((MARGINE, 520), "VIRAL PERFORMANCE INDEX", font=f_titolo, fill=INCHIOSTRO)
    f_riga = _font(34)
    d.text((MARGINE, 610),
           "Independent measurement of one video against its own channel's baseline.",
           font=f_riga, fill=GRIGIO)

    # La targa, centrata verticalmente nello spazio che resta
    alto, basso = 780, ALTA - 620
    y = alto + (basso - alto - targa.height) // 2
    d.rectangle([MARGINE - 10, y - 10, LARGA - MARGINE + 9, y + targa.height + 9],
                outline=LINEA, width=3)
    foglio.paste(targa, (MARGINE, y))

    # Piede
    d.line([(MARGINE, ALTA - 430), (LARGA - MARGINE, ALTA - 430)], fill=LINEA, width=3)
    d.text((MARGINE, ALTA - 380),
           "Scan the code on this sheet to open the full record: the views, the",
           font=f_riga, fill=GRIGIO)
    d.text((MARGINE, ALTA - 330),
           "channel baseline, the ratio and the date it was measured.",
           font=f_riga, fill=GRIGIO)
    d.text((MARGINE, ALTA - 240), "iosa-mvp-psi.vercel.app",
           font=_font(34, True), fill=INCHIOSTRO)
    d.text((MARGINE, ALTA - 190),
           "Free. Nothing for sale. Independent, non-profit research.",
           font=_font(28), fill=GRIGIO)

    foglio.save(uscita, dpi=(DPI, DPI))
    return uscita


if __name__ == "__main__":
    sorgente = sys.argv[1] if len(sys.argv) > 1 else "targa.png"
    destinazione = sys.argv[2] if len(sys.argv) > 2 else "targa_a4.png"
    print(impagina(sorgente, destinazione))
