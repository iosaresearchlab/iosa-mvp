"""The slowest database call of a run, for its notes (FIX-1b, 20/10/2026).

On 19/10 at 00:37:56 UTC the processing of 18/10 failed with 57014
(statement timeout): close_exits_of_day ran past the 8 s the API roles get
(`authenticator`, statement_timeout=8s). 02 section 4.8 asks every query of
the run to stay far from that limit; the run notes carry the slowest call
("slowest query N ms (label)") so the nightly check sees the margin shrink
before it runs out.

TimedClient wraps the Supabase client the run uses and times every
.execute() of a builder started by .table(), .from_() or .rpc(). The time is
the call as the run sees it (network included), the one the timeout cuts.
"""
import time

TIMEOUT_MS = 8000          # statement_timeout of the API roles (authenticator)


class Timings:
    def __init__(self):
        self.max_ms = None
        self.label = None
        self.calls = 0

    def record(self, label, ms):
        self.calls += 1
        if self.max_ms is None or ms > self.max_ms:
            self.max_ms, self.label = ms, label

    def note(self):
        if self.max_ms is None:
            return "slowest query: no database call timed"
        return f"slowest query {round(self.max_ms)} ms ({self.label}, {self.calls} calls)"


class _Chain:
    """A query builder whose .execute() is timed; every builder it returns is
    wrapped the same way."""

    def __init__(self, obj, timings, label):
        self._obj, self._timings, self._label = obj, timings, label

    def __getattr__(self, name):
        attr = getattr(self._obj, name)
        if name == "execute":
            def run(*a, **k):
                t0 = time.perf_counter()
                try:
                    return attr(*a, **k)
                finally:
                    self._timings.record(self._label, (time.perf_counter() - t0) * 1000)
            return run
        if callable(attr):
            def call(*a, **k):
                out = attr(*a, **k)
                return _Chain(out, self._timings, self._label) if hasattr(out, "execute") else out
            return call
        return _Chain(attr, self._timings, self._label) if hasattr(attr, "execute") else attr


class TimedClient:
    def __init__(self, client, timings=None):
        self._client = client
        self.timings = timings or Timings()

    def table(self, name):
        return _Chain(self._client.table(name), self.timings, name)

    def from_(self, name):
        return _Chain(self._client.from_(name), self.timings, name)

    def rpc(self, fn, *a, **k):
        return _Chain(self._client.rpc(fn, *a, **k), self.timings, f"rpc {fn}")

    def __getattr__(self, name):
        return getattr(self._client, name)


def timed(client):
    """The client wrapped once (an already timed client is returned as it is)."""
    return client if isinstance(client, TimedClient) else TimedClient(client)
