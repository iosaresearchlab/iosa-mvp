# Task log — v2 implementation

The state of the loop defined in `08-implementation-plan.md`. **This file is
the source of truth for what is closed.** A session picks up the first task
that is not `CLOSED` and works only that one.

Update this file in the same commit as the task it refers to. Record the
commit hash and the evidence — the command that passed, not an adjective.

| Task | State | Commit | Evidence |
|---|---|---|---|
| T-01 test and CI scaffolding | CLOSED | `5f50446`, `530dd37` | `CHK-CI`: workflow green on `530dd37` (backend tests, frontend build) — https://github.com/iosaresearchlab/iosa-mvp/actions/runs/36092416638. Local, clean `git archive` + `env -i`: `pytest -q` 24 passed |
| T-02 regression harness | CLOSED | this commit (subject `T-02: regression harness`) | on untouched code, clean `git archive` + `env -i`: `pytest -q tests/test_regressione.py` 4 passed; full `CHK-REG` exit 0 (frontend build included). Negative control on a throwaway copy: renaming the Stripe webhook route -> 1 failed (`routes no longer registered: POST /api/webhooks/stripe`); renaming `send_printify_order` -> 3 failed |
| T-03 pin current core behaviour | OPEN | | |
| **GATE-0 database** | | | |
| T-04 migration: new tables | OPEN | | |
| T-05 migration: new columns on posts | OPEN | | |
| T-06 entries_of_day() + v1 archiving | OPEN | | |
| **GATE-1 engine** | | | |
| T-07 backend/census.py | OPEN | | |
| T-08 backend/baseline.py | OPEN | | |
| T-09 quota counter and brake | OPEN | | |
| T-10 rewrite ingestion entry point | OPEN | | |
| T-11 dead branches to archive/ | OPEN | | |
| T-12 endpoints | OPEN | | |
| **GATE-2 dry run** | | | |
| T-13 dry run on 3 countries | OPEN | | |
| T-14 scheduling and reactivation | OPEN | | |
| T-15 day 0: snapshot only | OPEN | | |
| T-16 day 1: first real records | OPEN | | |
| T-17 day 1 audit | OPEN | | |
| **GATE-3 GO / NO-GO** | | | |
| T-18 data layer and overall chart | OPEN | | |
| T-19 leaderboard at day 1 | OPEN | | |
| T-20 claim page and plaque | OPEN | | |
| T-21 public methodology text | OPEN | | |
| T-22 three weeks of accumulation | OPEN | | |
| T-23 deferred measurements | OPEN | | |
| T-24 scale calibration | OPEN | | |
| T-25 final review and production | OPEN | | |

States: `OPEN`, `IN PROGRESS`, `CLOSED`, `BLOCKED — <why>`.

---

## Notes

Anything learned during a task that the next session needs: a surprise in the
existing code, a check that had to be rewritten, a figure that came out
different from the plan. One line each, dated. Do not use this file for
decisions — those belong in `01` or in the correction log.

- 2026-09-25: `backend/tests/` already exists (24 tests: `test_vpi_core.py`, `test_formati_motore.py`; `audit_scala.py` is a script). `pytest -q` from the root collects them together with `tests/`.
- 2026-09-25: the frontend build fails with an empty `NEXT_PUBLIC_SUPABASE_URL` (`supabaseUrl is required`, on `/sitemap.xml`). CI sets public placeholders (`http://127.0.0.1:54321`), no secrets.
- 2026-09-25: the shell on Migert's PC has no GitHub credentials: pushes are done by Migert from Windows. Git there needs delete permission on the folder (lock files).
- 2026-09-25: first CI run on `5f50446` failed in `backend tests` (frontend green): `vpi_engine.py` raises at import without `SUPABASE_URL`/`SUPABASE_KEY`. Locally it had passed only because `backend/.env` was read. Local checks now run on a clean `git archive` of `HEAD` with an emptied environment (`env -i`), the same conditions as CI.
- 2026-09-25: `frontend/node_modules` is built on Windows; the Linux shell builds from a clean `git archive` copy with its own `npm ci`, like CI.
- 2026-09-25: a commit cannot contain its own hash. Where the Commit column says "this commit", the hash is the commit whose subject carries that task ID.
- 2026-09-25: `CHK-REG` as listed in T-02 covers Printify, the plaque modules and the routes. It does **not** assert that an existing v1 claim token still resolves, which T-20 says `CHK-REG` covers: that needs a database fixture, and must be added before T-20 at the latest.
- 2026-09-25: `main.py` uses the deprecated `@app.on_event("startup")`; FastAPI warns, it still works. Not touched.
