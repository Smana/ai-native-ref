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
from urllib.parse import urlparse

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


def sponsored_in(node, parent=None):
    """True when an `api` mapping holds `sponsored`, or a JSON patch path names api/sponsored, at any depth,
    through ConfigMap data and kustomize patch strings (themselves YAML) alike."""
    if isinstance(node, str):
        if "api/sponsored" in node:
            return True
        try:
            inner = yaml.safe_load(node)
        except yaml.YAMLError:
            return False
        return isinstance(inner, (dict, list)) and sponsored_in(inner, parent)
    if isinstance(node, dict):
        if parent == "api" and "sponsored" in node:
            return True
        return any(sponsored_in(v, k) for k, v in node.items())
    if isinstance(node, list):
        return any(sponsored_in(v, parent) for v in node)
    return False


# Every values source that reaches the factory, found by glob: a values ConfigMap, a HelmRelease's inline
# values, a kustomize patch in any overlay. The Slack App's own directories hold none.
for path in sorted(ROOT.glob("tooling/*/agent-factory/**/*.yaml")):
    rel = path.relative_to(ROOT)
    if any(str(rel).startswith(d) for d in SLACK_DIRS):
        continue
    if sponsored_in(load(str(rel))):
        problems.append(f"{rel} declares api.sponsored (D4)")

# The App appends /mcp itself: a brokerURL with a path would call /mcp/mcp.
app_cfg = yaml.safe_load((ROOT / "tooling/base/agent-factory/slack-app/config.yaml").read_text())
if urlparse(app_cfg["brokerURL"]).path not in ("", "/"):
    problems.append(f"slack-app config.yaml brokerURL {app_cfg['brokerURL']!r} has a path: the App appends /mcp")

# gen-webhook-egress.py refuses a named targetPort for a cluster subscriber: every port of the App's Service
# has a numeric targetPort equal to its port.
for doc in load("tooling/base/agent-factory/slack-app/service.yaml"):
    if doc.get("kind") != "Service":
        continue
    for port in doc["spec"]["ports"]:
        if port.get("targetPort") != port["port"]:
            problems.append(f"slack-app service.yaml: port {port['name']} has targetPort {port.get('targetPort')!r}, "
                            f"want the number {port['port']}")

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
