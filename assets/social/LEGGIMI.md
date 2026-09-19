# Card social

Sorgente unica delle immagini pubblicate su Instagram e X.

- `iosa_cards.html` — le quattro card in un solo file. La card si sceglie con
  `?c=1..4`. I colori di livello sono quelli di `VPI_SCALE` in
  `backend/vpi_core.py`: una card che mostra un record dichiara il proprio
  livello con `style="--lvl:#RRGGBB"` sulla `<section>`, e cifra, badge e riga
  evidenziata lo seguono. Il ciano del marchio resta solo sulla cornice.
- `render_cards.mjs` — rende le quattro PNG a 1080x1080 (formato quadrato: la
  griglia del profilo Instagram ritaglia sempre a 1:1).

Rigenerare:

    npm i playwright
    node render_cards.mjs

Le PNG finiscono in `cards/` e vanno copiate in `frontend/public/social/`.
