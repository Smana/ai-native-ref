#!/usr/bin/env python3
"""Human touches per incident and the knowledge queue, from GitHub alone (the RunLore knowledge-base plan, K6).

  python3 scripts/ops/kb-measures.py --since YYYY-MM-DD [--until YYYY-MM-DD] [--fixtures DIR]

An incident is a RunLore stub: a `factory/proposed` issue of Smana/cloud-native-ref opened by the factory's
App whose body carries RunLore's origin line. The follow-up the monitor files when a fix did not hold
(title `RunLore: the fix in #<pr> did not hold (<alert>)`) carries `factory/proposed` too and is not an
incident; neither is a stub from another source. A human touch is a label event, or the merge, on the stub
or on what it published, whose actor is not a bot (type `Bot`, or a login ending `[bot]`). The knowledge
base's PRs are Smana/runlore-kb's, labelled `runlore`.

Reads GitHub through `gh api` with the caller's own `gh` authentication: no token is read or printed here.
With --fixtures DIR, reads DIR/{stubs,events,kb-prs}.json instead (events keyed by stub number).
Prints one Markdown table.
"""
import argparse
import json
import pathlib
import re
import statistics
import subprocess
import sys
from datetime import datetime, timedelta, timezone

HOST_REPO = "Smana/cloud-native-ref"
KB_REPO = "Smana/runlore-kb"
# RunLore's origin on a stub, read from a real one (cloud-native-ref #2657, the factory's `finding` text):
# the body opens "RunLore reported **<severity>** on `<service>` (alert `<name>`, ...". The follow-up's body
# opens "RunLore reports that the fix in #N did not hold", which this does not match.
ORIGIN = re.compile(r"^RunLore reported \*\*[a-z]+\*\* on `")
FOLLOW_UP = re.compile(r"^RunLore: the fix in #\d+ did not hold \(")
TOUCH_EVENTS = {"labeled", "unlabeled", "merged"}


def is_bot(actor):
    actor = actor or {}
    return actor.get("type") == "Bot" or str(actor.get("login", "")).endswith("[bot]")


def is_incident(stub):
    return bool(ORIGIN.match(stub.get("body") or "")) and not FOLLOW_UP.match(stub.get("title") or "") \
        and is_bot(stub.get("author"))


def parse(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00")) if ts else None


def measures(stubs, events, kb_prs, now=None, since=None, until=None):
    """With since and until, the KB counts are the window's (opened, merged and closed inside it) and the queue
    is every PR open at `until` whenever it was opened: a session that leaves the backlog open must read it.
    Without them every PR given counts."""
    now = now or datetime.now(timezone.utc)
    inside = (lambda ts: bool(ts) and since <= parse(ts) < until) if since and until else (lambda ts: bool(ts))
    by_incident = {}
    for s in stubs:
        if is_incident(s):
            n = s["number"]
            by_incident[f"#{n}"] = sum(1 for e in events.get(str(n), [])
                                       if e.get("event") in TOUCH_EVENTS and not is_bot(e.get("actor")))
    counts = sorted(by_incident.values())
    end = until or now
    opened = [p for p in kb_prs if inside(p.get("created_at"))]
    merged = [p for p in kb_prs if inside(p.get("merged_at"))]
    closed = [p for p in kb_prs if inside(p.get("closed_at")) and not p.get("merged_at")]
    open_ = [p for p in kb_prs if parse(p["created_at"]) < end and not (p.get("closed_at") and parse(p["closed_at"]) < end)
             and not (p.get("merged_at") and parse(p["merged_at"]) < end)]
    oldest = max(((end - parse(p["created_at"])).total_seconds() / 86400 for p in open_), default=None)
    return {
        "incidents": len(by_incident),
        "touches_by_incident": by_incident,
        "touches": {"median": statistics.median(counts), "max": counts[-1]} if counts else {"median": None, "max": None},
        "kb_opened": len(opened), "kb_merged": len(merged), "kb_closed": len(closed), "kb_open_end": len(open_),
        "oldest_open_days": None if oldest is None else round(oldest, 1),
    }


def render(m):
    rows = [("Incidents", m["incidents"]),
            ("Human touches per incident, median", m["touches"]["median"]),
            ("Human touches per incident, max", m["touches"]["max"]),
            ("KB PRs opened", m["kb_opened"]), ("KB PRs merged", m["kb_merged"]),
            ("KB PRs closed unmerged", m["kb_closed"]), ("KB PRs open at the end (any age)", m["kb_open_end"]),
            ("Oldest open KB PR (days)", m["oldest_open_days"])]
    out = ["| Measure | Value |", "|---|---|"]
    return "\n".join(out + [f"| {k} | {'-' if v is None else v} |" for k, v in rows])


def gh(path):
    """Every page of one `gh api` read (--paginate prints one JSON document per page)."""
    res = subprocess.run(["gh", "api", "--paginate", path], capture_output=True, text=True, check=False)
    if res.returncode != 0:
        sys.exit(f"gh api {path} failed: {res.stderr.strip()[:200]}")
    dec, text, i, items = json.JSONDecoder(), res.stdout, 0, []
    while i < len(text):
        if text[i].isspace():
            i += 1
            continue
        page, i = dec.raw_decode(text, i)
        items += page if isinstance(page, list) else [page]
    return items


def in_window(ts, since, until):
    d = parse(ts)
    return since <= d < until


def from_github(since, until):
    issues = [i for i in gh(f"repos/{HOST_REPO}/issues?labels=factory/proposed&state=all&since={since:%Y-%m-%d}T00:00:00Z&per_page=100")
              if "pull_request" not in i and in_window(i["created_at"], since, until)]
    stubs = [{"number": i["number"], "title": i["title"], "body": i["body"], "created_at": i["created_at"],
              "author": {"login": i["user"]["login"], "type": i["user"]["type"]}} for i in issues]
    events = {}
    for s in stubs:
        if not is_incident(s):
            continue
        n = s["number"]
        recs = [{"event": e["event"], "label": (e.get("label") or {}).get("name"), "actor": e.get("actor")}
                for e in gh(f"repos/{HOST_REPO}/issues/{n}/events?per_page=100") if e["event"] in TOUCH_EVENTS]
        # What it published: the fix issue the factory's "Published as #N" comment names, and the PR that
        # references it, whose merger is the merge actor.
        published = [int(m.group(1)) for c in gh(f"repos/{HOST_REPO}/issues/{n}/comments?per_page=100")
                     for m in [re.search(r"Published as #(\d+)", c["body"] or "")] if m]
        for fix in published:
            recs += [{"event": e["event"], "label": (e.get("label") or {}).get("name"), "actor": e.get("actor")}
                     for e in gh(f"repos/{HOST_REPO}/issues/{fix}/events?per_page=100") if e["event"] in TOUCH_EVENTS]
            for t in gh(f"repos/{HOST_REPO}/issues/{fix}/timeline?per_page=100"):
                src = ((t.get("source") or {}).get("issue") or {})
                if t.get("event") == "cross-referenced" and src.get("pull_request") \
                        and (src.get("repository") or {}).get("full_name") == HOST_REPO:
                    pr = gh(f"repos/{HOST_REPO}/pulls/{src['number']}")[0]
                    if pr.get("merged_by"):
                        recs.append({"event": "merged", "label": None, "actor": pr["merged_by"]})
        events[str(n)] = recs
    prs = [{"number": p["number"], "created_at": p["created_at"], "closed_at": p["closed_at"], "merged_at": p["merged_at"]}
           for p in gh(f"repos/{KB_REPO}/pulls?state=all&per_page=100")
           if any(l["name"] == "runlore" for l in p["labels"])]  # every PR: the queue is read at the end, not by creation
    return stubs, events, prs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--since", required=True, help="YYYY-MM-DD")
    ap.add_argument("--until", help="YYYY-MM-DD, default tomorrow")
    ap.add_argument("--fixtures", help="read DIR/{stubs,events,kb-prs}.json instead of GitHub")
    a = ap.parse_args(argv)
    since = datetime.strptime(a.since, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    until = (datetime.strptime(a.until, "%Y-%m-%d").replace(tzinfo=timezone.utc) if a.until
             else datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
             + timedelta(days=1))
    if a.fixtures:
        d = pathlib.Path(a.fixtures)
        stubs, events, prs = (json.loads((d / f"{n}.json").read_text()) for n in ("stubs", "events", "kb-prs"))
    else:
        stubs, events, prs = from_github(since, until)
    print(render(measures(stubs, events, prs, since=since, until=until)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
