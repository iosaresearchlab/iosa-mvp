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
    def __init__(self, data):
        self.data = data


class _Table:
    def __init__(self, conn, name):
        self.conn, self.name, self.op = conn, name, None

    def insert(self, rows):
        self.op, self.rows, self.conflict = "insert", rows, None
        return self

    def select(self, cols="*"):
        self.op, self.cols, self.filters = "select", cols, []
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

    def upsert(self, rows, on_conflict=None):
        self.op, self.rows, self.conflict = "upsert", rows, on_conflict
        return self

    def execute(self):
        if self.op == "update":
            q = sql.SQL("update {} set {} where {} returning *").format(
                sql.Identifier(self.name),
                sql.SQL(", ").join(sql.SQL("{} = %s").format(sql.Identifier(c)) for c in self.values),
                sql.SQL(" and ").join(sql.SQL("{} = any(%s)").format(sql.Identifier(c))
                                      for c, _ in self.filters))
            vals = list(self.values.values()) + [v for _, v in self.filters]
            with self.conn.transaction(), self.conn.cursor(row_factory=dict_row) as cur:
                cur.execute(q, vals)
                return _Result([{k: _plain(v) for k, v in r.items()} for r in cur.fetchall()])
        if self.op == "select":
            if self.cols != "*":
                raise NotImplementedError("PgClient.select supports '*' only")
            q = sql.SQL("select * from {}").format(sql.Identifier(self.name))
            vals = []
            if self.filters:
                q += sql.SQL(" where ") + sql.SQL(" and ").join(
                    sql.SQL("{} = any(%s)").format(sql.Identifier(c)) for c, _ in self.filters)
                vals = [v for _, v in self.filters]
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
            upd = [c for c in cols if c not in key]
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

    def _pk(self):
        with self.conn.cursor() as cur:
            cur.execute("select a.attname from pg_index i join pg_attribute a "
                        "on a.attrelid = i.indrelid and a.attnum = any(i.indkey) "
                        "where i.indrelid = %s::regclass and i.indisprimary", (f"public.{self.name}",))
            return [r[0] for r in cur.fetchall()]


class _Rpc:
    def __init__(self, conn, fn, params):
        self.conn, self.fn, self.params = conn, fn, params
        self._order, self._range = None, None

    def order(self, col):
        self._order = col
        return self

    def range(self, a, b):
        self._range = (a, b)
        return self

    def execute(self):
        with self.conn.cursor() as cur:
            cur.execute("select proretset from pg_proc where proname = %s", (self.fn,))
            retset = cur.fetchone()[0]
        args = sql.SQL(", ").join(
            sql.SQL("{} => {}").format(sql.Identifier(k), sql.Placeholder()) for k in self.params)
        vals = [Jsonb(v) if isinstance(v, (list, dict)) else v for v in self.params.values()]
        if retset:
            q = sql.SQL("select * from {}({})").format(sql.Identifier(self.fn), args)
            if self._order:
                q += sql.SQL(" order by {}").format(sql.Identifier(self._order))
            if self._range:
                a, b = self._range
                q += sql.SQL(" offset {} limit {}").format(sql.Literal(a), sql.Literal(b - a + 1))
            with self.conn.transaction(), self.conn.cursor(row_factory=dict_row) as cur:
                cur.execute(q, vals)
                return _Result([{k: _plain(v) for k, v in r.items()} for r in cur.fetchall()])
        q = sql.SQL("select {}({})").format(sql.Identifier(self.fn), args)
        with self.conn.transaction(), self.conn.cursor() as cur:
            cur.execute(q, vals)
            return _Result(_plain(cur.fetchone()[0]))


class PgClient:
    def __init__(self, conn):
        self.conn = conn

    def table(self, name):
        return _Table(self.conn, name)

    def rpc(self, fn, params):
        return _Rpc(self.conn, fn, params)
