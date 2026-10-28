#!/usr/bin/env python3
# requires: python3
"""RunLore's factory values (feature 14): the client calls POST /v1/tasks on the factory's API port, every
env name it reads comes from a Secret the envFrom list mounts, the list restates the host's three entries
first (lists replace, TW7), no templated notifier calls /intake/runlore (G4), and stage 2 (verification, soak, the old intake retired)."""
import pathlib
import sys

try:
    import yaml
except ImportError:
    print("PyYAML is not installed")
    sys.exit(77)

ROOT = pathlib.Path(__file__).resolve().parents[3]
DIR = ROOT / "observability/base/runlore-factory"
problems = []
cm = yaml.safe_load((DIR / "helm-values-configmap.yaml").read_text())
values = yaml.safe_load(cm["data"]["values.yaml"])
factory = values.get("config", {}).get("factory") or {}
env_from = values.get("envFrom") or []

if [e["secretRef"]["name"] for e in env_from[:3]] != ["runlore-credentials", "runlore-slack", "runlore-webhook"]:
    problems.append("envFrom must restate the host's three Secrets first, in order")
principal = next((e for e in env_from if e["secretRef"]["name"] == "runlore-factory-principal"), None)
if not principal or principal["secretRef"].get("optional") is not True:
    problems.append("envFrom mounts runlore-factory-principal, optional: a cluster without its key keeps RunLore up")
if "templated" in (values.get("config", {}).get("notify") or {}):
    problems.append("the templated notifier still calls /intake/runlore (G4)")
if factory.get("url") != "http://agent-factory.agent-system.svc.cluster.local:8082":
    problems.append(f"factory.url is the factory's API port 8082, got {factory.get('url')!r}")
if factory.get("token_url") != "${identity_provider_url}/oauth/v2/token":
    problems.append("factory.token_url is ZITADEL's token endpoint, substituted per cluster")
es = yaml.safe_load((DIR / "externalsecret-principal.yaml").read_text())
keys = set(es["spec"]["target"]["template"]["data"])
for k in ("client_id_env", "client_secret_env", "project_id_env"):
    if factory.get(k) not in keys:
        problems.append(f"factory.{k} {factory.get(k)!r} is not a key of runlore-factory-principal")
if (factory.get("webhook") or {}).get("secret_env") not in keys:
    problems.append("factory.webhook.secret_env is not a key of runlore-factory-principal")
for cluster in ("aws-0", "gcp-0"):
    ks = yaml.safe_load((ROOT / f"clusters/{cluster}-agent-platform/observability-runlore-factory.yaml").read_text())
    if not (ks["spec"].get("postBuild") or {}).get("substituteFrom"):
        problems.append(f"{cluster}: the runlore-factory Kustomization substitutes ${{identity_provider_url}}")
if factory.get("soak") != "30m" or not (factory.get("verify") or {}).get("alertmanager_url", "").startswith(
        "http://vmalertmanager-victoria-metrics-k8s-stack.observability.svc:9093"):
    problems.append("stage 2: factory.soak 30m and verify.alertmanager_url on the host's Alertmanager")
if any(e["secretRef"]["name"] == "runlore-factory-intake" for e in env_from) or (DIR / "externalsecret-intake.yaml").exists():
    problems.append("RA8: the intake bearer is retired")
fvalues = yaml.safe_load(yaml.safe_load((ROOT / "tooling/base/agent-factory/helm-values-configmap.yaml").read_text())["data"]["values.yaml"])
if "runlore" in fvalues["config"]:
    problems.append("RA8: the factory's runlore block is retired")
alert = fvalues["config"]["repositories"][0]["classes"].get("alert-rules") or {}
if (alert.get("monitor") or {}).get("verification") != {"within": "2h"}:
    problems.append("the seeded fix's class watches RunLore's verdict for 2h")
cnp = yaml.safe_load((ROOT / "tooling/base/agent-factory/network-policy.yaml").read_text())
rl = [r for r in cnp["spec"]["ingress"] if any((e.get("matchLabels") or {}).get("io.kubernetes.pod.namespace") == "runlore"
                                               for e in r.get("fromEndpoints", []))]
if [p["port"] for r in rl for p in r["toPorts"][0]["ports"]] != ["8082"]:
    problems.append("RunLore reaches the factory on 8082 only")
gp = yaml.safe_load((ROOT / "tooling/gcp-0/agent-factory/helm-values-sponsored.yaml").read_text())
gv = yaml.safe_load(gp["data"][next(iter(gp["data"]))])
ip = [p for p in gv["config"]["api"]["internalPrincipals"] if p["name"] == "runlore"]
if not ip or ip[0].get("verification") is not True:
    problems.append("gcp-0's runlore principal has verification: true")
if problems:
    print("\n".join(problems))
    sys.exit(1)
print("PASS: RunLore's factory values call the factory's API, with every credential mounted")
