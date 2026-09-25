"""Verifica che la scala VPI sia identica ovunque compaia.

Unica definizione: VPI_SCALE in backend/vpi_core.py, la stessa che il motore
scrive nella colonna vpi_color di ogni record e la stessa della documentazione
di progetto. Questo script confronta con quella ogni altro punto del repo che
mostra un livello. Si esegue da backend/:  python tests/audit_scala.py
"""
import io, re, sys, json, pathlib

R = pathlib.Path(__file__).resolve().parents[2]
UFFICIALE = [
    (10, "Hyper Outlier", "#FF0055"), (9, "Mega Outlier", "#FF2A00"),
    (8, "Outlier", "#FF5500"), (7, "Super Viral", "#FF8800"),
    (6, "Viral", "#FFAA00"), (5, "Breakout", "#FFCC00"),
    (4, "Trending", "#00CC88"), (3, "Rising", "#0099FF"),
    (2, "Moderate", "#7755FF"), (1, "Standard", "#888888"),
]
ATTESI = {c for _, _, c in UFFICIALE}
FONTI = {"vpi-scale.ts", "vpi_core.py", "audit_scala.py"}


def leggi(p):
    return io.open(R / p if not isinstance(p, pathlib.Path) else p, encoding="utf-8").read()


def tripla(testo, schema):
    return [(int(l), n.strip(), c.upper()) for l, n, c in re.findall(schema, testo)]


esiti = []

core = tripla(leggi("backend/vpi_core.py").split("VPI_SCALE = (")[1].split("\n)")[0],
              r'\([\d.]+,\s*(\d+),\s*"Lvl \d+ - ([^"]+)",\s*"(#[0-9A-Fa-f]{6})"\)')
esiti.append(("backend/vpi_core.py — VPI_SCALE", core == UFFICIALE, core))

ts = tripla(leggi("frontend/src/lib/vpi-scale.ts").split("SCALA")[1],
            r"\[[\d.]+,\s*(\d+),\s*'Lvl \d+ - ([^']+)',\s*'(#[0-9A-Fa-f]{6})'\]")
esiti.append(("frontend/src/lib/vpi-scale.ts — SCALA", ts == UFFICIALE, ts))

card = leggi("assets/social/iosa_cards.html")
c4 = [c.upper() for c in re.findall(r'class="lvl" style="color:(#[0-9A-Fa-f]{6})"', card)]
esiti.append(("card 4 — i dieci livelli", c4 == [c for _, _, c in UFFICIALE], c4))
c2 = [c.upper() for c in re.findall(r'id="c2" style="--lvl:(#[0-9A-Fa-f]{6})"', card)]
esiti.append(("card 2 — badge Lvl 10", c2 == ["#FF0055"], c2))

fuori = []
for p in list(R.glob("frontend/src/**/*.ts*")) + list(R.glob("backend/**/*.py")):
    if "node_modules" in str(p) or p.name in FONTI:
        continue
    for c in re.findall(r"#[0-9A-Fa-f]{6}", leggi(p)):
        if c.upper() in ATTESI:
            fuori.append(f"{p.relative_to(R)}: {c}")
esiti.append(("nessun colore della scala scritto a mano nel codice", not fuori, fuori))

# Ogni file che RENDERIZZA un livello deve passare dalla fonte unica.
rende, importa = [], []
for p in R.glob("frontend/src/**/*.tsx"):
    if "node_modules" in str(p):
        continue
    t = leggi(p)
    # Solo chi lo STAMPA in JSX: "{post.vpi_level_name" o livelloDiRecord(.
    # Dichiararlo in un type non e' renderizzarlo.
    if re.search(r"\{\s*\w+\.vpi_level_name|livelloDiRecord\(", t):
        rende.append(str(p.relative_to(R)))
    if "vpi-scale" in t:
        importa.append(str(p.relative_to(R)))
mancanti = sorted(set(rende) - set(importa))
esiti.append(("ogni pagina che mostra un livello legge vpi-scale", not mancanti, mancanti))

t = leggi("backend/generate_trophy.py")
# Sulla targa seguono la scala il badge del livello E la cornice del pannello
# centrale. Approvato da Migert il 20/09, con il vincolo esplicito: solo la
# cornice, nessun'altra modifica e nessuna regressione sul resto del disegno.
centrale = re.search(r'<!-- Center Panel -->\s*<div class="([^"]*)"', t)
classi_centrali = centrale.group(1) if centrale else ""
esiti.append(("targa — badge e cornice seguono la scala",
              "from vpi_core import VPI_SCALE" in t
              and "level_badge_style" in t
              and "level_frame_style" in t
              and "emerald" not in classi_centrali,
              classi_centrali[-60:] or None))

# Due date e non una: il conteggio e' congelato al momento della misura, e la
# sola data di pubblicazione si presterebbe a essere letta come la data delle
# visualizzazioni.
esiti.append(("targa — due date, pubblicazione e misura",
              "PUBLISHED:" in t and "MEASURED:" in t and "{measured_date}" in t,
              None))

# Il resto del disegno non si tocca: le misure sono quelle dell'area di stampa
# della tazza. Se cambiano, la tazza esce sbagliata.
esiti.append(("targa — misure e colonne invariate",
              'w-[2700px] h-[1120px]' in t
              and t.count('class="w-[23%]') == 2
              and 'class="w-[50%]' in t,
              None))

# Il corpo del popup (le dieci soglie) deve esistere una volta sola.
corpi = sorted(str(p.relative_to(R)) for p in R.glob("frontend/src/**/*.tsx")
               if "node_modules" not in str(p)
               and "Levels (10), set by the project owner" in leggi(p))
esiti.append(("popup metodologia — un solo corpo",
              corpi == ["frontend/src/components/MetodologiaModal.tsx".replace("/", "\\")]
              or len(corpi) == 1, corpi))

ok = True
for nome, passa, det in esiti:
    print(("  OK   " if passa else " FAIL  ") + nome)
    if not passa:
        ok = False
        print("         " + json.dumps(det, ensure_ascii=False)[:700])
print("\nESITO:", "scala allineata ovunque" if ok else "DISALLINEAMENTI PRESENTI")
sys.exit(0 if ok else 1)
