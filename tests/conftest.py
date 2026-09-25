"""Shared pytest configuration for the repository-level test suite.

Tests in this folder import backend modules by their bare names
(``import vpi_core``), the same way the backend imports them at runtime
(Render runs with ``rootDir: backend``). Putting ``backend/`` on the path
here keeps that true when pytest is run from the repository root, locally
and in CI.

No test in this suite may call the real YouTube API: the quota is a daily
production budget. HTTP is mocked (``responses``).
"""

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"

if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
