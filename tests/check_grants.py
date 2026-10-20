"""FIX-1i: a migration that creates a table grants what the table needs.

From 30/10/2026 Supabase no longer grants new tables in `public` to the API
roles by default (Supabase mail of 23/09): a table created without a GRANT is
invisible to the backend (service_role) and to the site (anon). Every
migration from 20/10/2026 on that creates a table must, in the same file:
- GRANT on it to service_role (the backend's role);
- GRANT to anon or authenticated only together with row level security
  enabled on it and a policy for that role (or `revoke` them explicitly).
Migrations before CUTOFF ran under the old default and are not re-read.

    python tests/check_grants.py [file.sql ...]   # default: supabase/migrations and supabase/pending

Prints one line per missing grant and exits 1, or OK.
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CUTOFF = "20261020000000"          # migrations from this version on are checked

_CREATE = re.compile(r"create\s+(?:unlogged\s+)?table\s+(?:if\s+not\s+exists\s+)?(?:\"?public\"?\.)?\"?(\w+)\"?", re.I)


def _strip_comments(sql: str) -> str:
    return re.sub(r"/\*.*?\*/", "", re.sub(r"--[^\n]*", "", sql), flags=re.S)


def problems(sql: str) -> list:
    """[(table, reason)] for one migration."""
    s = _strip_comments(sql)
    out = []
    for t in dict.fromkeys(_CREATE.findall(s)):
        def granted(role):
            return re.search(rf"grant\s+[^;]*\bon\s+(?:table\s+)?(?:public\.)?\"?{t}\"?\b[^;]*\bto\s+[^;]*\b{role}\b", s, re.I)
        if not granted("service_role"):
            out.append((t, "no GRANT to service_role"))
        rls = re.search(rf"alter\s+table\s+(?:public\.)?\"?{t}\"?\s+enable\s+row\s+level\s+security", s, re.I)
        for role in ("anon", "authenticated"):
            if granted(role):
                policy = re.search(rf"create\s+policy\s+[^;]*\bon\s+(?:public\.)?\"?{t}\"?\b[^;]*\bto\s+[^;]*\b(?:{role}|public)\b", s, re.I)
                if not (rls and policy):
                    out.append((t, f"GRANT to {role} without row level security and a policy for it"))
    return out


def migrations():
    files = sorted((ROOT / "supabase" / "migrations").glob("*.sql")) + sorted((ROOT / "supabase" / "pending").glob("*.sql"))
    return [f for f in files if f.name[:14] >= CUTOFF]


def main(argv) -> int:
    files = [pathlib.Path(a) for a in argv] or migrations()
    bad = [(f.name, t, r) for f in files for t, r in problems(f.read_text(encoding="utf-8"))]
    for name, t, r in bad:
        print(f"FAIL {name}: table {t}: {r}")
    if not bad:
        print(f"OK {len(files)} migrations from {CUTOFF[:8]} checked")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
