#!/usr/bin/env python3
# requires: python3 kustomize
"""RunLore's knowledge base reaches triager runs through the broker's room tools (Maku EX11), on each
cloud as Flux applies it. Since R3 a run's only MCP server is the broker's :8090, so kb_search is
served there or not at all:

- every broker config copy sets roomTools.knowledge to RunLore's /mcp, serving kb_search to the
  triager role, and the copies agree;
- the HelmRelease's broker.roomTools.knowledge restates it (the postRenderer replaces the chart's
  config, so the values only render the chart's NetworkPolicy) and opens its egress to RunLore's pods;
- the broker's CiliumNetworkPolicy reaches RunLore's pods on the URL's port.

A drift would leave the broker serving no knowledge tool, to the wrong role, or one whose calls the
network refuses.
"""
import pathlib
import sys
from urllib.parse import urlparse

try:
    import yaml
except ImportError:
    print("SKIP: pyyaml not installed")
    sys.exit(77)

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts/ci"))
import room_broker_chart  # noqa: E402

URL = "http://runlore.runlore.svc.cluster.local:8080/mcp"
RUNLORE = {"io.kubernetes.pod.namespace": "runlore", "app.kubernetes.io/name": "runlore"}
CLOUDS = ("aws-0", "gcp-0")
CONFIG_KEYS = ("url", "tools", "roles", "timeout", "maxBytes")

checks = {}
knowledge = None
for copy in ("base", *CLOUDS):
    config = yaml.safe_load((ROOT / f"infrastructure/{copy}/room-broker/config.yaml").read_text())
    k = (config.get("roomTools") or {}).get("knowledge") or {}
    knowledge = knowledge if knowledge is not None else k
    checks[f"{copy} config: roomTools.knowledge.url is RunLore's /mcp"] = k.get("url") == URL
    checks[f"{copy} config: kb_search is forwarded"] = "kb_search" in k.get("tools", ["kb_search", "kb_get"])
    checks[f"{copy} config: the triager role may call it"] = "triager" in k.get("roles", ["triager"])
    checks[f"{copy} config: roomTools.knowledge is base's"] = k == knowledge

port = str(urlparse(URL).port)
for cloud in CLOUDS:
    try:
        docs = room_broker_chart.build(ROOT, f"infrastructure/{cloud}/room-broker")
    except room_broker_chart.Unavailable as e:
        print(f"SKIP: {e}")
        sys.exit(77)
    release = next(d for d in docs if d["kind"] == "HelmRelease" and d["metadata"]["name"] == "room-broker")
    values = ((release["spec"]["values"]["broker"].get("roomTools") or {}).get("knowledge")) or {}
    checks[f"{cloud}: the values' roomTools.knowledge is the config's"] = (
        {k: v for k, v in values.items() if k in CONFIG_KEYS} == knowledge)
    to = (values.get("networkPolicy") or {}).get("to") or []
    checks[f"{cloud}: the values open the chart's egress to RunLore's pods only"] = to == [{
        "namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": RUNLORE["io.kubernetes.pod.namespace"]}},
        "podSelector": {"matchLabels": {"app.kubernetes.io/name": RUNLORE["app.kubernetes.io/name"]}}}]
    cnp = next(d for d in docs if d["kind"] == "CiliumNetworkPolicy" and d["metadata"]["name"] == "room-broker")
    checks[f"{cloud}: the broker's CiliumNetworkPolicy reaches RunLore's pods on {port}"] = any(
        any(e.get("matchLabels") == RUNLORE for e in rule.get("toEndpoints", []))
        and any(p.get("port") == port for tp in rule.get("toPorts", []) for p in tp.get("ports", []))
        for rule in cnp["spec"].get("egress", []))

fails = 0
for desc, ok in checks.items():
    print(f"  {'ok  ' if ok else 'FAIL'} {desc}")
    fails += not ok
sys.exit(1 if fails else 0)
