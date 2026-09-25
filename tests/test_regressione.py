"""Regression harness: what the v2 work must not break.

Run after every task of docs/08-implementation-plan.md as CHK-REG:

    pytest -q tests/test_regressione.py && (cd frontend && npm run build)

The frontend build is the second half of that command, not a test here.

The expected names below are a snapshot of the code on 25 September 2026,
before any v2 change (T-02). They are written out by hand on purpose: a list
computed from the current code would follow the code wherever it went and
could never fail. New routes and functions may be added; none of these may
disappear.

No test here calls a network service, renders a plaque or starts the engine:
modules are imported and inspected, nothing more.
"""

import importlib
import inspect

import pytest

# --- Printify: suspended, not dead. It must stay importable and complete. ---

PRINTIFY_PUBLIC_FUNCTIONS = {
    "normalize_country",
    "get_optimal_routing",
    "get_variant_for_provider",
    "upload_image_to_printify",
    "create_dynamic_mug_product",
    "send_printify_order",
}


def test_printify_service_imports_with_its_public_functions():
    mod = importlib.import_module("printify_service")
    missing = {n for n in PRINTIFY_PUBLIC_FUNCTIONS
               if not inspect.isfunction(getattr(mod, n, None))}
    assert not missing, f"printify_service lost: {sorted(missing)}"


# --- Plaque generation and fulfilment. ---

TROPHY_PIPELINE_FUNCTIONS = {
    "generate_and_publish_trophy",
    "fulfill_trophy_order",
}

GENERATE_TROPHY_FUNCTIONS = {
    "create_trophy_image",
    "generate_trophy_png",
    "generate_mug_preview_png",
    "impronta_campione_tazza",
    "resolve_level_and_style",
    "format_count",
    "format_count_full",
}


@pytest.mark.parametrize("module_name, expected", [
    ("trophy_pipeline", TROPHY_PIPELINE_FUNCTIONS),
    ("generate_trophy", GENERATE_TROPHY_FUNCTIONS),
])
def test_trophy_modules_import_with_their_functions(module_name, expected):
    mod = importlib.import_module(module_name)
    missing = {n for n in expected if not callable(getattr(mod, n, None))}
    assert not missing, f"{module_name} lost: {sorted(missing)}"


# --- Every route main.py registers today: trophy, claim, Stripe, analytics. ---

ROUTES_TODAY = {
    ("HEAD", "/"),
    ("GET", "/"),
    ("POST", "/api/ingest/run"),
    ("GET", "/api/posts"),
    ("GET", "/api/analytics/top10"),
    ("GET", "/api/analytics/insights"),
    ("GET", "/api/analytics/keywords"),
    ("POST", "/api/trophy/generate"),
    ("GET", "/api/trophy/preview"),
    ("GET", "/api/trophy/preview-mug"),
    ("POST", "/api/claim/initialize/{token}"),
    ("POST", "/api/checkout/create-session"),
    ("POST", "/api/webhooks/stripe"),
}


def _registered_routes(app):
    pairs = set()
    for route in app.routes:
        for method in getattr(route, "methods", None) or ():
            pairs.add((method, route.path))
    return pairs


def test_every_route_registered_today_is_still_registered():
    # Importing main does not run the startup hook, so the engine does not
    # start; only a TestClient or a server would trigger it.
    main = importlib.import_module("main")
    missing = ROUTES_TODAY - _registered_routes(main.app)
    assert not missing, f"routes no longer registered: {sorted(missing)}"
