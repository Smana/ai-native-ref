"""The room broker as Flux applies it (R1): the HelmRelease of infrastructure/<cloud>/room-broker,
its pinned `maku` chart rendered with its values, and its postRenderers applied, as helm-controller
does. Suites read the broker's Deployment, Service, RBAC and CronJob from here, since no file in
this repository holds them any more.

render() raises Unavailable when the chart cannot be had (no helm, no kustomize, no network and no
cached copy): a suite then exits 77, a SKIP, as test-maku-config-load.sh does without its clone.
"""
import os
import pathlib
import re
import shutil
import subprocess
import tempfile

import yaml

# What Flux substitutes from the cluster's vars, with values the chart accepts.
SUBS = {"oidc_issuer_url": "https://issuer.test", "oidc_jwks_uri": "https://issuer.test/keys",
        "identity_provider_url": "https://auth.example.test", "private_domain_name": "priv.example.test",
        "public_domain_name": "example.test", "oidc_jwks_host": "issuer.test", "region": "eu-west-3",
        "project_id": "project-0", "cluster_name": "cluster-0"}
# The render-bundle's cache (the host's validate-manifests.sh pulls the pinned chart there first).
CACHE = pathlib.Path(os.environ.get("HELM_CACHE_HOME", pathlib.Path.home() / ".cache/helm")) / "oci-charts"


class Unavailable(Exception):
    pass


def substitute(text):
    return re.sub(r"\$\{(\w+)\}", lambda m: SUBS.get(m.group(1), "unset-var-" + m.group(1)), text)


def build(root, path):
    """`kustomize build` of a directory, as parsed documents."""
    if not shutil.which("kustomize"):
        raise Unavailable("kustomize not installed")
    out = subprocess.run(["kustomize", "build", str(pathlib.Path(root) / path)],
                         capture_output=True, text=True, check=True).stdout
    return [d for d in yaml.safe_load_all(out) if d]


def helmrelease(root, cloud="base"):
    """The room-broker HelmRelease of a cloud's render, generated names resolved."""
    return next(d for d in build(root, f"infrastructure/{cloud}/room-broker")
                if d["kind"] == "HelmRelease" and d["metadata"]["name"] == "room-broker")


def source(root):
    """The OCIRepository the HelmRelease's chartRef names."""
    return yaml.safe_load((pathlib.Path(root) / "infrastructure/base/room-broker/ocirepository.yaml").read_text())


def chart(root, tmp):
    """The pinned chart's tarball: the render-bundle's cached copy, else a pull by digest."""
    ref = source(root)["spec"]
    url, digest = ref["url"], ref["ref"]["digest"]
    cached = CACHE / f"{url.removeprefix('oci://').replace('/', '_')}_{digest.replace(':', '_')}.tgz"
    if cached.is_file():
        return cached
    if not shutil.which("helm"):
        raise Unavailable("helm not installed")
    out = subprocess.run(["helm", "pull", f"{url}@{digest}", "-d", str(tmp)], capture_output=True, text=True)
    pulled = sorted(pathlib.Path(tmp).glob("*.tgz"))
    if out.returncode or not pulled:
        raise Unavailable(f"cannot pull {url}@{digest}: {out.stderr.strip()[-160:]}")
    return pulled[0]


def render(root, cloud="base"):
    """The chart's objects as Flux applies them for a cloud, post-renderers included."""
    hr = helmrelease(root, cloud)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        tgz = chart(root, tmp)
        (tmp / "values.yaml").write_text(substitute(yaml.safe_dump(hr["spec"]["values"])))
        out = subprocess.run(["helm", "template", hr["spec"]["releaseName"], str(tgz), "--skip-crds",
                              "--kube-version", "1.33.0", "-n", hr["metadata"]["namespace"],
                              "-f", str(tmp / "values.yaml")], capture_output=True, text=True)
        if out.returncode:
            raise RuntimeError(f"helm template failed: {out.stderr.strip()}")
        post = tmp / "post"
        post.mkdir()
        (post / "rendered.yaml").write_text(out.stdout)
        patches = [p for r in hr["spec"].get("postRenderers", []) for p in r["kustomize"].get("patches", [])]
        (post / "kustomization.yaml").write_text(yaml.safe_dump({"resources": ["rendered.yaml"], "patches": patches}))
        out = subprocess.run(["kustomize", "build", str(post)], capture_output=True, text=True)
        if out.returncode:
            raise RuntimeError(f"a postRenderer patch failed: {out.stderr.strip()}")
    return [d for d in yaml.safe_load_all(out.stdout) if d]
