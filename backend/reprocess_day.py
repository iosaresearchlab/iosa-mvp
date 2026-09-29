"""reprocess_day <day>: finish the processing of a day whose census is complete.

    python backend/reprocess_day.py 2026-09-28

Uses the stored snapshot of the day as its census: the charts are never read
again. Refuses a day whose census is incomplete, whose snapshot is not the one
the census counted, or that is still being read (vpi_engine.reprocess_day).
The same work runs on Render through POST /api/ingest/reprocess/{day}, and by
itself at the 00:30 second attempt when the night's processing failed.
Quota: baselines as on a normal night, plus 1 unit per 50 titles; the 9,500
brake applies to this pass. Prints the rewritten run report.
"""

import sys
from datetime import date

from vpi_engine import ReprocessRefused, riprendi_un_giorno


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    try:
        row = riprendi_un_giorno(date.fromisoformat(argv[1]))
    except ReprocessRefused as e:
        print(f"REFUSED: {e}")
        return 1
    for k in ("day", "outcome", "census_complete", "entries", "updated", "exits",
              "quota_total", "baselines_complete", "reprocessed_at"):
        print(f"{k}: {row.get(k)}")
    print(f"notes: {row.get('notes')}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
