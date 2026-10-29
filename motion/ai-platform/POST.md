# LinkedIn post draft

Agents you can hand work to, not just sit next to.

I've been building Maku, an open-source agent platform on Kubernetes. Its factory feature turns an issue into a pull request: a maintainer labels a GitHub issue, a coding agent works it in a gVisor sandbox under its own short-lived identity, every call is metered through a gateway, and a human review decides the merge. Every control sits outside the sandbox: network policy, per-run tokens, budgets, a kill switch.

The dark factory, as a platform: serving and agents, one platform, Apache-2.0 → airef.ogenki.io

#Kubernetes #PlatformEngineering #AIAgents #OpenSource

---

Alternatives for the first line:

- Label an issue. Review a pull request. Everything in between runs sandboxed, metered and attributed.
- What changes when an agent runs on a platform instead of a laptop? You can trust, meter, audit and stop it.
