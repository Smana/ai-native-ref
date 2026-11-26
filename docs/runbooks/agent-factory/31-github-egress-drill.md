# 31 — GitHub egress: the install window, live

Maku's [GitHub egress tightening](https://github.com/Smana/maku/blob/main/docs/superpowers/specs/2026-11-26-github-egress-tightening-design.md)
takes GitHub's release and raw hosts off every run's allow-list. A check-enabled run reaches them
only in its install phase: the harness installs the pinned tools and pre-commit's hook environments,
closes those hosts at the egress proxy, checks that a release download is refused, and only then
starts the agent. This runbook proves it on the cluster the fences name, with ANR as the repository.

Needs: the Maku release that carries the install window, pinned here (the `room-broker` HelmRelease's
images and chart). `kubectl` stays read-only apart from the runs this drill starts and the two
fault injections in step 4, each undone at its end. Keep the task names, run ids, the proxy log
lines and the alert's firing time in `results-github-egress-drill-<date>.md` beside this runbook.

## 0. Baseline

```bash
kubectl -n agent-system get deploy egress-proxy -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'
kubectl -n agents get role egress-proxy -o jsonpath='{.rules[0].verbs}{"\n"}'
kubectl get validatingadmissionpolicy maku-agent-system-run-pods -o yaml | grep -c egress-install
kubectl -n agent-system get configmap run-controller-config -o jsonpath='{.data.config\.yaml}' | grep -A3 installEgress || echo "installEgress: built-in defaults"
kubectl -n observability get vmrule agent-platform-logs -o yaml | grep -c MakuEgressInstallClosedRefusal
```

Expected: the proxy runs the pinned `maku-run-controller` digest; the proxy's Role in `agents` lists
`patch` beside `get`, `list`, `watch`; the run-pod policy names the install annotations (count above
0); no `installEgress` override (the built-in hosts); the logs rule exists.

## 1. The incident, replayed

File an issue on `Smana/ai-native-ref` whose task, once the run starts, tells the agent to run:

```bash
python3 -c "import urllib.request; urllib.request.urlretrieve('https://github.com/robxu9/bash-static/releases/download/5.2.015-1.2.3-2/bash-linux-x86_64','/workspace/b')"
curl -sS -o /dev/null -w '%{http_code}\n' https://raw.githubusercontent.com/Smana/ai-native-ref/main/README.md
curl -sS -o /dev/null -w '%{http_code}\n' https://codeload.github.com/Smana/ai-native-ref/tar.gz/main
```

Label it `factory/ready` (a maintainer). Then, with `<id>` the run id:

```bash
kubectl -n agent-system logs -l app.kubernetes.io/name=egress-proxy --prefix --tail=-1 | grep "run=<id>"
```

Pass:

- The download fails in the agent's step. The proxy logs `allow run=<id> github.com:443` (GitHub
  answers the release URL with a 302), then `refuse run=<id> release-assets.githubusercontent.com:443`
  (or `objects.githubusercontent.com:443`) with `"reason":"install_closed"` and `"phase":"agent"`.
- `raw.githubusercontent.com:443` is refused `install_closed` (it is in the install set), and
  `codeload.github.com:443` is refused `not_allowed` (in no set).
- `MakuEgressInstallClosedRefusal` fires within the rule's 5-minute interval (Grafana, Alerting).

## 2. The pinned toolchain still installs

In the same run's harness log, before its first `agent-run step`:

```bash
kubectl -n agents logs <run pod> -c harness | grep -E "install phase|install hosts closed|agent-run step 1:" | head
```

Pass: `agent-run install phase: agent-checks: toolchain ready`, then
`agent-run: install hosts closed: the egress proxy refuses them`, then the first step. The proxy
logs the harness's check as `refuse run=<id> install-check.maku.invalid:443` with
`"reason":"install_check"`, which the alert ignores. The run's own `agent-checks` in the agent phase reports no `toolchain incomplete`, and
the pre-commit hook environments exist:

```bash
kubectl -n agents exec <run pod> -c harness -- ls /workspace/.toolchain/cache/pre-commit | head
```

Read-only `exec`: it lists a directory. Skip it if the run already ended; the `agent-checks` result
in the room shows the `pre-commit` steps passing instead.

## 3. The proxy's view of the phases

```bash
kubectl -n agent-system logs -l app.kubernetes.io/name=egress-proxy --prefix --tail=-1 | grep -E "run=<id>|close-install run=<id>"
```

Pass: `allow ... release-assets.githubusercontent.com:443` lines carry `"phase":"install"` only; one
`close-install run=<id>`; every later release or raw host line is a refusal with `"phase":"agent"`.
Record the time from the first decision to the close: the install phase's length. Compare it with
the M1 baseline in the Maku spec (p50 15 s); over about 60 s at p50 across the drill's runs is the
signal for a shared toolchain cache, not for reopening the hosts.

## 4. Fail closed

Two fault injections, each on one scratch run, each undone before the next step. Suspend the
release first so Flux does not revert them mid-run:

```bash
flux suspend helmrelease -n agent-system room-broker
```

**a. The window ends before the close.** Patch the run-controller's config to a 1-second window,
restart it, start one check run, then restore:

```bash
kubectl -n agent-system get configmap run-controller-config -o jsonpath='{.data.config\.yaml}' > /tmp/rc.yaml
printf 'installEgress:\n  windowSeconds: 1\n' >> /tmp/rc.yaml   # only if the file has no installEgress yet
kubectl -n agent-system create configmap run-controller-config --from-file=config.yaml=/tmp/rc.yaml --dry-run=client -o yaml | kubectl apply -f -
kubectl -n agent-system rollout restart deploy run-controller
```

Pass: the run's harness logs `install phase: agent-checks: toolchain incomplete: ...` (the hosts
closed under it), the close succeeds, the check host answers 403, and the agent starts; its proxy lines
show `install_closed` from the start. Restore with `flux resume helmrelease -n agent-system room-broker`
and check the ConfigMap lost the override.

**b. The close fails.** Take `patch` away from the proxy, start one check run, then restore:

```bash
kubectl -n agents patch role egress-proxy --type=json -p '[{"op":"replace","path":"/rules/0/verbs","value":["get","list","watch"]}]'
```

Pass: the proxy logs `close-install failed run=<id>` (a 403 from the API server), the harness logs
`agent-run: egress_install_open: the close answered 500; the agent does not start`, the run ends
`Failed` and the room shows no agent step. Restore with `flux resume helmrelease -n agent-system room-broker`
and check the Role lists `patch` again.

## 5. No regression

One ordinary ANR task, an issue the factory would take anyway, reaches a pull request with its
checks green. Record its wall time and its install phase's length beside step 3's.

## What this does not prove

- `git clone` of a public repository on `github.com` still works by design: the spec's residual.
- In `cilium` mode the install hosts stay open for the run. The reference host runs `kubernetes`
  mode; the follow-up spec moves `cilium` mode's HTTPS through the proxy.
