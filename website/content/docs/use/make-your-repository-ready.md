---
title: Make your repository ready
weight: 15
diataxis: how-to
description: "The three files that let an agent build and test your repository before it pushes, and what to do with the tests it cannot run."
---

Before an agent pushes, it runs your repository's own checks in its sandbox. The pull request you read
has then already been built and tested. Three files on the default branch make that possible. Without
them, the agent still opens a pull request, but nothing tested it first.

## What the sandbox has {#sandbox}

| The sandbox has | It does not have |
|---|---|
| `git`, `bash`, Python and `mise`, which installs your pinned tools | Docker, a database, a queue or any other service |
| GitHub and the package registries your platform team grants the repository | Any other host, or your CI's secrets |
| 2 CPU, 4 GiB of memory and 10 GiB of scratch space | More than 15 minutes for its checks |

The registries a platform team can grant are PyPI, npm, the Go module proxy, crates.io, Maven Central with Gradle's hosts, and Node's downloads. Your files
never name a host: ask your platform team for the registry your build needs.

## 1. Pin your tools in `mise.toml` {#mise}

The sandbox installs exactly the versions pinned here before it runs a check. Pin every tool a check
needs:

```toml
[tools]
go = "1.27.4"
golangci-lint = "2.14.0"
```

## 2. Declare the checks in `.github/agent-checks.yaml` {#agent-checks}

This file is the fast part of your CI. The sandbox reads it from the default branch only, so a branch
cannot change what it is held to.

```yaml
version: 1
timeoutMinutes: 12
tools: [go, golangci-lint]
definedBy: [mise.toml, go.mod, .golangci.yaml]
steps:
  - {name: build, run: go build ./..., ci: test, stopOnFailure: true}
  - {name: unit, run: go test -short ./..., ci: test}
  - {name: lint, run: golangci-lint run, ci: lint}
ciOnly:
  - {check: test, part: "integration tests", why: "they need Postgres; the sandbox has no Docker"}
```

| Key | What you write |
|---|---|
| `steps` | Each step is one shell line, run from the repository's root. `ci` names the CI check it stands for |
| `tools` | The `mise.toml` tools the steps use |
| `definedBy` | The files that change how the checks behave |
| `ciOnly` | What the sandbox cannot run, with `check`, `part` and `why` |

## 3. Say what the sandbox skips, in `ciOnly` {#ci-only}

List everything that needs Docker, a service, a secret or a host the sandbox cannot reach. Listing it
does not weaken anything: your CI still runs it, and CI decides whether the pull request merges.

Make such a test skip, not fail, when its service is missing. For example, skip a database test when
`DATABASE_URL` is unset. The sandbox removes `CI` from a step's environment, so a test that skips
outside CI skips there too.

## 4. Tell the agent how to work in `AGENTS.md` {#agents-md}

Write a few lines: how to build, test and lint, where the main parts live, and what a change must come
with. The agent reads it before it starts.

```markdown
# Agent notes

- Build: `go build ./...`. Unit tests: `go test -short ./...`. Lint: `golangci-lint run`.
- Integration tests need `DATABASE_URL`; they skip without it, and CI runs them.
- A new endpoint gets a handler test in `internal/http/`.
```

## Check it {#check}

Ask your platform team to run `maku repo check owner/repo`, or run it yourself if you have cluster
access. A ready repository prints:

```text
PASS  readiness      .github/agent-checks.yaml, mise.toml and AGENTS.md are on the default branch
```

A missing file prints `WARN` with the file's name and how to add it.

**Next:** [hand off your first task]({{< relref "/docs/use/guide/your-first-task.md" >}}).
