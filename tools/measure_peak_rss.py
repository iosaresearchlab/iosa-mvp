"""Peak resident memory of the two heavy backend paths (FIX-1c, 20/10/2026).

    python tools/measure_peak_rss.py plaque     # one plaque render (Chromium)
    python tools/measure_peak_rss.py room       # /api/room/latest on a cache miss

Each path runs in a child process; this process samples the resident memory
of the child and of every process below it (Chromium's) from /proc every
20 ms and prints the baseline, the peak and the difference in MB (PSS: shared
pages split between processes; the RSS sum, which counts them twice, too).
Linux only.

`room` reads the real window through room_records with the service key in
backend/.env (never printed) and builds the payload, the JSON and its gzip
exactly as main._room_response does; one process, so the child also prints
its own RSS after the imports and its peak (ru_maxrss), the reliable figure. `plaque` renders one example plaque
with generate_trophy._render_png_sync (CHROMIUM_EXECUTABLE points it at
another Chromium binary when Playwright's own is not installed). No YouTube
quota.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"


def _children():
    kids = {}
    for p in Path("/proc").iterdir():
        if p.name.isdigit():
            try:
                ppid = int((p / "stat").read_text().rsplit(")", 1)[1].split()[1])
                kids.setdefault(ppid, []).append(int(p.name))
            except (OSError, IndexError, ValueError):
                pass
    return kids


def tree_kb(pid):
    """(RSS, PSS) of pid and every process below it, in kB. RSS counts a page
    shared by two Chromium processes twice; PSS splits it between them, so
    the sum of PSS is the memory the tree really holds."""
    kids, rss, pss, todo = _children(), 0, 0, [pid]
    while todo:
        p = todo.pop()
        try:
            for line in Path(f"/proc/{p}/smaps_rollup").read_text().splitlines():
                if line.startswith("Rss:"):
                    rss += int(line.split()[1])
                elif line.startswith("Pss:"):
                    pss += int(line.split()[1])
        except OSError:
            pass
        todo += kids.get(p, [])
    return rss, pss


CHILD = {
    "plaque": """
import generate_trophy, os, time
exe = os.environ.get("CHROMIUM_EXECUTABLE")   # a Chromium other than Playwright's own
if exe:
    from playwright.sync_api._generated import BrowserType
    _launch = BrowserType.launch
    BrowserType.launch = lambda self, *a, **k: _launch(self, *a, **{"executable_path": exe, **k})
time.sleep(1.0)
generate_trophy._render_png_sync(record_id="rss_probe", vpi_score="+48.5x", user_handle="@probe",
    content_title="A measured video", e_act="125000", e_base="2577", recorded_date="2026-10-10",
    measured_date="2026-10-14", output_dir="renders", file_id="rss_probe")
time.sleep(0.5)
""",
    "room": """
import gzip, json, os, time
from dotenv import load_dotenv
load_dotenv(".env")
import main
from supabase import create_client
c = create_client(os.environ["SUPABASE_URL"].strip(), os.environ["SUPABASE_SERVICE_KEY"].strip())
import resource
def vmrss():
    for line in open("/proc/self/status"):
        if line.startswith("VmRSS:"):
            return int(line.split()[1])
base = vmrss()                                   # imported, nothing built yet
runs = main._room_window(c, None)
body = json.dumps(main.room_payload(c, runs), ensure_ascii=False, separators=(",", ":")).encode()
gz = gzip.compress(body, 6)
peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
print(f"room: {len(body)} bytes, gzip {len(gz)}; process RSS after imports {base // 1024} MB, "
      f"peak {peak // 1024} MB, added {(peak - base) // 1024} MB", flush=True)
time.sleep(0.5)
""",
}


def main(argv):
    mode = argv[1] if len(argv) > 1 else ""
    if mode not in CHILD:
        sys.exit(__doc__)
    child = subprocess.Popen([sys.executable, "-c", CHILD[mode]], cwd=BACKEND,
                             env={**os.environ, "IOSA_ENGINE_MODE": "off"})
    time.sleep(0.8)
    base_rss, base_pss = tree_kb(child.pid)
    peak_rss, peak_pss = base_rss, base_pss
    while child.poll() is None:
        rss, pss = tree_kb(child.pid)
        peak_rss, peak_pss = max(peak_rss, rss), max(peak_pss, pss)
        time.sleep(0.02)
    mb = lambda kb: round(kb / 1024, 1)                                # noqa: E731
    out = {"mode": mode, "exit": child.returncode,
           "baseline_pss_mb": mb(base_pss), "peak_pss_mb": mb(peak_pss),
           "added_pss_mb": mb(peak_pss - base_pss), "peak_rss_sum_mb": mb(peak_rss)}
    print(json.dumps(out))
    return child.returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv))
