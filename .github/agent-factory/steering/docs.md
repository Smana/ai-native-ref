# Steering: docs

## Verify
- `task links` (CI: validate): every relative Markdown link resolves.
- `task docs` (CI: validate): the site builds; every repository path it names exists.
- In the sandbox `agent-checks` is the evidence: it runs the CI's fast subset (`.github/agent-checks.yaml`). `task check` runs in CI, not here: it needs `helm`, Docker and hosts the sandbox cannot reach.
- Never install a tool the sandbox lacks (`helm`, Docker): those checks are CI-only, listed under `ciOnly` in `.github/agent-checks.yaml`.

## Leave alone
- `docs/superpowers/`: dated designs and plans; edit only the one the issue names.
- `website/content/docs/decisions/`: an ADR is superseded by a new one, never edited.

## Write
- English, short declarative sentences, tables over prose; a host page by absolute URL.
- Site pages follow `docs/docs-style.md`; `python3 scripts/ci/check-reader-first.py` checks them offline.
