"""A minimal stand-in for the supabase-py client, backed by PostgreSQL.

Implements exactly the calls the v2 engine makes, with PostgREST semantics:
  client.table(name).insert(rows) / .upsert(rows, on_conflict=...) .execute()
  client.table(name).select("*").in_(col, values) .execute()
  client.rpc(fn, params) [.order(col)] [.range(a, b)] .execute()
A set-returning function answers a list of dicts; a scalar function answers
the value. Rows written come back in .data, as PostgREST returns them. Each
call runs in its own savepoint, as each PostgREST request is its own
transaction: a failed call does not abort the test's transaction.

So the engine test runs the real SQL (every migration, the pending file)
and asserts real rows, instead of asserting on mocks of the database.
"""

import json
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


def _plain(v):
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    if isinstance(v, UUID):
        return str(v)
    return v


class _Result:
    def __init__(self, data, count=None):
        self.data = data
        self.count = count


class _Table:
    def __init__(self, conn, name):
        self.conn, self.name, self.op = conn, name, None

    def insert(self, rows):
        self.op, self.rows, self.conflict = "insert", rows, None
        return self

    def select(self, cols="*"):
        self.op, self.cols, self.filters = "select", cols, []
        self.orders, self.lim = [], None
        return self

    def order(self, col, desc=False):
        self.orders.append((col, desc))
        return self

    def limit(self, n):
        self.lim = n
        return self

    def gte(self, col, value):
        self.ranges = getattr(self, "ranges", []) + [(col, value)]
        return self

    def range(self, a, b):
        self.offset, self.lim = a, b - a + 1
        return self

    def in_(self, col, values):
        self.filters.append((col, list(values)))
        return self

    def update(self, values):
        self.op, self.values, self.filters = "update", values, []
        return self

    def eq(self, col, value):
        self.filters.append((col, [value]))
        return self

    def upsert(self, rows, on_conflict=None, ignore_duplicates=False):
        self.op, self.rows, self.conflict = "upsert", rows, on_conflict
        self.ignore_duplicates = ignore_duplicates
        return self

    def execute(self):
        if self.op == "update":
            # each value cast to its column's type, as PostgREST does from JSON
            ftypes = self._formatted_types()
            q = sql.SQL("update {} set {} where {} returning *").format(
                sql.Identifier(self.name),
                sql.SQL(", ").join(sql.SQL("{} = %s::{}").format(sql.Identifier(c), sql.SQL(ftypes[c]))
                                   for c in self.values),
                sql.SQL(" and ").join(sql.SQL("{} = any(%s)").format(sql.Identifier(c))
                                      for c, _ in self.filters))
            vals = [Jsonb(v) if ftypes[c] == "jsonb" and v is not None else v
                    for c, v in self.values.items()] + [v for _, v in self.filters]
            with self.conn.transaction(), self.conn.cursor(row_factory=dict_row) as cur:
                cur.execute(q, vals)
                return _Result([{k: _plain(v) for k, v in r.items()} for r in cur.fetchall()])
        if self.op == "select":
            if self.cols == "*":
                cols = sql.SQL("*")
            else:
                cols = sql.SQL(", ").join(sql.Identifier(c.strip()) for c in self.cols.split(","))
            q = sql.SQL("select {} from {}").format(cols, sql.Identifier(self.name))
            vals = []
            if self.filters:
                q += sql.SQL(" where ") + sql.SQL(" and ").join(
                    sql.SQL("{} = any(%s)").format(sql.Identifier(c)) for c, _ in self.filters)
                vals = [v for _, v in self.filters]
            for c, v in getattr(self, "ranges", []):
                q += sql.SQL(" and " if (self.filters or vals) else " where ") + \
                    sql.SQL("{} >= %s").format(sql.Identifier(c))
                vals.append(v)
            if self.orders:
                q += sql.SQL(" order by ") + sql.SQL(", ").join(
                    sql.SQL("{} desc" if d else "{}").format(sql.Identifier(c)) for c, d in self.orders)
            if self.lim is not None:
                q += sql.SQL(" limit {}").format(sql.Literal(self.lim))
            if getattr(self, "offset", None):
                q += sql.SQL(" offset {}").format(sql.Literal(self.offset))
            with self.conn.transaction(), self.conn.cursor(row_factory=dict_row) as cur:
                cur.execute(q, vals)
                return _Result([{k: _plain(v) for k, v in r.items()} for r in cur.fetchall()])
        rows = self.rows if isinstance(self.rows, list) else [self.rows]
        if not rows:
            return _Result([])
        cols = list(rows[0])
        types = self._types()
        stmt = sql.SQL("insert into {} ({}) values ({})").format(
            sql.Identifier(self.name),
            sql.SQL(", ").join(map(sql.Identifier, cols)),
            sql.SQL(", ").join(sql.Placeholder() * len(cols)))
        if self.op == "upsert":
            key = [self.conflict] if self.conflict else self._pk()
            upd = [] if getattr(self, "ignore_duplicates", False) else [c for c in cols if c not in key]
            target = sql.SQL(", ").join(map(sql.Identifier, key))
            if upd:
                stmt += sql.SQL(" on conflict ({}) do update set {}").format(
                    target,
                    sql.SQL(", ").join(sql.SQL("{0} = excluded.{0}").format(sql.Identifier(c)) for c in upd))
            else:
                stmt += sql.SQL(" on conflict ({}) do nothing").format(target)
        stmt += sql.SQL(" returning *")
        out = []
        with self.conn.transaction(), self.conn.cursor(row_factory=dict_row) as cur:
            for r in rows:
                vals = [Jsonb(r[c]) if types.get(c) == "jsonb" and r[c] is not None else r[c] for c in cols]
                cur.execute(stmt, vals)
                out.extend({k: _plain(v) for k, v in row.items()} for row in cur.fetchall())
        return _Result(out)

    def _types(self):
        with self.conn.cursor() as cur:
            cur.execute("select column_name, data_type from information_schema.columns "
                        "where table_schema='public' and table_name=%s", (self.name,))
            return dict(cur.fetchall())

    def _formatted_types(self):
        with self.conn.cursor() as cur:
            cur.execute("select attname, format_type(atttypid, atttypmod) from pg_attribute "
                        "where attrelid = %s::regclass and attnum > 0 and not attisdropped",
                        (f"public.{self.name}",))
            return dict(cur.fetchall())

    def _pk(self):
        with self.conn.cursor() as cur:
            cur.execute("select a.attname from pg_index i join pg_attribute a "
                        "on a.attrelid = i.indrelid and a.attnum = any(i.indkey) "
                        "where i.indrelid = %s::regclass and i.indisprimary", (f"public.{self.name}",))
            return [r[0] for r in cur.fetchall()]


class _Rpc:
    # max_rows: PostgREST's db-max-rows, None = unlimited (the project's setting).
    max_rows = None

    def __init__(self, conn, fn, params, count=None):
        self.conn, self.fn, self.params, self.count = conn, fn, params, count
        self._order, self._range = None, None

    def order(self, col):
        self._order = col
        return self

    def range(self, a, b):
        self._range = (a, b)
        return self

    def execute(self):
        with self.conn.cursor() as cur:
            cur.execute("select proretset, proargnames, "
                        "array(select t.typcategory from unnest(proargtypes) a join pg_type t on t.oid = a) "
                        "from pg_proc where proname = %s", (self.fn,))
            retset, argnames, cats = cur.fetchone()
        # PostgREST turns a JSON array into a PostgreSQL array for an array
        # parameter, and passes JSON otherwise: the same here.
        array_args = {n for n, c in zip(argnames or [], cats or []) if c == "A"}
        args = sql.SQL(", ").join(
            sql.SQL("{} => {}").format(sql.Identifier(k), sql.Placeholder()) for k in self.params)
        vals = [v if k in array_args and isinstance(v, list) else Jsonb(v) if isinstance(v, (list, dict)) else v
                for k, v in self.params.items()]
        if retset:
            q = sql.SQL("select * from {}({})").format(sql.Identifier(self.fn), args)
            if self._order:
                q += sql.SQL(" order by {}").format(sql.Identifier(self._order))
            a, b = self._range or (0, None)
            limit = None if b is None else b - a + 1
            if self.max_rows is not None:
                limit = self.max_rows if limit is None else min(limit, self.max_rows)
            if a:
                q += sql.SQL(" offset {}").format(sql.Literal(a))
            if limit is not None:
                q += sql.SQL(" limit {}").format(sql.Literal(limit))
            with self.conn.transaction(), self.conn.cursor(row_factory=dict_row) as cur:
                cur.execute(q, vals)
                rows = [{k: _plain(v) for k, v in r.items()} for r in cur.fetchall()]
                total = None
                if self.count == "exact":
                    cur.execute(sql.SQL("select count(*) as n from {}({})").format(sql.Identifier(self.fn), args), vals)
                    total = cur.fetchone()["n"]
                return _Result(rows, total)
        q = sql.SQL("select {}({})").format(sql.Identifier(self.fn), args)
        with self.conn.transaction(), self.conn.cursor() as cur:
            cur.execute(q, vals)
            return _Result(_plain(cur.fetchone()[0]))


class PgClient:
    def __init__(self, conn):
        self.conn = conn

    def table(self, name):
        return _Table(self.conn, name)

    def rpc(self, fn, params, count=None):
        return _Rpc(self.conn, fn, params, count)
