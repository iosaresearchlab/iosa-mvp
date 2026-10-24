"""SOC-W2 (24/10/2026): the baseline sample of a record, from what the database already holds.

GET /api/posts/{id}/baseline-sample (main.py). Read-only, and never a YouTube API call.

What is stored with a record whose baseline_rule is standard: the ids of the videos of its
sample, in the order of the window (posts.baseline_video_ids, T-05), and their number
(baseline_samples). Not stored anywhere: their titles and the view counts read at baseline time
(the views were read with videos.list, used for the median and not kept). Those two fields are
answered as null and named in "not_stored"; storing them would be a change to the ingestion,
which this task does not make. A sample video's publication date comes from the channel's
cached inventory (channel_inventory.items: {video_id: [published epoch, format]}) when the
inventory still holds it.

in_most_popular, per sample video, from our daily readings (complete censuses only):
- true: the video is in the snapshot window (trend_snapshot), or has a v2 record (posts): every
  video of a measured format first observed in Most Popular after the first complete census
  has one (a video already present in that first census is the reference, not an entry, and
  has none);
- false: the video was published after the first complete census, no complete census is
  missing since, and it is in neither;
- unknown: otherwise (published before our first census, or its publication date unknown, or a
  census missing since).
The days consulted are returned as window_from / window_to. "Not in Most Popular" means "not
in any of our daily readings": a video can enter and leave a chart between two readings.
The archived snapshot files (Storage, trend_snapshot/<day>.jsonl.gz) are not read on a
request: for the measured format they hold no video that is not in posts, except those of the
first census.
"""
from datetime import date, datetime, timezone

NOT_STORED = ["title", "views_at_baseline"]


class NotAvailable(Exception):
    """The record is missing, hidden, not v2, or has no standard baseline."""


def _day(v):
    return date.fromisoformat(str(v)[:10]) if v else None


def census_days(client):
    """The days with a complete census, ascending."""
    res = (client.table("ingest_run").select("day,census_complete")
           .eq("census_complete", True).order("day").execute())
    return sorted({_day(r["day"]) for r in res.data or []})


def classify(published, found, complete, first_census, last_census):
    """true / false / unknown for one sample video (see the module docstring)."""
    if found:
        return True
    if published is None or first_census is None:
        return "unknown"
    pub_day = published.date() if isinstance(published, datetime) else published
    if pub_day <= first_census:          # could be in the first census, which makes no record
        return "unknown"
    expected = (last_census - pub_day).days + 1
    seen = sum(1 for d in complete if pub_day <= d <= last_census)
    return False if seen == expected else "unknown"


def sample(client, record_id):
    rec = (client.table("posts")
           .select("id,external_post_id,channel_id,format,method_version,hidden,baseline_rule,"
                   "baseline_samples,baseline_video_ids,baseline_computed_at")
           .eq("id", record_id).limit(1).execute().data or [None])[0]
    if not rec or rec.get("method_version") != "v2" or rec.get("hidden"):
        raise NotAvailable("no such record")
    if rec.get("baseline_rule") != "standard":
        raise NotAvailable(f"no baseline sample: baseline_rule is {rec.get('baseline_rule')}")
    ids = list(rec.get("baseline_video_ids") or [])

    inv = (client.table("channel_inventory").select("items")
           .eq("channel_id", rec["channel_id"]).limit(1).execute().data or [{}])[0].get("items") or {}
    recorded = {}
    snap = {}
    if ids:
        for r in (client.table("posts").select("external_post_id,entered_on")
                  .eq("method_version", "v2").in_("external_post_id", ids).execute().data or []):
            recorded[r["external_post_id"]] = _day(r["entered_on"])
        for r in (client.table("trend_snapshot").select("video_id,day,published_at")
                  .in_("video_id", ids).execute().data or []):
            d = _day(r["day"])
            prev = snap.get(r["video_id"])
            if prev is None or d < prev[0]:
                snap[r["video_id"]] = (d, r.get("published_at"))

    complete = census_days(client)
    first, last = (complete[0], complete[-1]) if complete else (None, None)
    samples = []
    for vid in ids:
        item = inv.get(vid) if isinstance(inv, dict) else None
        published = None
        if item:
            published = datetime.fromtimestamp(int(item[0]), tz=timezone.utc)
        elif vid in snap and snap[vid][1]:
            published = datetime.fromisoformat(str(snap[vid][1]).replace("Z", "+00:00"))
        seen = [d for d in (recorded.get(vid), snap.get(vid, (None,))[0]) if d]
        samples.append({
            "video_id": vid,
            "title": None,
            "published_at": published.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if published else None,
            "views_at_baseline": None,
            "in_most_popular": classify(published, bool(seen), complete, first, last),
            "first_observed": min(seen).isoformat() if seen else None,
        })
    return {
        "id": rec["id"],
        "video_id": rec["external_post_id"],
        "channel_id": rec["channel_id"],
        "format": rec.get("format"),
        "baseline_rule": rec["baseline_rule"],
        "n_baseline": rec.get("baseline_samples"),
        "baseline_computed_at": rec.get("baseline_computed_at"),
        "window_from": first.isoformat() if first else None,
        "window_to": last.isoformat() if last else None,
        "consulted": "complete daily readings of YouTube's Most Popular category charts: the snapshot "
                     "window (trend_snapshot) and the v2 records (posts); no YouTube API call",
        "not_stored": NOT_STORED,
        "samples": samples,
    }
