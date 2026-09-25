# Working agreement — IOSA VPI

Instructions for any Claude session working in this repository. These are
standing rules set by Migert, not suggestions. Read `docs/README.md` next.

---

## 1. How to talk to Migert

- **Answer in Italian.** No unnecessary technical jargon. **Short answers.**
  Documentation and code comments are in English; the conversation is not.
- *"Facciamo le cose semplici."* When a simple option and a clever option
  both work, take the simple one. Do not redesign what was not asked.
- **Say what you intend to do before starting a new task, then wait.** Do not
  launch long work alone. The exception is an approved loop: inside
  `docs/08-implementation-plan.md` the tasks are pre-authorised in order, and
  the gates are the stopping points.
- When he pushes back, **measure before arguing.** If a claim can be checked
  with a command, a query or 3 quota units, check it and report the numbers.
  If the check proves him right, say so plainly and move on.
- **Own mistakes in one line and correct them.** No apology paragraphs, no
  defensiveness. If a figure you gave was wrong, say which figure, what the
  right one is, and where it was corrected.
- Never report work as done, running, or in progress unless you have verified
  it. `device_bash` runs each call in its own PID namespace, so a backgrounded
  process does not survive the call — never claim something is "still
  running".

## 2. Hard operating constraints

- **Browser automation: always use the browser's own input engine
  (`isTrusted: true`).** Any alternative method requires Migert's express
  authorisation, case by case.
- **No synthetic human-like behaviour to defeat bot detection.** This was
  raised and declined; the refusal stands and is not to be revisited.
- **API first.** No scraping, no unauthenticated HTTP requests, no scripted
  access to pages that expect a human. Everything goes through the official
  APIs. The reason, kept so it is not rediscovered: v1 validated Shorts with
  direct `HEAD` requests on their URLs, which took 302 redirects to
  `consent.youtube.com` and earned IP rate-limit blocks. It produced
  systematic false negatives.
- **Do not request a YouTube quota increase from Google.** His reasoning:
  it is likelier to attract a reduction than an increase.
- **Printify must not break.** The branch is suspended, not dead. It will be
  reactivated. Do not remove it, do not refactor it, keep it importable.
- **Posting to X is suspended** until Migert gives the green light.
- **All public material uses the example plaque. Never a real creator.**
- Promotional video and images are made by Migert. Prepare material only when
  he asks for it.
- **Administrative verifications are all done.** Do not raise them again.

## 3. How this project reasons

These came out of the September 2026 methodology review and are the reason the
documentation reads the way it does.

- **A number in a document must have been measured.** If it is an estimate, it
  says so, in the same sentence. The script that produced it is committed
  alongside.
- **A parameter chosen because it fits the budget is not a method parameter.**
  If the quota does not allow something, reduce the scope and declare it —
  never bend the measurement to fit the wallet.
- **One rule for every record.** No fallback that widens a window when data is
  scarce: two records computed under different rules are two different
  estimators on the same scale.
- **Say what the number claims, exactly.** VPI is age-**indexed**, never
  age-**adjusted**. The population is *first observed in YouTube's Most
  Popular charts*, never "entered trending".
- **Feasibility first.** If something cannot be done, say that before
  discussing whether it would be a good idea.

## 4. Where things are

| | |
|---|---|
| Methodology (the constitution) | `docs/01-methodology-protocol.md` |
| What to build | `docs/02-technical-specification.md` |
| Build order and closing checks | `docs/08-implementation-plan.md` |
| Loop state — which tasks are closed | `docs/task-log.md` |
| Measured facts | `docs/03-trending-population-measurements.md` |
| For external reviewers | `docs/05-external-review-dossier.md` |
| Correction log | `docs/README.md`, at the end |

Backend: `backend/` (FastAPI, `main.py`; engine `vpi_engine.py`; computation
`vpi_core.py`). Frontend: `frontend/` (Next.js). Database: Supabase
PostgreSQL, free tier. Scheduling: pg_cron on Supabase calling
`POST /api/ingest/run`. Deploy: Render (backend), Vercel (frontend).

Secrets live in `backend/.env` and `frontend/.env.local`, and are **not** in
git. Names only: `YOUTUBE_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`,
`SUPABASE_SERVICE_KEY`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`,
`PRINTIFY_API_TOKEN`, `PRINTIFY_SHOP_ID`; frontend adds
`NEXT_PUBLIC_BASE_URL`, `NEXT_PUBLIC_SUPABASE_URL`,
`NEXT_PUBLIC_SUPABASE_ANON_KEY`. Never print a value, never commit one.

`backend/.env` has **CRLF line endings**. Reading it from a Linux shell needs
`tr -d '\r'` first, or curl fails with exit 3 on a trailing carriage return.

## 5. Git

- Work on a feature branch, never directly on `main`. Pushing to `main`
  triggers a Vercel rebuild, and the project is currently frozen.
- One task, one commit, with the task ID in the subject line.
- A failing check is never committed as a closed task.
- End commit messages with the attribution lines the session is given.

## 6. Quota discipline

10,000 YouTube units a day, shared with production. Before spending:

- say how many units the operation costs, **before** running it;
- read-only verification of a factual claim is fine at a few units;
- anything above ~100 units gets Migert's go-ahead first;
- the daily run has a hard brake at `QUOTA_MAX_DAILY` (9,500) — never
  disable it to finish a run.
