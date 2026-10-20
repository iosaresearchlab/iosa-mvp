"""What a plaque carries and under which name it is archived (FIX-1a).

One source for the backend (/api/trophy/preview, which serves the archived
plaque) and for the job that renders plaques away from Render
(render_plaques.py, run by .github/workflows/plaques.yml). Both build the
arguments of generate_trophy.generate_trophy_png and the archive name here,
so the file the job uploads is the file the endpoint looks for.

Moved out of main.py unchanged (APP-2, CLAIM-2): the plaque of a closed v2
record carries vpi_max, views_max, days_charting, entered_on and left_on; its
archive key names the day the record left Most Popular; a v1 archive record
keeps its plaque.
"""
import hashlib
import re

from generate_trophy import METHOD_TEXT_V1, METHOD_TEXT_V2
from vpi_format import format_vpi_full

# Defaults of /api/trophy/preview for a request without a record behind it
# (an example plaque built from the query parameters).
DEFAULTS = {"author": "@TEARDOWNMAYHEM", "vpi": "+8.7x", "title": None,
            "e_act": "87.2K", "e_base": "10.0K", "gamma": "1.0x",
            "level_name": None, "recorded_date": None, "measured_date": None}


def safe_record_id(value) -> str:
    """Makes a record_id safe as a file name without changing claim tokens."""
    return re.sub(r"[^A-Za-z0-9_-]", "_", str(value or "preview"))[:120]


def claim_lookup(client, token):
    """The record a claim token names: posts first, then the v1 archive.

    The v1 records left posts on 25/09/2026 (02 section 3.6); claim tokens
    already sent must still resolve (08 T-20). claim_record_v1 returns the one
    archived row with that token and nothing else. Both answers carry .data.
    A record hidden on a removal request (OPTOUT-1) resolves to nothing.
    """
    res = (client.table("posts").select("*").eq("claim_token", token)
           .eq("hidden", False).execute())
    if (res and res.data) or not token:
        return res
    return client.rpc("claim_record_v1", {"p_token": token}).execute()


def plaque_state_v2(record):
    """CLAIM-2 (01/10/2026), v2 records only: "open" once the record has closed
    with a VPI; "charting" while it is in Most Popular (no plaque, no order);
    "no_vpi" when it closed without a computable baseline (no plaque)."""
    if record.get("status") != "CLOSED":
        return "charting"
    if record.get("vpi_max") is None:
        return "no_vpi"
    return "open"


def plaque_figures_v2(record):
    """APP-2: what the plaque of a closed v2 record carries - the highest VPI
    observed, the views, the days in Most Popular, first observed and left.
    None for anything else (a v1 archive record, an open record)."""
    if (record or {}).get("method_version") != "v2" or plaque_state_v2(record) != "open":
        return None
    return {"vpi": format_vpi_full(float(record['vpi_max'])),
            "views": str(record.get("views_max") if record.get("views_max") is not None
                         else record.get("engagement_score")),
            "days": record.get("days_charting"),
            "entered_on": str(record.get("entered_on"))[:10],
            "left_on": str(record.get("left_on"))[:10]}


def plaque_state(record):
    """v1 archive records all closed under v1 and keep their plaque."""
    if (record or {}).get("method_version") != "v2":
        return "open"
    return plaque_state_v2(record)


def build(post=None, claim_token=None, **params):
    """(refused, archive name, generate_trophy_png keyword arguments).

    `post` is the row claim_lookup found (None when there is none or the
    lookup failed); `params` are the query parameters of the endpoint, used
    only where the record says nothing. `refused` is None, "charting" or
    "no_vpi"; when it is not None there is no plaque to render.
    """
    p = {**DEFAULTS, **{k: v for k, v in params.items() if k in DEFAULTS}}
    author, vpi, e_act, e_base = p["author"], p["vpi"], p["e_act"], p["e_base"]
    resolved_title, resolved_level_name = p["title"], p["level_name"]
    resolved_record_id = claim_token
    req_date, req_misura, misura_date = p["recorded_date"], p["measured_date"], None
    plaque_v2 = refused = metodo = None

    if post:
        refused = plaque_state(post)
        plaque_v2 = plaque_figures_v2(post)
        metodo = METHOD_TEXT_V2 if plaque_v2 else METHOD_TEXT_V1
        author = post.get("author_handle") or author
        resolved_title = post.get("content_text") or resolved_title
        resolved_record_id = post.get("claim_token") or claim_token
        resolved_level_name = post.get("vpi_level_name") or resolved_level_name
        if post.get("vpi_ratio") is not None:
            raw_vpi = post.get("vpi_ratio")
            try:
                vpi = format_vpi_full(float(raw_vpi))
            except (ValueError, TypeError):
                vpi = str(raw_vpi)
                if not vpi.startswith("+"):
                    vpi = f"+{vpi}"
        if post.get("engagement_score") is not None:
            e_act = str(post.get("engagement_score"))
        if post.get("baseline_score") is not None:
            e_base = str(post.get("baseline_score"))
        if post.get("created_at"):
            req_date = str(post.get("created_at"))[:10]
        # The plaque carries two dates: when the video came out and when we
        # measured it. The count is frozen at the second.
        if post.get("detected_at"):
            misura_date = str(post.get("detected_at"))[:10]

    if refused in ("charting", "no_vpi"):
        return refused, None, None
    refused = None
    if plaque_v2:
        vpi, e_act = plaque_v2["vpi"], plaque_v2["views"]
        req_date, misura_date = plaque_v2["entered_on"], plaque_v2["left_on"]
    if not resolved_title:
        resolved_title = "Viral Content Title"

    if resolved_record_id:
        cache_key = safe_record_id(resolved_record_id)
    else:
        # Without a claim token the plaque is an example: the key comes from
        # the parameters, or two different examples would share one file.
        impronta = hashlib.sha1("|".join([
            str(author), str(vpi), str(resolved_title), str(e_act),
            str(e_base), str(p["gamma"]), str(resolved_level_name),
            str(req_date), str(req_misura),
        ]).encode("utf-8")).hexdigest()[:12]
        cache_key = safe_record_id(f"preview_{impronta}")
    # The archive key of a v2 plaque is tied to the closed state: it names
    # the day the record left Most Popular, so no plaque rendered under
    # another state (or before APP-2) is ever served for it.
    file_key = f"{cache_key}_closed_{plaque_v2['left_on']}" if plaque_v2 else cache_key
    kwargs = dict(
        record_id=cache_key,
        file_id=file_key,
        days_charting=(plaque_v2 or {}).get("days"),
        entered_on=(plaque_v2 or {}).get("entered_on"),
        left_on=(plaque_v2 or {}).get("left_on"),
        method_text=metodo,
        vpi_score=vpi,
        user_handle=author,
        content_title=resolved_title,
        e_act=e_act,
        e_base=e_base,
        recorded_date=req_date or "2026-08-20",
        measured_date=misura_date or req_misura or req_date or "2026-08-20",
        level_name=resolved_level_name,
    )
    return None, f"{file_key}.png", kwargs


def mug_archive_name() -> str:
    """The one mug sample in the archive: its name follows the sample image,
    so a new sample gets a new name (frontend/src/lib/plaque.ts names it)."""
    from generate_trophy import impronta_campione_tazza
    return f"mug_{impronta_campione_tazza()}.png"
