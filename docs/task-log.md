# Task log — v2 implementation

The state of the loop defined in `08-implementation-plan.md`. **This file is
the source of truth for what is closed.** A session picks up the first task
that is not `CLOSED` and works only that one.

Update this file in the same commit as the task it refers to. Record the
commit hash and the evidence — the command that passed, not an adjective.

| Task | State | Commit | Evidence |
|---|---|---|---|
| T-01 test and CI scaffolding | OPEN | | |
| T-02 regression harness | OPEN | | |
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
