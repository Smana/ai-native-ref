#!/usr/bin/env python3
# requires: python3
"""The room broker's Room verbs are the ones its code calls: the web view's "new room" and a
fork create a Room (agent-platform internal/humanapi rooms.go and fork.go), so without create
both answer an unlogged 503. It never deletes one, so it gets no delete. Since Maku v0.39.0 the
human API reads coordination parents live (Tasks, and the day ledgers' ConfigMaps) whenever
coordination is not off: exactly get and list, never watch and never a write, as Maku's own
chart grants them."""
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
fails = 0
if verbs != want:
    print(f"the broker's verbs on rooms are {sorted(verbs)}, want {sorted(want)}", file=sys.stderr)
    fails += 1


def verbs_on(group, resource):
    return {v for d in roles for r in d["rules"] if group in r.get("apiGroups", [])
            and resource in r.get("resources", []) for v in r["verbs"]}


for group, resource in (("maku.ogenki.io", "tasks"), ("", "configmaps")):
    got = verbs_on(group, resource)
    if got != {"get", "list"}:
        print(f"the broker's verbs on {resource} are {sorted(got)}, want ['get', 'list'] (read-only)",
              file=sys.stderr)
        fails += 1
if fails:
    sys.exit(1)
print("PASS")
