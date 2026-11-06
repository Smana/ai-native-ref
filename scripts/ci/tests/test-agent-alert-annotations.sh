#!/usr/bin/env bash
# requires: python3
#
# External review M9: every alert the agent platform ships names its runbook and its
# dashboard, as the karpenter and openbao VMRules do. The real tree, not fixtures: SP2's
# and SP3's alerts land in the same directory and are held to the same rule.
#
# A `runbook_url` on this repository's own `main` also names a file here: where this tree holds
# `docs/runbooks/`, that file must exist, or the alert's one link 404s and nobody notices until
# the night it is read (the Slack decision alerts point at runbook 22 §7 this way). The composite
# run has the host's `docs/` but not this repository's, so it says so rather than passing
# silently.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
python3 -c 'import yaml' 2>/dev/null || { echo "SKIP: pyyaml not installed"; exit 77; }
ROOT="$ROOT" python3 - <<'PY'
import glob, os, re, sys, yaml

root = os.environ["ROOT"]
OWN = re.compile(r"^https://github\.com/Smana/ai-native-ref/blob/main/([^#?]+)")
holds_docs = os.path.isdir(os.path.join(root, "docs/runbooks/agent-factory"))
missing = []
broken = []
unchecked = []
for path in sorted(glob.glob(os.path.join(root, "observability/base/agent-platform/vmrule*.yaml"))):
    for doc in yaml.safe_load_all(open(path)):
        if not doc or doc.get("kind") != "VMRule":
            continue
        for group in doc["spec"]["groups"]:
            for rule in group.get("rules") or []:
                if "alert" not in rule:
                    continue
                annotations = rule.get("annotations") or {}
                for key in ("runbook_url", "dashboard"):
                    if not annotations.get(key):
                        missing.append(f"{os.path.relpath(path, root)}: {rule['alert']} has no {key}")
                own = OWN.match(annotations.get("runbook_url") or "")
                if not own:
                    continue
                if not holds_docs:
                    unchecked.append(rule["alert"])
                elif not os.path.exists(os.path.join(root, own.group(1))):
                    broken.append(
                        f"{os.path.relpath(path, root)}: {rule['alert']}'s runbook_url names "
                        f"{own.group(1)}, which is not in this tree")
if missing or broken:
    print("\n".join(missing + broken), file=sys.stderr)
    sys.exit(1)
if unchecked:
    print(f"note: {len(unchecked)} runbook_url path(s) not checked: docs/runbooks/ is not in this tree")
print("PASS")
PY
