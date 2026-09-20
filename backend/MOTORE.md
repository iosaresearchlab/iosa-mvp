# Il motore di ingestione: dove gira

## Il problema

`main.py` chiamava `start_engine()` all'avvio, quindi lo scheduler viveva dentro
il servizio web. Il piano gratuito di Render spegne un web service dopo circa un
quarto d'ora senza richieste HTTP: con il servizio moriva lo scheduler.

Misurato il 20 settembre 2026 sugli inserimenti ora per ora: **dieci ore di buco
la notte** (21:00 → 06:00 UTC) e altre ore vuote in pieno giorno. Il buco
notturno attraversa il reset della quota YouTube delle 08:00 UTC, quindi non era
la quota: era il servizio che dormiva.

## La soluzione, a costo zero

**Lo scheduler sta nel database.** `pg_cron` e `pg_net` sono compresi in
Supabase e non costano niente. Ogni venti minuti il database chiama
`POST /api/ingest/run` sul backend. La chiamata in arrivo **sveglia anche il
servizio** se era in sospensione, che e' esattamente il problema da risolvere.

Niente worker a pagamento, niente minuti di GitHub Actions, nessun servizio
terzo.

```
pg_cron (ogni 20 min)
   -> chiedi_un_giro_di_ingestione()
        -> legge il token dal Vault
        -> net.http_post verso il backend
             -> il backend si sveglia, risponde 202, e fa il giro
```

### Cosa e' gia' configurato sul database

| Oggetto | Cosa fa |
| --- | --- |
| estensioni `pg_cron`, `pg_net` | attive |
| segreto `INGEST_TRIGGER_TOKEN` nel Vault | generato, 48 caratteri casuali |
| funzione `chiedi_un_giro_di_ingestione()` | legge il token e chiama il backend |
| job `ingestione-iosa` | `*/20 * * * *`, attivo |

### Cosa manca, e va fatto a mano una volta sola

1. Copiare il token dal Vault di Supabase (Project Settings → Vault, segreto
   `INGEST_TRIGGER_TOKEN`) e metterlo su Render come variabile d'ambiente con
   lo stesso nome.
2. Mettere `IOSA_ENGINE_MODE=off` su Render. Senza, lo scheduler interno
   continua a girare quando il servizio e' sveglio e si ingerisce due volte:
   quota YouTube pagata doppia per gli stessi video.

Fino a quel momento il job gira e riceve 401 (token mancante sul backend) o 404
(endpoint non ancora deployato). Non rompe niente: si vede nei log.

## Controllare che stia girando

Le ultime chiamate partite dal database:

```sql
select r.id, r.status_code, left(r.content, 120) as risposta, r.created
from net._http_response r order by r.id desc limit 10;
```

Lo storico del job:

```sql
select status, return_message, start_time
from cron.job_run_details
where jobid = (select jobid from cron.job where jobname = 'ingestione-iosa')
order by start_time desc limit 10;
```

E se l'indice si sta aggiornando davvero:

```sql
select max(detected_at), now() - max(detected_at) as fa from posts;
```

Se `fa` supera i quaranta minuti, qualcosa non va.

Sul backend:

```
tail -f backend/logs/iosa.log
```

## Le modalita' del motore

`IOSA_ENGINE_MODE` decide chi lo fa girare.

| Valore | Cosa succede |
| --- | --- |
| `inline` (default) | lo scheduler parte dentro il processo che chiama `start_engine()`, com'e' sempre stato |
| `off` | non parte niente: ci pensa pg_cron |

Il default resta `inline` apposta: cambiare modalita' e' una scelta di
dispiegamento e non deve succedere da sola al primo deploy.

## Un giro a mano

    python run_engine.py --un-ciclo

Esce con codice diverso da zero se ogni passo del giro e' fallito.

`run_engine.py` senza argomenti resta acceso e cicla: serve solo se un giorno
il motore girera' su una macchina sempre accesa. Oggi non e' il caso.

## Se si volesse cambiare assetto

Spegnere il cron del database:

```sql
select cron.unschedule('ingestione-iosa');
```

e rimettere `IOSA_ENGINE_MODE=inline` su Render, tornando al comportamento di
prima — con il buco notturno che ne consegue.
