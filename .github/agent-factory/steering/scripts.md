# Steering: scripts

## Verify
- `task test` (CI: validate): every suite under `scripts/ci/tests/`; `scripts/ci/tests/run.sh` runs them directly.
- In the sandbox `agent-checks` is the evidence: it runs the CI's fast subset (`.github/agent-checks.yaml`). `task check` runs in CI, not here: it needs `helm`, Docker and hosts the sandbox cannot reach.
- Never install a tool the sandbox lacks (`helm`, Docker): those checks are CI-only, listed under `ciOnly` in `.github/agent-checks.yaml`.

## Leave alone
- `scripts/ci/flux-schema/` and `taskfile.yaml`: the gates and the entry points; edit only when the issue names them.

## Write
- Shell with `set -euo pipefail` or Python 3 with PyYAML; a suite or a gate gets a test beside it.
