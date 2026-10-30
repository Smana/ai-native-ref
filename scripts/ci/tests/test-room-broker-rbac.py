#!/usr/bin/env python3
# requires: python3
"""The room broker's Room verbs are the ones its code calls: the web view's "new room" and a
fork create a Room (agent-platform internal/humanapi rooms.go and fork.go), so without create
both answer an unlogged 503. It never deletes one, so it gets no delete."""
import pathlib
import sys

try:
    import yaml
except ImportError:
    print("SKIP: pyyaml not installed")
    sys.exit(77)

ROOT = pathlib.Path(__file__).resolve().parents[3]
RBAC = ROOT / "infrastructure/base/room-broker/rbac.yaml"
docs = [d for d in yaml.safe_load_all(RBAC.read_text()) if d]
roles = [d for d in docs if d["kind"] == "Role" and d["metadata"]["namespace"] == "agent-system"]
verbs = {v for d in roles for r in d["rules"] if "maku.ogenki.io" in r.get("apiGroups", [])
         and "rooms" in r.get("resources", []) for v in r["verbs"]}
want = {"get", "list", "watch", "create", "update"}
if verbs != want:
    print(f"the broker's verbs on rooms are {sorted(verbs)}, want {sorted(want)}", file=sys.stderr)
    sys.exit(1)
print("PASS")
