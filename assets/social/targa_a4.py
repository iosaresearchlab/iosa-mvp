"""Rende la targa IOSA su un A4 ORIZZONTALE pieno, bordo a bordo.

Non si impagina la targa dentro un foglio: la targa ha rapporto 2,41 e un A4
orizzontale 1,41, quindi infilarcela dentro lascia bande bianche sopra e sotto.
Qui si rende il template alle proporzioni dell'A4 e le tre colonne si allungano
a riempire la pagina.

3508x2480 e' un A4 orizzontale a 300 dpi, di stampa.
"""
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

import generate_trophy as gt

# A4 orizzontale a 300 dpi. Si rende a meta' con deviceScaleFactor 2: stessa
# risoluzione finale, meta' della memoria per il layout.
LARGA, ALTA = 3508, 2480
SCALA = 2


def _a4(html: str) -> str:
    """Porta il template da 2700x1120 alle proporzioni dell'A4 orizzontale."""
    h = html.replace("w-[2700px] h-[1120px]", f"w-[{LARGA // SCALA}px] h-[{ALTA // SCALA}px]")
    # Con una pagina molto piu' alta, i margini e gli spazi verticali del
    # template originale diventano stretti: si allargano.
    h = h.replace('overflow-hidden p-12 flex', 'overflow-hidden p-16 flex')
    h = h.replace('py-10 px-8 relative z-10 border-2', 'py-14 px-10 relative z-10 border-2')
    h = h.replace('py-12 px-10 relative z-10 rounded-3xl bg-grid',
                  'py-16 px-12 relative z-10 rounded-3xl bg-grid')
    # A 1,41 le colonne 23/50/23 lasciano i pannelli laterali troppo stretti:
    # le sigle vanno a capo in mezzo alla parola. Si allargano i lati.
    h = h.replace('class="w-[23%]', 'class="w-[27%]')
    h = h.replace('class="w-[50%]', 'class="w-[42%]')

    # Il badge del livello andava a capo: meno respiro orizzontale, piu' stretto
    # il testo, e resta su una riga.
    h = h.replace('text-3xl font-mono-tech px-12 py-4 rounded-2xl font-black tracking-widest',
                  'text-xl font-mono-tech px-8 py-5 rounded-2xl font-black tracking-wide '
                  'whitespace-nowrap')

    # Le sigle lunghe dei pannelli bianchi, rimpicciolite quel tanto che basta
    # a non spezzarsi.
    h = h.replace('class="text-sm font-mono-tech text-gray-500 font-semibold">'
                  'INSTITUTE FOR OPEN SOCIAL ANALYTICS',
                  'class="text-xs font-mono-tech text-gray-500 font-semibold tracking-tight">'
                  'INSTITUTE FOR OPEN SOCIAL ANALYTICS')
    h = h.replace('class="text-gray-500 text-xs font-mono-tech uppercase font-bold">'
                  'INSTITUTE FOR OPEN SOCIAL ANALYTICS',
                  'class="text-gray-500 text-[10px] font-mono-tech uppercase font-bold '
                  'tracking-tight">INSTITUTE FOR OPEN SOCIAL ANALYTICS')
    h = h.replace('<div>HASH: <span class="text-gray-800 font-bold">{record_hash}</span></div>',
                  '<div class="whitespace-nowrap">HASH: '
                  '<span class="text-gray-800 font-bold">{record_hash}</span></div>')
    h = h.replace('<span class="font-bold">{domain_display}</span>',
                  '<span class="font-bold text-[11px] whitespace-nowrap">{domain_display}</span>')
    return h


def rendi(dati: dict, uscita: str) -> str:
    nome, stile_badge, stile_cornice = gt.resolve_level_and_style(
        dati["level_name"], dati["vpi_score"]
    )
    url = gt.DEFAULT_CLAIM_BASE_URL.rstrip("/") + "/claim/" + dati["record_id"]
    import urllib.parse
    html = gt.TROPHY_HTML_TEMPLATE.format(
        user_handle=dati["user_handle"],
        vpi_score=dati["vpi_score"],
        content_title=dati["content_title"],
        e_act=dati["e_act"],
        e_base=dati["e_base"],
        gamma=dati["gamma"],
        recorded_date=dati["recorded_date"],
        level_name=nome,
        level_badge_style=stile_badge,
        level_frame_style=stile_cornice,
        record_hash=dati["record_hash"],
        domain_display=gt.DEFAULT_CLAIM_BASE_URL.split("//")[-1].upper(),
        encoded_claim_url=urllib.parse.quote(url, safe=""),
    )

    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        pg = b.new_page(viewport={"width": LARGA // SCALA, "height": ALTA // SCALA},
                        device_scale_factor=SCALA)
        pg.set_content(_a4(html), wait_until="networkidle")
        pg.wait_for_timeout(2500)
        pg.screenshot(path=uscita)
        b.close()
    return uscita


if __name__ == "__main__":
    print(rendi({
        "user_handle": "@LASTRANK",
        "vpi_score": "6770.0x",
        "level_name": "Lvl 10 - Hyper Outlier",
        "content_title": "YouTube Short - United States",
        "e_act": "29,335,793",
        "e_base": "4,333",
        "gamma": "6,770x",
        "recorded_date": "2026-09-19",
        "record_id": "lastrank",
        "record_hash": "0x3BE6CA73",
    }, sys.argv[1] if len(sys.argv) > 1 else "targa_a4_orizzontale.png"))
