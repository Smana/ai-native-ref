#!/usr/bin/env python3
# requires: python3
"""Factory interfaces part 2 ships every switch off (D4, R30, L3', L8).

On the real tree: no cluster applies the Slack App's manifests; no broker config declares a webhook
or a sponsored human MCP client, and no factory values declare a sponsored API client; the factory's
public route is still the one POST /v1/runs, and the Slack App's is the one POST /slack/events.
A switch-on lands in a gcp-0 session's copy (runbook 18), never here.
"""
import pathlib
import sys

try:
    import yaml
except ImportError:
    print("PyYAML is not installed")
    sys.exit(77)

ROOT = pathlib.Path(__file__).resolve().parents[3]
SLACK_DIRS = ("tooling/base/agent-factory/slack-app", "tooling/gcp-0/agent-factory/slack-app")
problems = []


def load(rel):
    return [d for d in yaml.safe_load_all((ROOT / rel).read_text()) if d]


# 1. Nothing applies the Slack App (R30, L3').
for path in sorted((ROOT / "clusters").rglob("*")):
    if path.is_file():
        text = path.read_text(errors="replace")
        for d in SLACK_DIRS:
            if d in text:
                problems.append(f"{path.relative_to(ROOT)} names {d}: the Slack App is applied by a gcp-0 session only")
for path in sorted(ROOT.rglob("kustomization.yaml")):
    rel = path.relative_to(ROOT)
    if rel.parts[0] in (".host", ".composite", "node_modules"):
        continue
    if str(rel.parent) in SLACK_DIRS:  # the App's own directories: the overlay lists the base
        continue
    for doc in load(str(rel)):
        for res in (doc.get("resources") or []) + (doc.get("components") or []):
            # a directory named slack-app (the host's alertmanager-slack-app file is another thing)
            if "slack-app" in pathlib.PurePosixPath(str(res)).parts:
                problems.append(f"{rel} lists {res}: the Slack App is not wired")

# 2. The broker declares no webhook and no sponsored human MCP client; the factory no sponsored API client.
for cfg in sorted(ROOT.glob("infrastructure/*/room-broker/config.yaml")):
    rel = cfg.relative_to(ROOT)
    for doc in load(str(rel)):
        if "webhooks" in doc:
            problems.append(f"{rel} declares webhooks (D4)")
        if "sponsored" in ((doc.get("human") or {}).get("mcp") or {}):
            problems.append(f"{rel} declares human.mcp.sponsored (D4)")
for rel in ("tooling/base/agent-factory/helm-values-configmap.yaml",
            "tooling/gcp-0/agent-factory/helm-values-suspend.yaml"):
    for doc in load(rel):
        if doc.get("kind") != "ConfigMap":
            continue
        for body in doc["data"].values():
            values = yaml.safe_load(body) or {}
            if "sponsored" in ((values.get("config") or {}).get("api") or {}):
                problems.append(f"{rel} declares config.api.sponsored (D4)")


# 3 and 4. One route, one match, exact path, POST.
def one_match(rel, path):
    routes = [d for d in load(rel) if d.get("kind") == "HTTPRoute"]
    if len(routes) != 1:
        problems.append(f"{rel}: expected one HTTPRoute, found {len(routes)}")
        return
    rules = routes[0]["spec"]["rules"]
    matches = rules[0]["matches"] if len(rules) == 1 else []
    if len(rules) != 1 or len(matches) != 1:
        problems.append(f"{rel}: expected one rule with one match")
        return
    m = matches[0]
    if m.get("path") != {"type": "Exact", "value": path} or m.get("method") != "POST":
        problems.append(f"{rel}: the match must be POST Exact {path}, got {m}")


one_match("tooling/base/agent-factory/httproute.yaml", "/v1/runs")
slack_route = "tooling/base/agent-factory/slack-app/httproute.yaml"
if (ROOT / slack_route).exists():
    one_match(slack_route, "/slack/events")
else:
    problems.append(f"{slack_route} does not exist")

if problems:
    print("\n".join(problems))
    sys.exit(1)
print("PASS: the Slack App is unwired, no webhook or sponsored client is declared, both routes are one POST")
