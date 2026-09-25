"""One quota counter per run, and the brake.

docs/02-technical-specification.md section 4.6; docs/08 T-09; CLAUDE.md
section 6. Counted, not estimated: every HTTP attempt to the YouTube Data
API is marked here BEFORE it is sent, so the counter can never lag behind
the calls, and the brake stops the call that would cross the limit.

The limit is QUOTA_MAX_DAILY (default 9,500). It may be lowered (the dry
run uses 2,000); it can never be raised above 9,500: a larger value is
clamped, because a brake that can be configured away is not a brake.
"""

from __future__ import annotations

import os
import threading
from collections import Counter

QUOTA_HARD_MAX = 9_500

# the ingest_run column each endpoint is written to
COLUMNS = {"charts": "quota_charts", "channels": "quota_channels",
           "playlist": "quota_playlist", "videos": "quota_videos"}


class QuotaExhausted(Exception):
    """The next call would cross the daily limit. The run is partial."""


def configured_limit(value=None) -> int:
    raw = value if value is not None else os.environ.get("QUOTA_MAX_DAILY", QUOTA_HARD_MAX)
    limit = int(raw)
    if limit <= 0:
        raise ValueError(f"QUOTA_MAX_DAILY must be positive, got {raw!r}")
    return min(limit, QUOTA_HARD_MAX)


class QuotaCounter:
    def __init__(self, limit=None):
        self.limit = configured_limit(limit)
        self.per_endpoint: Counter = Counter()
        self._lock = threading.Lock()
        self.braked = False

    def mark(self, endpoint: str) -> None:
        """Account one call to `endpoint` (1 unit), or refuse it."""
        if endpoint not in COLUMNS:
            raise ValueError(f"unknown endpoint {endpoint!r}")
        with self._lock:
            if self.total >= self.limit:
                self.braked = True
                raise QuotaExhausted(f"quota brake at {self.limit} units")
            self.per_endpoint[endpoint] += 1

    @property
    def total(self) -> int:
        return sum(self.per_endpoint.values())

    def as_ingest_run(self) -> dict:
        row = {col: self.per_endpoint[ep] for ep, col in COLUMNS.items()}
        row["quota_total"] = self.total
        return row
