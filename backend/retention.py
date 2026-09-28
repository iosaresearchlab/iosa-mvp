"""Rolling 7-day retention of trend_snapshot (02 section 3.1).

Owner decision 28/09/2026: keep the last 7 reading days, drop the rest, no
exception for day 0. Snapshot rows are working data: the reference for
"absent yesterday" is always the last complete reading, and what open
records need lives in posts, post_daily and ingest_run.

A row never leaves the table without a copy. For each day that leaves the
window, in this order and never another:
  1. export the day's rows, one jsonb text line each, video_id order;
  2. write them to Supabase Storage (private bucket 'archivio'), gzip, one
     file per day: trend_snapshot/<day>.jsonl.gz;
  3. read the stored file back and check it line for line against the rows
     exported;
  4. only then delete, through purge_snapshot_day, which deletes only when
     the row count and the md5 of the file read back match the rows in the
     table, refuses a day inside the window and refuses the reference.
Any failure stops before the delete of that day and leaves every later day
untouched. The purge runs only after a complete census (vpi_engine), so the
day it runs on is the next reference and is never in reach.
"""
import gzip
import hashlib
import os
from datetime import date, timedelta

import requests

WINDOW_DAYS = 7
BUCKET = "archivio"
PREFIX = "trend_snapshot"
MAX_FILE_BYTES = 50 * 1024 * 1024   # free-tier upload ceiling, per file
RPC_PAGE = 1000                     # PostgREST returns at most 1,000 rows
TIMEOUT = 120


class ArchiveError(RuntimeError):
    """The archive could not be written or does not match: nothing deleted."""


def keep_from(reading_day: date) -> date:
    """First day kept: the reading day and the six before it."""
    return reading_day - timedelta(days=WINDOW_DAYS - 1)


def encode(lines: list[str]) -> bytes:
    """One line per row, gzip, no timestamp: the same rows give the same file."""
    return gzip.compress(("".join(line + "\n" for line in lines)).encode("utf-8"), mtime=0)


def decode(blob: bytes) -> list[str]:
    text = gzip.decompress(blob).decode("utf-8")
    if text and not text.endswith("\n"):
        raise ArchiveError("archive truncated: no final newline")
    return text.split("\n")[:-1] if text else []


def digest(lines: list[str]) -> str:
    """md5 of the lines joined by '|': string_agg(line, '|' order by key) in SQL."""
    return hashlib.md5("|".join(lines).encode("utf-8")).hexdigest()


class SupabaseStorage:
    """Private-bucket reads and writes with the service key."""

    def __init__(self, url: str, key: str, bucket: str = BUCKET, session=None):
        if not url or not key:
            raise ArchiveError("Storage not configured: URL or service key missing")
        self.base = f"{url.rstrip('/')}/storage/v1/object/{bucket}"
        self.headers = {"apikey": key, "Authorization": f"Bearer {key}"}
        self.http = session or requests

    @classmethod
    def from_env(cls):
        url = (os.getenv("NEXT_PUBLIC_SUPABASE_URL") or os.getenv("SUPABASE_URL") or "").strip()
        key = (os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
        return cls(url, key)

    def put(self, path: str, blob: bytes) -> None:
        r = self.http.post(f"{self.base}/{path}",
                           headers={**self.headers, "Content-Type": "application/gzip",
                                    "x-upsert": "true"},
                           data=blob, timeout=TIMEOUT)
        if r.status_code not in (200, 201):
            raise ArchiveError(f"upload of {path} failed: {r.status_code} {r.text[:200]}")

    def get(self, path: str) -> bytes:
        r = self.http.get(f"{self.base}/{path}", headers=self.headers, timeout=TIMEOUT)
        if r.status_code != 200:
            raise ArchiveError(f"read-back of {path} failed: {r.status_code} {r.text[:200]}")
        return r.content


class MemoryStorage:
    """For tests: the same two calls, in a dict."""

    def __init__(self):
        self.files = {}

    def put(self, path, blob):
        self.files[path] = bytes(blob)

    def get(self, path):
        if path not in self.files:
            raise ArchiveError(f"read-back of {path} failed: not found")
        return self.files[path]


def _pages(client, fn, params, order):
    out, start = [], 0
    while True:
        page = (client.rpc(fn, params).order(order)
                .range(start, start + RPC_PAGE - 1).execute().data) or []
        out.extend(page)
        if len(page) < RPC_PAGE:
            return out
        start += RPC_PAGE


def archive_lines(storage, path: str, lines: list[str]) -> dict:
    """Write the lines, read the file back, check it. Returns what was stored."""
    if not lines:
        raise ArchiveError(f"{path}: nothing to archive")
    blob = encode(lines)
    if len(blob) > MAX_FILE_BYTES:
        raise ArchiveError(f"{path}: {len(blob)} bytes, over the {MAX_FILE_BYTES} per-file limit")
    storage.put(path, blob)
    back = decode(storage.get(path))
    if back != lines:
        raise ArchiveError(f"{path}: the file read back differs from the rows exported "
                           f"({len(back)} lines back, {len(lines)} exported)")
    return {"path": path, "rows": len(back), "md5": digest(back), "bytes": len(blob)}


def export_day(client, storage, day) -> dict:
    day = str(day)[:10]
    rows = _pages(client, "snapshot_export", {"p_day": day}, "video_id")
    out = archive_lines(storage, f"{PREFIX}/{day}.jsonl.gz", [r["line"] for r in rows])
    out["day"] = day
    return out


def purge(client, storage, reading_day: date) -> list[dict]:
    """Archive and delete every snapshot day older than the window."""
    kf = keep_from(reading_day).isoformat()
    days = [str(r["day"])[:10] for r in
            (client.rpc("snapshot_days_before", {"p_day": kf}).execute().data or [])]
    done = []
    for day in sorted(days):
        a = export_day(client, storage, day)
        a["deleted"] = client.rpc("purge_snapshot_day", {
            "p_day": day, "p_keep_from": kf, "p_rows": a["rows"], "p_md5": a["md5"],
        }).execute().data
        done.append(a)
    return done


def note(reading_day: date, done: list[dict]) -> str:
    kf = keep_from(reading_day).isoformat()
    if not done:
        return f"retention: kept from {kf}, nothing older"
    parts = [f"{a['day']} {a['deleted']:,} rows {a['bytes'] / 1024:,.0f} KB" for a in done]
    return f"retention: kept from {kf}, archived then purged " + ", ".join(parts)
