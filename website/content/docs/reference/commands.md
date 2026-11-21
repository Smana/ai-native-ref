---
title: Commands
weight: 15
description: "This platform's room broker URL, OIDC sign-in command, MCP setup and hand-started run task, with a link to Maku's CLI reference."
lastVerified: 2026-11-15
diataxis: values
---

`maku` is the terminal client and local MCP server for reading rooms, checking what needs you, handing
tasks to the planner, and checking out agent branches; every subcommand, flag, MCP tool, room state and
exit code is in Maku's [CLI guide]({{< maku "docs/cli.md" >}}).

## CLI and sign-in values on this platform {#maku}

<span id="setup"></span><span id="tools"></span><span id="clients"></span><span id="room-states"></span><span id="run-ends"></span><span id="run-by-hand"></span>

Example (the reference host): download `maku` from the release pinned on the
[status page]({{< relref "/docs/status.md" >}}), then configure it against this host's room broker and
ZITADEL issuer:

```bash
maku configure \
  --url https://rooms.<private-domain> \
  --issuer https://zitadel.<private-domain> \
  --client-id <roomctl-client-id> \
  --project-id <zitadel-project-id>
maku login
maku setup opencode   # or: claude, codex, gemini, cursor, copilot
```

The exact `maku configure` one-liner with the cluster's current client and project IDs is printed in the
**CLI setup** drawer on `https://rooms.<private-domain>`.

<!-- example -->
| Platform setting | Value on this platform | Manifest path |
|---|---|---|
| Room broker URL (`publicURL`, `roomsURL`) | `https://rooms.${private_domain_name}` (`https://rooms.priv.aws.ogenki.io` or `https://rooms.priv.gcp.ogenki.io`) | `infrastructure/base/room-broker/config.yaml`, `tooling/base/agent-factory/helm-values-configmap.yaml` |
| Identity provider preset and issuer | `preset: zitadel`, `issuer: ${identity_provider_url}`, `groups: {admin: agents-admin, member: agents-member}` | `infrastructure/base/room-broker/config.yaml` |
| CLI OIDC client and project IDs | Mounted from OpenBao into `/etc/room-broker/roomctl/client-id` and `/etc/room-broker/oidc/project-id` | `infrastructure/base/room-broker/config.yaml`, `infrastructure/base/room-broker/externalsecret-roomctl.yaml`, `infrastructure/base/room-broker/externalsecret-rooms-proxy.yaml` |
| Developer MCP server (`maku mcp`) | `human.mcp.enabled: true`; `human.mcp.start` unset, so `start`'s form offers **Start now** on every repository the planner serves (`human.mcp.start.except` lists the repositories where it never does) | `infrastructure/base/room-broker/config.yaml`, `infrastructure/aws-0/room-broker/config.yaml`, `infrastructure/gcp-0/room-broker/config.yaml` |
| Start a run by hand (`agents-member`) | `task agent:run -- --role implementer --class public --task-url <issue>` (wraps `scripts/ops/k8s/agent-run.sh` against `:8082`) | `taskfile.yaml`, `scripts/ops/k8s/agent-run.sh` |

Unlike Maku's generic OIDC defaults (which require only an issuer and client ID), this platform uses
the `zitadel` preset with a ZITADEL project ID audience check and a tailnet-only `rooms.${private_domain_name}`
endpoint signed by the cluster's `openbao-ca` root CA.
