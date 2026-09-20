# Il motore di ingestione: dove gira

## Il problema che questo risolve

`main.py` chiamava `start_engine()` all'avvio, quindi lo scheduler viveva dentro
il servizio web. Il piano gratuito di Render spegne un web service dopo circa un
quarto d'ora senza richieste HTTP: con il servizio moriva lo scheduler.

Misurato il 20 settembre 2026 sugli inserimenti ora per ora: **dieci ore di buco
la notte** (21:00 → 06:00 UTC) e altre ore vuote in pieno giorno. Il buco
notturno attraversa il reset della quota YouTube delle 08:00 UTC, quindi non era
la quota: era il servizio che dormiva.

## Le tre modalita'

`IOSA_ENGINE_MODE` decide chi fa girare il motore.

| Valore | Cosa succede |
| --- | --- |
| `inline` (default) | lo scheduler parte dentro il processo che chiama `start_engine()`, com'e' sempre stato |
| `off` | non parte niente: se ne occupa un worker o un cron esterno |

Il default resta `inline` apposta: cambiare modalita' e' una scelta di
dispiegamento e non deve succedere da sola al primo deploy.

## Opzione A — worker dedicato (consigliata)

Un processo sempre acceso, separato dal web service. `render.yaml` nella radice
del repo lo descrive gia': servizio web con `IOSA_ENGINE_MODE=off` piu' un
worker che esegue `python run_engine.py`.

Costo: circa 7 $/mese per il worker su Render. In cambio l'indice non si ferma.

Funziona uguale su qualsiasi macchina sempre accesa:

    IOSA_ENGINE_MODE=worker python run_engine.py

## Opzione B — cron esterno (gratis)

Il web service resta l'unico servizio, con `IOSA_ENGINE_MODE=off`, e un cron di
fuori chiama `POST /api/ingest/run` ogni 20 minuti. L'endpoint risponde subito
con 202 e lavora in background, perche' un giro dura minuti e la richiesta
scadrebbe.

Serve `INGEST_TRIGGER_TOKEN` fra le variabili d'ambiente del backend. Senza,
l'endpoint risponde 503 e non fa niente: una porta aperta sull'ingestione senza
autenticazione sarebbe un modo semplice per farci bruciare la quota.

    curl -X POST https://iosa-mvp-backend.onrender.com/api/ingest/run \
      -H "Authorization: Bearer $INGEST_TRIGGER_TOKEN"

`.github/workflows/ingestione.yml` fa esattamente questo: basta mettere il
segreto omonimo nel repository. GitHub non garantisce la puntualita' dei cron,
quindi i giri possono slittare.

Due giri sovrapposti sono rifiutati: il secondo riceve `gia_in_corso` e non
parte, altrimenti si pagherebbe due volte la quota per gli stessi video.

## Opzione C — tenerlo sveglio a ping

Un cron che chiama `GET /` ogni dieci minuti tiene il servizio acceso e lo
scheduler interno continua a girare. Gratis e senza modifiche, ma consuma le 750
ore mensili del piano gratuito e basta un ping saltato per rimettere il servizio
a dormire. Va bene come tampone, non come assetto.

## Un giro solo, a mano

    python run_engine.py --un-ciclo

Esce con codice diverso da zero se ogni passo del giro e' fallito, cosi' un cron
esterno se ne accorge invece di segnare verde su un giro andato a vuoto.

## Cosa guardare per sapere se sta girando

    tail -f backend/logs/iosa.log

e sul database:

    select max(detected_at), now() - max(detected_at) as fa from posts;

Se `fa` supera il doppio di `INGEST_INTERVAL_MINUTES`, il motore e' fermo.
