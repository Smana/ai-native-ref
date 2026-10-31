# LinkedIn post draft

Agents you can hand work to, not just sit next to.

I've been building an open-source agent factory on Kubernetes, a bundle of OSS tools (Maku, agentgateway, OpenHands, gVisor, octo-sts…). Maku turns the issue into a task: a maintainer labels a GitHub issue, a coding agent works it in a gVisor sandbox under its own short-lived identity, every call is metered through a gateway, and a human review decides the merge. Every control sits outside the sandbox: network policy, per-run tokens, budgets, a kill switch.

Serving and agents, one platform, Apache-2.0 → airef.ogenki.io

#Kubernetes #PlatformEngineering #AIAgents #OpenSource

---

Alternatives for the first line:

- Label an issue. Review a pull request. Everything in between runs sandboxed, metered and attributed.
- What changes when an agent runs on a platform instead of a laptop? You can trust, meter, audit and stop it.

---

# The v3 clip (docs, not the feed)

`agent-factory-v3`, 33 s, 1080×1280, no title card. It sits under the diagram on the
[run roles](https://airef.ogenki.io/docs/platform/ai-platform/agents/roles/) page. What it says,
beat by beat:

1. **0–7 s.** Before any code, a **scoper** bounds the task. Or asks the author **one question**.
2. **7–13 s.** Too big? **Split** into parts a maintainer approves, landed **one by one**.
3. **13–20 s.** The implementer runs the repo's **own checks**, asks **search** and **stops if it wanders**.
4. **20–27 s.** A fresh-context **judge** says done. A fresh-context **reviewer** cites the **checks**.
5. **27–33 s.** Each stage is a per-class switch. **Only link fixes and reverts merge without a human.**

Post line, if it is shared: "The agent that writes the code never grades it: a scoper before, a
judge and a reviewer after, and a human for anything but a link fix."
