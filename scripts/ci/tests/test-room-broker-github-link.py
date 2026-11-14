#!/usr/bin/env python3
# requires: python3 kustomize helm
"""The GitHub account link beside the ZITADEL reader (Maku docs/github-link.md, v4 step 5 ANR
follow-ups 1 and 2), on each cloud as Flux applies it:

- every broker config copy says human.preset zitadel and the same human.githubLink, whose two files
  sit in one directory, and keeps human.access.readerFile as the fallback;
- the HelmRelease mounts room-broker-github-link there, optional, and not through
  broker.githubLink.existingSecret: Maku v0.48.0 refuses to start without the files under the chart's
  mount, and its NetworkPolicy would open any public address on 443;
- the ExternalSecret room-broker-github-link holds client_id and client_secret from agents/github-link;
- oauth2-proxy lets the callback and roomctl's discovery document through unauthenticated, nothing else;
- the broker's CiliumNetworkPolicy reaches github.com and api.github.com on 443;
- the factory reads the links from the broker (api.access.links broker), keeps readerFile, and says
  api.preset zitadel.

The rendered Deployment (the chart with its postRenderers) is checked where the chart can be had.
"""
import pathlib
import posixpath
import sys

try:
    import yaml
except ImportError:
    print("SKIP: pyyaml not installed")
    sys.exit(77)

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts/ci"))
import room_broker_chart  # noqa: E402

SECRET = "room-broker-github-link"  # pragma: allowlist secret
SKIP_AUTH = {"GET=^/\\.well-known/roomctl$", "GET=^/link/github/callback$"}
CLOUDS = ("aws-0", "gcp-0")


def find(docs, kind, name):
    return next((d for d in docs if d["kind"] == kind and d["metadata"]["name"] == name), None)


checks = {}
link = None
for copy in ("base", *CLOUDS):
    human = yaml.safe_load((ROOT / f"infrastructure/{copy}/room-broker/config.yaml").read_text())["human"]
    gl = human.get("githubLink") or {}
    link = link or gl
    checks[f"{copy} config: human.preset zitadel"] = human.get("preset") == "zitadel"
    checks[f"{copy} config: human.githubLink sets both files and activeWindow 168h"] = (
        bool(gl.get("clientIDFile")) and bool(gl.get("clientSecretFile")) and gl.get("activeWindow") == "168h")
    checks[f"{copy} config: human.githubLink is base's"] = gl == link
    checks[f"{copy} config: human.access.readerFile stays the fallback"] = bool((human.get("access") or {}).get("readerFile"))

link_dir = posixpath.dirname(link.get("clientIDFile", ""))
checks["the two link files share one directory"] = bool(link_dir) and posixpath.dirname(link.get("clientSecretFile", "")) == link_dir
checks["the link files are not under the chart's /etc/room-broker/github-link mount (required at start)"] = (
    link_dir != "/etc/room-broker/github-link")

for cloud in CLOUDS:
    try:
        docs = room_broker_chart.build(ROOT, f"infrastructure/{cloud}/room-broker")
    except room_broker_chart.Unavailable as e:
        print(f"SKIP: {e}")
        sys.exit(77)
    hr = find(docs, "HelmRelease", "room-broker")["spec"]["values"]["broker"]
    vols = {v["name"]: v for v in hr.get("extraVolumes", [])}
    mounts = {m["name"]: m["mountPath"] for m in hr.get("extraVolumeMounts", [])}
    vol = next((v for v in vols.values() if (v.get("secret") or {}).get("secretName") == SECRET), None)
    checks[f"{cloud}: the HelmRelease mounts {SECRET}, optional, at the config's directory"] = (
        vol is not None and vol["secret"].get("optional") is True and mounts.get(vol["name"]) == link_dir)
    checks[f"{cloud}: broker.githubLink.existingSecret stays unset"] = not (hr.get("githubLink") or {}).get("existingSecret")

    es = find(docs, "ExternalSecret", SECRET)
    data = {d["secretKey"]: d["remoteRef"] for d in (es or {}).get("spec", {}).get("data", [])}
    checks[f"{cloud}: ExternalSecret {SECRET} holds client_id and client_secret from agents/github-link"] = (
        es is not None and es["spec"]["target"]["name"] == SECRET
        and es["spec"]["secretStoreRef"] == {"kind": "SecretStore", "name": "agents-secrets"}
        and data == {k: {"key": "github-link", "property": k} for k in ("client_id", "client_secret")})

    proxy = find(docs, "HelmRelease", "rooms-oauth2-proxy")["spec"]["values"]["extraArgs"]
    checks[f"{cloud}: oauth2-proxy skips auth for the callback and roomctl's discovery alone"] = (
        set(proxy.get("skip-auth-route", "").split(",")) == SKIP_AUTH)

    egress = find(docs, "CiliumNetworkPolicy", "room-broker")["spec"]["egress"]
    for host in ("github.com", "api.github.com"):
        checks[f"{cloud}: the broker's CNP reaches {host} on 443"] = any(
            any(f.get("matchName") == host for f in r.get("toFQDNs") or [])
            and any(p.get("port") == "443" for tp in r.get("toPorts") or [] for p in tp.get("ports") or [])
            for r in egress)

    try:
        deploy = find(room_broker_chart.render(ROOT, cloud), "Deployment", "room-broker")
    except room_broker_chart.Unavailable as e:
        print(f"  skip {cloud}: the rendered Deployment ({e})")
        continue
    pod = deploy["spec"]["template"]["spec"]
    rvol = next((v for v in pod["volumes"] if (v.get("secret") or {}).get("secretName") == SECRET), None)
    rmounts = {m["name"]: m["mountPath"] for c in pod["containers"] for m in c.get("volumeMounts", [])}
    checks[f"{cloud}: the rendered broker mounts {SECRET} once, optional, at {link_dir}"] = (
        rvol is not None and rvol["secret"].get("optional") is True and rmounts.get(rvol["name"]) == link_dir
        and sum((v.get("secret") or {}).get("secretName") == SECRET for v in pod["volumes"]) == 1)

factory = yaml.safe_load(yaml.safe_load((ROOT / "tooling/base/agent-factory/helm-values-configmap.yaml").read_text())
                         ["data"]["values.yaml"])["config"]["api"]
access = factory.get("access") or {}
checks["factory: api.preset zitadel"] = factory.get("preset") == "zitadel"
checks["factory: api.access.links broker, readerFile kept as the fallback"] = (
    access.get("links") == "broker" and bool(access.get("readerFile")))

fails = 0
for desc, ok in checks.items():
    print(f"  {'ok  ' if ok else 'FAIL'} {desc}")
    fails += not ok
sys.exit(1 if fails else 0)
