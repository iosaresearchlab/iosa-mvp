"""The v2 daily reading as a one-off process: the fallback if pg_cron fails.

    python run_engine.py --un-ciclo

Runs one reading for today (UTC) and exits, with the same environment the
HTTP trigger uses (SNAPSHOT_ONLY, IOSA_COUNTRIES, QUOTA_MAX_DAILY). There is
no continuous loop any more: one reading a day, at 23:59 UTC, is the method
(docs/01 section 4; docs/02 section 5). The exit code is 0 only for
outcome 'ok', so a cron notices a partial or failed reading.
"""
import argparse
import sys

from log_iosa import configura, prendi
from vpi_engine import RunAlreadyExists, esegui_un_ciclo

log = prendi(__name__)


def un_ciclo() -> int:
    try:
        esito = esegui_un_ciclo()
    except RunAlreadyExists as e:
        log.warning("%s: nothing done.", e)
        return 2
    log.info("reading finished: outcome=%s quota=%s entries=%s exits=%s",
             esito.get("outcome"), esito.get("quota_total"),
             esito.get("entries"), esito.get("exits"))
    return 0 if esito.get("outcome") == "ok" else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--un-ciclo", action="store_true", required=True,
                    help="one reading for today, then exit")
    ap.parse_args()
    configura()
    return un_ciclo()


if __name__ == "__main__":
    sys.exit(main())
