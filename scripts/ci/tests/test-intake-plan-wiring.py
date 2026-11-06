#!/usr/bin/env python3
# requires: python3
"""The planner's client identity, and both halves of its one network path (CD18).

The broker calls the AI Gateway's data plane once per plan, as the client `planner`. Three
things have to agree for that call to work, and each is silent when it does not:

- Two copies of one value, each through its own namespace's store: the broker reads
  `agents/planner` through the namespaced `agents-secrets` (S9: agent-system reads the `agents`
  mount, never a ClusterSecretStore), the gateway reads `apps/planner` through the cluster-scoped
  `openbao-apps`. A namespaced `Password` generator cannot mint the same value twice, and a
  cross-namespace Secret read is not allowed, so two `ExternalSecret`s it is — and the two remote
  entries must hold the same key, which is why the runbook writes both.
- The gateway copy's Secret KEY is the client id. `apiKeyAuth` compares the bearer against
  each Secret *value* and forwards the Secret *key* on `x-ai-gateway-client-id`, so a key
  named `api-key` would attribute every planner token, in the access log and in the spend
  series, to a client nobody can name.
- Both CNP halves. Cilium `toEndpoints` selects pods, not Services: the broker's egress rule
  names the data-plane pods' own labels, and `envoy-data-plane` admits the broker pod on
  8080 and nothing else. Either half alone refuses the call, and an ingress half that widened
  to a namespace would whitelist every pod in it — so every source in that rule is checked, not
  just the one this feature adds.

This reads the source tree, not the rendered bundle: all three facts are legible before a
render, and the gate stays runnable without the host profile.
"""
import pathlib
import sys

try:
    import yaml
except ImportError:
    print("PyYAML is not installed")
    sys.exit(77)

ROOT = pathlib.Path(__file__).resolve().parents[3]
PLANNER_PATHS = {
    "broker": "infrastructure/base/room-broker/externalsecret-planner.yaml",
    "gateway": "infrastructure/base/envoy-ai-gateway/externalsecret-planner-key.yaml",
}
problems = []


def check(cond, msg):
    if not cond:
        problems.append(msg)


def docs(path):
    p = ROOT / path
    if not p.is_file():
        print(f"FAIL no such file: {path}")
        sys.exit(1)
    return [d for d in yaml.safe_load_all(p.read_text()) if d]


def load(path, name=None):
    """The first YAML document, or the one whose metadata.name is `name`."""
    found = docs(path)
    if name is not None:
        found = [d for d in found if (d.get("metadata") or {}).get("name") == name]
        if not found:
            print(f"FAIL no such document: {path} {name}")
            sys.exit(1)
    return found[0]


def ports(rule):
    return {int(p["port"]) for t in rule.get("toPorts") or [] for p in t.get("ports") or []}


def credential_names():
    pol = load("infrastructure/base/envoy-ai-gateway/security-policy.yaml")
    return [c["name"] for c in pol["spec"]["apiKeyAuth"]["credentialRefs"]]


def tree(top):
    return sorted(p for p in (ROOT / top).rglob("*") if p.is_file())


def listed(path, resource):
    """`resource` is in the kustomization beside `path`: an unlisted file is never applied."""
    return resource in (load(path) or {}).get("resources", [])


# --- A1: two namespaces, each through its own store, one value between them ---------------
# S9: the broker reads its own namespace's store (`agents-secrets`, the `agents` mount) and never
# the cluster-scoped store the gateway uses. The gateway's copy stays on `openbao-apps`: a
# namespaced Password generator cannot mint the same value twice, and nothing may read another
# namespace's Secret, so each side syncs its own copy from the entry its store can reach.
STORES = {
    PLANNER_PATHS["broker"]: {"kind": "SecretStore", "name": "agents-secrets"},
    PLANNER_PATHS["gateway"]: {"kind": "ClusterSecretStore", "name": "openbao-apps"},
}
for path, name, ns in [(PLANNER_PATHS["broker"], "room-broker-planner", "agent-system"),
                       (PLANNER_PATHS["gateway"], "ai-gateway-planner-key", "envoy-ai-gateway-system")]:
    es = load(path)
    check(es["spec"]["secretStoreRef"] == STORES[path],
          f"{path}: must read {STORES[path]['kind']} {STORES[path]['name']}")
    check(es["metadata"]["namespace"] == ns, f"{path}: namespace")
    # One key, one remote reference: a second entry would be a second value to rotate.
    check(len(es["spec"]["data"]) == 1, f"{path}: exactly one data entry")
    check(es["spec"]["data"][0]["remoteRef"]["key"] == "planner", f"{path}: remote key")
    check(es["spec"]["data"][0]["remoteRef"]["property"] == "apiKey", f"{path}: property")
    check(es["spec"]["target"]["name"] == name, f"{path}: target name")

# The gateway's Secret key IS the client id: `planner`, never `api-key`, or every log line and
# spend series attributes these tokens to a client nobody can name. The broker's own Secret key is
# arbitrary (it reads a file), so it keeps `api-key` and must not borrow the client id.
check(load(PLANNER_PATHS["gateway"])["spec"]["data"][0]["secretKey"] == "planner",  # pragma: allowlist secret
      "the gateway copy's Secret key must be planner")
check(load(PLANNER_PATHS["broker"])["spec"]["data"][0]["secretKey"] == "api-key",  # pragma: allowlist secret
      "the broker copy's Secret key is its file name: api-key")
names = credential_names()
check("ai-gateway-planner-key" in names and names[0] == "ai-gateway-api-keys",
      "the planner key is a credential of the one API-key policy")

# The broker mounts its own copy under its own name, and never reads another namespace's Secret.
# optional: an absent key runs the broker with the planner disabled instead of crashlooping;
# 0440 is the octal the API wants, readable through the pod's fsGroup alone.
app = load("infrastructure/base/room-broker/app.yaml")
mounts = [m for m in app["spec"]["extraVolumeMounts"] if m["name"] == "planner"]
check(mounts and mounts[0]["mountPath"] == "/etc/room-broker/planner" and mounts[0]["readOnly"],
      "the broker's mount")
volumes = [v for v in app["spec"]["extraVolumes"] if v["name"] == "planner"]
want_volume = {"secretName": "room-broker-planner", "optional": True, "defaultMode": 0o440}  # pragma: allowlist secret
check(volumes and volumes[0]["secret"] == want_volume,
      "the planner volume: its own Secret, optional, 0440")

# Both directions of the wiring are listed, or the object is written and never applied.
check(listed("infrastructure/base/room-broker/kustomization.yaml", "externalsecret-planner.yaml"),
      "room-broker's kustomization must list externalsecret-planner.yaml")
check(listed("infrastructure/base/envoy-ai-gateway/kustomization.yaml", "externalsecret-planner-key.yaml"),
      "envoy-ai-gateway's kustomization must list externalsecret-planner-key.yaml")

# No literal anywhere.
for p in tree("infrastructure"):
    text = p.read_text(errors="ignore")
    check("sk-planner" not in text and "plannerKey:" not in text, f"{p}: a literal key")

# --- A2: the two CNP halves, and the pairing they must keep ------------------------------
# The egress names the data-plane PODS, not a Service: a Cilium toEndpoints naming a Service or
# a Gateway label matches no endpoint and the call is dropped in silence. This selector is the
# one envoy-data-plane uses for its own endpointSelector.
dp_labels = {"app.kubernetes.io/managed-by": "envoy-gateway", "app.kubernetes.io/component": "proxy",
             "gateway.envoyproxy.io/owning-gateway-name": "ai-gateway",
             "gateway.envoyproxy.io/owning-gateway-namespace": "envoy-ai-gateway-system"}
broker_cnp = load("infrastructure/base/room-broker/network-policy.yaml", name="room-broker")
to_gw = [r for r in broker_cnp["spec"]["egress"]
         if any(e.get("matchLabels", {}) == {"io.kubernetes.pod.namespace": "envoy-gateway-system", **dp_labels}
                for e in r.get("toEndpoints", []))]
check(len(to_gw) == 1 and ports(to_gw[0]) == {8080},
      "the broker's egress selects the ai-gateway data-plane pods on 8080, and nothing else")

# gcp-0's overlay patches this file by index (`/spec/egress/5` is the ZITADEL rule), so the new
# rule goes after it: inserted earlier, the overlay edits the wrong rule and the build fails.
egress = broker_cnp["spec"]["egress"]
auth = [i for i, r in enumerate(egress)
        if any(f.get("matchName") == "auth.${public_domain_name}" for f in r.get("toFQDNs") or [])]
check(len(auth) == 1 and to_gw and egress.index(to_gw[0]) > auth[0],
      "the planner's egress rule must follow the ZITADEL one (gcp-0 pins that index)")

dp = load("infrastructure/base/envoy-gateway/network-policy.yaml", name="envoy-data-plane")
check(dp["spec"]["endpointSelector"]["matchLabels"] == dp_labels,
      "the data-plane policy is still the ai-gateway's alone")
planner = [r for r in dp["spec"]["ingress"] if r.get("fromEndpoints")
           and any(e["matchLabels"].get("app.kubernetes.io/name") == "room-broker"
                   for e in r["fromEndpoints"])]
check(len(planner) == 1 and ports(planner[0]) == {8080}, "one entry, 8080")
sources = planner[0]["fromEndpoints"] if planner else []
# Every source in the rule this PR edits, not only the one it adds: the rule's per-pod promise is
# what keeps a new consumer from becoming a namespace-wide hole, and a review that only checks the
# broker's entry would let the next one through.
for e in sources:
    check(set(e["matchLabels"]) == {"io.kubernetes.pod.namespace", "app.kubernetes.io/name"},
          f"a widened ingress source: {e}")
broker_entries = [e for e in sources if e["matchLabels"].get("app.kubernetes.io/name") == "room-broker"]
check(len(broker_entries) == 1, "one selector for the broker, not several")
for e in broker_entries:
    check(e["matchLabels"] == {"io.kubernetes.pod.namespace": "agent-system",
                               "app.kubernetes.io/name": "room-broker"}, "any other pod")

# The pairing rule the data-plane file states: every in-cluster ingress source also holds a key
# the API-key SecurityPolicy knows, or it is whitelisted and refused.
check("ai-gateway-planner-key" in credential_names(), "the broker's source is authenticated, not only allowed")

for problem in problems:
    print(f"  FAIL {problem}")
print(f"intake plan wiring: {len(problems)} problem(s)")
sys.exit(1 if problems else 0)
