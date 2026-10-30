#!/usr/bin/env python3
# requires: python3
"""gen-webhook-egress: one egress rule per subscriber, by its network (factory interfaces F6, R21)."""
import contextlib
import importlib.util
import io
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("gen", ROOT / "scripts/ci/gen-webhook-egress.py")
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)

failures = []


def check(name, cond):
    if not cond:
        failures.append(name)


none = gen.render({})
check("no subscriber, an egress-only policy that allows nothing", none["spec"]["egress"] == [{}] and "ingress" not in none["spec"])

cfg = {"webhooks": [
    {"name": "slack-app", "network": "cluster", "url": "http://factory-slack-app.agent-system.svc.cluster.local:8081/webhooks"},
    {"name": "ci-mirror", "network": "internet", "url": "https://hooks.example.io/factory"},
    {"name": "own", "network": "internet", "url": "https://hooks.${public_domain_name}/factory"},
    {"name": "alt-port", "network": "internet", "url": "https://hooks.example.io:8443/factory"},
]}
rules = gen.render(cfg)["spec"]["egress"]
check("cluster: toEndpoints by namespace and name, its port",
      rules[0] == {"toEndpoints": [{"matchLabels": {"io.kubernetes.pod.namespace": "agent-system",
                                                    "app.kubernetes.io/name": "factory-slack-app"}}],
                   "toPorts": [{"ports": [{"port": "8081", "protocol": "TCP"}]}]})
check("internet: toFQDNs matchName on 443",
      rules[1] == {"toFQDNs": [{"matchName": "hooks.example.io"}], "toPorts": [{"ports": [{"port": "443", "protocol": "TCP"}]}]})
check("internet: a Flux ${var} label is kept for Flux to substitute",
      rules[2]["toFQDNs"] == [{"matchName": "hooks.${public_domain_name}"}])
check("internet: an explicit port is the rule's port",
      rules[3]["toPorts"] == [{"ports": [{"port": "8443", "protocol": "TCP"}]}])

for bad in ({"network": "internet", "url": "https://10.0.0.1/x"},
            {"network": "internet", "url": "https://[::1]/x"},
            {"network": "internet", "url": "https://localhost/x"},
            {"network": "internet", "url": "https://x.agent-system.svc.cluster.local/x"},
            {"network": "internet", "url": "https://x.svc/x"},
            {"network": "internet", "url": "https://x.corp.internal/x"},
            {"network": "internet", "url": "https://x.local/x"},
            {"network": "internet", "url": "https://hooks/x"},
            {"network": "internet", "url": "https://hooks.localdomain/x"},
            {"network": "internet", "url": "http://hooks.example.io/x"},
            {"network": "cluster", "url": "http://hooks.example.io/x"},
            {"network": "cluster", "url": "http://x.agent-system.svc.cluster.local/x"},
            {"network": "mars", "url": "https://hooks.example.io/x"}):
    try:
        gen.render({"webhooks": [dict(bad, name="x")]})
        failures.append(f"accepted {bad}")
    except gen.ConfigError:
        pass

try:
    gen.render({"webhooks": [{"name": "a", "network": "internet", "url": "https://h.example.io/x"},
                             {"name": "a", "network": "internet", "url": "https://h.example.io/y"}]})
    failures.append("accepted a duplicate name")
except gen.ConfigError:
    pass

base = {"webhooks": []}
check("an overlay with base's subscribers needs no patch", gen.overlay_patch(base, {"webhooks": []}) is None)
check("an overlay without a webhooks key needs no patch", gen.overlay_patch(base, {}) is None)
patch = gen.overlay_patch(base, cfg)
check("an overlay's own subscribers patch base's policy by name, spec replaced",
      patch["kind"] == "CiliumNetworkPolicy" and patch["metadata"]["name"] == "room-broker-webhooks"
      and patch["metadata"]["namespace"] == "agent-system"
      and patch["spec"] == gen.render(cfg)["spec"])

# Ruling 2: host labels, the one allowed ${var}, port 0, the name.
def refused(sub):
    try:
        gen.render({"webhooks": [sub]})
        return False
    except gen.ConfigError:
        return True


def net(url, name="x"):
    return {"name": name, "network": "internet", "url": url}


for url in ("https://ho_ok.example.io/x", "https://*.example.io/x", "https://Hooks!.example.io/x",
            "https://hooks.${private_domain_name}/x", "https://hooks.${other}/x", "https://ho${public_domain_name}.io/x",
            "https://hooks.example.io:0/x"):
    check(f"refused {url}", refused(net(url)))
for name in (None, "", "Bad_Name", "-a", "a-", "x" * 64, "a\n"):
    check(f"refused name {name!r}", refused(dict(net("https://hooks.example.io/x"), name=name)))
check("a one-letter name is a DNS label", not refused(net("https://hooks.example.io/x", name="a")))
check("a nameless subscriber is a ConfigError, not a KeyError", refused({"network": "internet", "url": "https://hooks.example.io/x"}))

# Ruling 1: a cluster subscriber's Service port equals its targetPort, or has none.
sub = {"name": "s", "network": "cluster", "url": "http://svc.ns.svc.cluster.local:8081/webhooks"}


def svc(*ports, selector=None):
    return {"selector": selector or {"app.kubernetes.io/name": "svc"}, "ports": list(ports)}


check("targetPort equal is accepted", gen.service_error(sub, svc({"port": 8081, "targetPort": 8081})) is None)
check("targetPort absent is accepted", gen.service_error(sub, svc({"port": 8081})) is None)
err = gen.service_error(sub, svc({"port": 8081, "targetPort": 9090}))
check("targetPort different is refused, naming the Service and both ports",
      err and "ns/svc" in err and "8081" in err and "9090" in err)
err = gen.service_error(sub, svc({"port": 8081, "targetPort": "http"}))
check("targetPort named is refused", err and "ns/svc" in err and "8081" in err and "http" in err)
check("a port the Service does not expose is refused", gen.service_error(sub, svc({"port": 80})) is not None)
check("a wrong selector is refused", gen.service_error(sub, svc({"port": 8081}, selector={"app": "svc"})) is not None)

# G7: RunLore's Service is the host chart's (HOST-CONTRACT H8): runlore/runlore on 8080, its backend 8080.
host = gen.HOST_SERVICES[("runlore", "runlore")]
rl = {"name": "runlore", "network": "cluster", "url": "http://runlore.runlore.svc.cluster.local:8080/factory/webhook"}
check("RunLore's host Service carries its rule", gen.service_error(rl, host) is None)
check("RunLore's rule is its namespace and name on 8080",
      gen.rule(rl) == {"toEndpoints": [{"matchLabels": {"io.kubernetes.pod.namespace": "runlore", "app.kubernetes.io/name": "runlore"}}],
                       "toPorts": [{"ports": [{"port": "8080", "protocol": "TCP"}]}]})
check("a host Service is only the contract's", set(gen.HOST_SERVICES) == {("runlore", "runlore")})

# Ruling 4: an overlay that replaces base's config and names no webhooks has no subscribers.
with_subs = {"webhooks": cfg["webhooks"][:2]}
patch = gen.overlay_patch(with_subs, {})
check("an overlay without webhooks, base with some, is patched to nothing allowed",
      patch is not None and patch["spec"]["egress"] == [{}])
check("an overlay with webhooks: [] likewise", gen.overlay_patch(with_subs, {"webhooks": []}) == patch)


# Ruling 5: main()'s branches, on a temp tree.
def tree(root, base_webhooks=None, overlay=None, listed=False, base_listed=True, patch_file=None, services=None):
    import yaml
    b = root / "infrastructure/base/room-broker"
    o = root / "infrastructure/gcp-0/room-broker"
    b.mkdir(parents=True), o.mkdir(parents=True)
    (b / "config.yaml").write_text(yaml.safe_dump({"publicURL": "x", **({"webhooks": base_webhooks} if base_webhooks else {})}))
    (b / "kustomization.yaml").write_text(yaml.safe_dump(
        {"resources": ["network-policy.yaml"] + (["network-policy-webhooks.yaml"] if base_listed else [])}))
    if overlay is not None:
        (o / "config.yaml").write_text(yaml.safe_dump(overlay))
    (o / "kustomization.yaml").write_text(yaml.safe_dump(
        {"resources": ["../../base/room-broker"], "patches": [{"path": gen.PATCH}] if listed else []}))
    if patch_file is not None:
        (o / gen.PATCH).write_text(patch_file)
    for i, d in enumerate(services or []):
        (root / f"svc{i}.yaml").write_text(yaml.safe_dump(d))


def run(root, *args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = gen.main(["x", *args, str(root)])
    return rc, out.getvalue() + err.getvalue()


def service(ports, ns="ns", name="svc", selector=None):
    return {"kind": "Service", "metadata": {"name": name, "namespace": ns},
            "spec": {"selector": selector or {"app.kubernetes.io/name": name}, "ports": ports}}


try:
    import yaml  # noqa: F401
    have_yaml = True
except ImportError:
    have_yaml = False
    print("note: PyYAML missing, main() branches skipped", file=sys.stderr)
if have_yaml:
    ci = {"name": "ci", "network": "internet", "url": "https://hooks.example.io/x",
          "events": ["room.created"], "secretFile": "/s", "repositories": ["a/b"]}
    for label, kw, want, text in (
        ("main: no subscriber anywhere, clean", dict(overlay={"publicURL": "x"}), 0, "its config's rendering"),
        ("main: the base policy is not listed", dict(base_listed=False), 1, "must list network-policy-webhooks.yaml"),
        ("main: an overlay needing a patch it has not got is written, then unlisted fails",
         dict(overlay={"webhooks": [ci]}), 1, "must list `- path: network-policy-webhooks-patch.yaml`"),
        ("main: a stale patch is detected", dict(overlay={"publicURL": "x"}, patch_file="x: 1\n"), 1, "needs no patch"),
        ("main: a patch listed and not needed is detected", dict(overlay={"publicURL": "x"}, listed=True), 1, "does not need"),
        ("main: a cluster subscriber with no Service", dict(overlay={"webhooks": [dict(sub, url=sub["url"])]}), 1, "no Service ns/svc"),
        ("main: a Service whose targetPort differs",
         dict(overlay={"webhooks": [sub]}, services=[service([{"port": 8081, "targetPort": 9090}])]), 1, "9090"),
    ):
        with tempfile.TemporaryDirectory() as t:
            root = pathlib.Path(t)
            tree(root, **kw)
            # The committed base policy is the rendering of base's config, as --write leaves it.
            if "base_listed" not in kw or kw["base_listed"]:
                run(root, "--write")
            rc, out = run(root)
            check(f"{label}: exit {want}", rc == want)
            check(f"{label}: says {text!r}", text in out)

    with tempfile.TemporaryDirectory() as t:
        root = pathlib.Path(t)
        tree(root, overlay={"webhooks": [ci]})
        rc, _ = run(root, "--write")
        written = root / "infrastructure/gcp-0/room-broker" / gen.PATCH
        check("main --write: the overlay's patch is written, exit 1 until listed", rc == 1 and written.exists())
        (root / "infrastructure/gcp-0/room-broker/kustomization.yaml").write_text(
            yaml.safe_dump({"resources": ["../../base/room-broker"], "patches": [{"path": gen.PATCH}]}))
        rc, out = run(root)
        check("main: once listed, the overlay's patch passes", rc == 0)
        written.write_text(written.read_text() + "# drift\n")
        rc, out = run(root)
        check("main: a patch edited by hand fails with a diff", rc == 1 and "(committed)" in out)

    with tempfile.TemporaryDirectory() as t:
        root = pathlib.Path(t)
        tree(root, base_webhooks=[sub], overlay={"publicURL": "x"}, services=[service([{"port": 8081}])])
        rc, _ = run(root, "--write")
        check("main: base subscribers, a replacing overlay with none is patched to nothing", rc == 1
              and "egress:\n  - {}" in (root / "infrastructure/gcp-0/room-broker" / gen.PATCH).read_text())
        rc, _ = run(root)
        check("main: base subscriber on a good Service, and the patch not listed, still fails once", rc == 1)

print("\n".join(failures) or ("PASS" if have_yaml else "SKIP: PyYAML missing"))
sys.exit(1 if failures else (0 if have_yaml else 77))  # 77: run-tests.sh shows SKIP
