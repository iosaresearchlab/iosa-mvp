# Archivio

File non piu usati dal progetto, conservati per riferimento.

## backend/
- backfill.py, backfill_vpi.py, recalculate_baselines.py: script one-shot di allineamento dati, gia eseguiti.
- fulfill_test_session.py: script di test con variant_id hardcoded.

## frontend/
- components/Header.tsx e header,tsx: due varianti dello stesso header, mai importate.
- api/checkout e api/webhooks/stripe: percorsi Next duplicati del backend FastAPI, con ID Printify placeholder.
- trophy-success: pagina di successo non raggiungibile, il flusso torna su /claim/{token}?status=success.
