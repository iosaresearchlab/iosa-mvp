"""OPS-2 (25/10/2026): apply_daily_views is called in batches of at most VIEWS_BATCH rows,
on every path (the night, the baselines completed by reprocess_day, the catch-up of later days)."""
import inspect

import vpi_engine


class _Rpc:
    def __init__(self, calls, fn, params):
        self.calls, self.fn, self.params = calls, fn, params

    def execute(self):
        self.calls.append((self.fn, len(self.params["rows"]), self.params["d"]))
        return type("R", (), {"data": len(self.params["rows"])})()


class _Client:
    def __init__(self):
        self.calls = []

    def rpc(self, fn, params):
        return _Rpc(self.calls, fn, params)


def test_batches_of_at_most_100_rows_cover_every_row():
    from datetime import date
    c = _Client()
    rows = [{"post_id": str(i), "views": 1.0} for i in range(1234)]
    assert vpi_engine.VIEWS_BATCH == 100
    assert vpi_engine._apply_views(c, date(2026, 10, 24), rows) == 1234
    sizes = [n for fn, n, d in c.calls]
    assert all(fn == "apply_daily_views" and d == "2026-10-24" for fn, _, d in c.calls)
    assert max(sizes) == 100 and sum(sizes) == 1234 and len(sizes) == 13


def test_no_path_calls_apply_daily_views_directly():
    src = inspect.getsource(vpi_engine)
    assert src.count('client.rpc("apply_daily_views"') == 1          # only inside _apply_views
    assert src.count("_apply_views(client,") == 4                    # the definition; night, completed baselines, catch-up
