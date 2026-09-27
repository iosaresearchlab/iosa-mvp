/**
 * Data di inizio della serie pubblicata (docs/01 §1).
 *
 * Decisione del titolare, 27/09/2026: le notti 0 (25/09) e 1 (26/09) restano
 * nel database come stati di riferimento, ma non fanno parte della serie
 * pubblicata. La serie parte dalla prima lettura che supera
 * tests/check_run.py; la data si scrive qui, in backend/vpi_core.py e in
 * docs/01 §1 nello stesso commit (tests/test_index_start.py li confronta).
 * Finche' e' null nessun record e' pubblicato.
 */
export const INDEX_START_DATE: string | null = null;

/** Il limite inferiore di entered_on per ogni lettura pubblica di posts. */
export const SERIES_FLOOR: string = INDEX_START_DATE ?? '9999-12-31';
