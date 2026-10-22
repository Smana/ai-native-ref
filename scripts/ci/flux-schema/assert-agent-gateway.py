#!/usr/bin/env python3
"""Gate the rendered bundle on the agent router's agentgateway invariants (ADR-0042, ADR-0053).

Each check relates objects that `flux schema validate` sees one at a time, and
breaking any of them leaves every object valid and the boundary quietly open.
A Gateway of class agentgateway is judged against its entry in PROFILES, which
names its listeners, audiences, caller namespace and route namespace:

  AG1  Every Gateway of class agentgateway has a profile, declares exactly its
       listeners and ports, and admits routes from its route namespace only.
       A required profile (the real agent router) must render in every cluster
       that renders agentgateway, so the PoC alone never passes. No such Gateway
       at all is a layout regression, not compliance.
  AG2  Each listener has exactly one listener-scoped jwtAuthentication: mode
       Strict, audiences equal to its class set, requiredClaims holding exp and
       sub, an authorization Require on the caller namespace's sub prefix, and
       a `set` of x-ar-agent from jwt.sub.
  AG3  A Gateway-scoped PreRouting transformation removes the four identity
       headers before routing.
  AG4  preserveToken is true on the sts listener and nowhere else, and no MCP
       target credential or transformation writes Authorization.
  AG5  Every route on the Gateway sets sectionName and lives in the route
       namespace; a Z.ai backend is reachable from `public` only and an
       Anthropic one from `internal` only (ADR-0054); a rule sends to one
       backend; no policy other than the listener ones carries
       jwtAuthentication. A Z.ai backend uses the custom provider: 1.6 keeps
       `openai` for the OpenAI API.
  AG6  Every MCP authorization is an Allow list whose expressions are each one
       complete alternative (role AND target AND tool names), for the route's
       own class: Allow expressions are OR-ed at runtime (PoC N7).
  AG7  Every listener with an LLM route answers an Exact /v1/models with a
       404 direct response (PoC N3).
  AG8  Every rateLimit.global fails open, charges Tokens at the run meter's
       price in reference tokens (design D11, J-AC2: the cost string is
       regenerated from meter.prices and must match), names no route or
       backend, and its domain resolves to a rate-limit ConfigMap. Every server
       mounting it sets SHADOW_MODE to "true" or "false", all alike, and no
       descriptor sets shadow_mode: SHADOW_MODE is the one switch (runbook 04,
       Part D), which a descriptor's own shadow_mode would override. The per-run
       bucket is at least every tier's run cap (runUSD in reference tokens, and
       runTokens), the fleet bucket at least budgets.factoryDaily plus
       caps.concurrentRuns runs at that cap: the gateway never refuses before
       the factory would. A local limit on the real router, which refuses in either mode, allows
       at least the raw tokens of the largest run the factory admits: its
       USD cap spent entirely on cache reads at the cheapest rate among the
       models its tier's name reaches, or its runTokens. Every descriptor
       entry and local-limit key reads only
       claims the JWT policy requires on each listener it covers: a descriptor
       whose CEL fails is dropped, unlimited (#3523). `aud` counts as required
       where every covered listener checks audiences. A local limit names a key.
  AG9  The Gateway's AgentgatewayParameters keeps the constitution's pod shape
       (seccomp, liveness, memory limit), ClusterIP, 2 replicas, a PDB, a
       digest-pinned image, and shutdown {min: 10, max: 660} (PoC N1).
  AG10 Every model a backend pins (each alias target, or its fixed model) has
       a row in the run meter's price overlay (meter.prices in the factory's
       values, plan J.1): input, cacheRead and output, and cacheWrite where the
       provider bills cache writes (Anthropic). meter.query groups by
       gen_ai_request_model, so each run is priced by the model that served it,
       not by its claim's agent name. An unpriced model is never free (J-AC4),
       but its runs would escape the USD caps.
  AG11 A provider with a host override names its path (1.6 sends `/` when the
       base has none), and a Z.ai backend routes typed formats only: Detect
       and Passthrough join the path wrongly (#3853).
  AG12 An LLM backend has one provider. One the agent router routes to
       refuses every name outside AGENT_MODELS before any upstream call
       (design D8): modelAliases names exactly AGENT_MODELS, with no wildcard;
       a `model` transformation, MODEL_ALLOWLIST, takes x-ar-model when the
       identity proxy pinned it (capability profiles P4), else the body's
       model, and nulls any name outside AGENT_MODELS, which 1.6 answers 400
       "model not specified" (finalize_request_model); and no fixed provider
       model, override or default supplies a model, since each maps every name
       to one. No policy carries aliases or a model mutation: names live on
       the backend. No object removes x-ar-model: removed before the backend
       reads it, the model would follow the body while AG14's rule judged the
       header (measured on 1.6.0). Any other backend (the PoC) keeps a fixed
       model or a `*` catch-all, so it serves only models we list.
  AG13 A backend that dials GitHub is the read-only route of identity design T4:
       TLS, no credential, no policy aimed at it or its routes, reached from
       `internal` only, and every match one of GITHUB_READ_MATCHES (a fetch
       of the opted-in repositories) on a rule that strips GITHUB_STRIPPED.
       Anything else, git-receive-pack included, matches no route: 404.
  AG14 Every rule of the agent router that sends to an LLM backend, except
       one a directResponse answers, is targeted by exactly one route-level
       authorization (capability profiles P2): a Require holding the
       listener's sub prefix, repeated, and one model rule over
       EFFECTIVE_MODEL naming each of the listener's audiences. A rule a
       directResponse answers (/v1/models, AG7) carries no authorization that
       reads the body: its GET would be refused 403 before its 404. Every
       model the factory's tiers pin is in every alternative: a run of that
       tier would otherwise be refused at its first call. A Gateway-scoped
       policy sets frontend.http.maxBufferSize: the rule reads the body within
       it, and without it 1.6 buffers 2 MiB there and 32 MiB for the backend,
       so a long run's call would be refused that the backend could take.

1.6 CRDs store no defaults, so every check reads explicit fields: an absent
field fails rather than being assumed. The bundle holds base and per-cluster
renders of the same objects, so the checks run once per cluster.

Usage: assert-agent-gateway.py [BUNDLE_DIR]    (default .bundle)
Exit:  0 clean, 1 violations (each printed), 2 bundle missing.
"""
import json
import pathlib
import re
import sys
from typing import NamedTuple

import yaml

from yamlcompat import YAML_LOADER

CLASS = "agentgateway"
API_GROUP = "agentgateway.dev"
ROLES = ("implementer", "reviewer", "tester", "triager")
IDENTITY_HEADERS = ("x-ar-agent", "x-ar-human", "x-ai-gateway-client-id", "agent-session-id")
REQUIRED_CLAIMS = {"exp", "sub"}
SHUTDOWN = {"min": 10, "max": 660}
UNTYPED_ROUTES = {"Detect", "Passthrough"}
ROUTE_KINDS = ("HTTPRoute", "GRPCRoute")
# ADR-0054: the listeners each provider may serve.
PROVIDER_LISTENERS = {"Z.ai": {"public"}, "Anthropic": {"internal"}}
# Design D11, OD-6, J-AC2: USD is the policy unit, and a rate-limit descriptor
# needs an integer, so a request costs its price in reference tokens ($1.70 per
# M), priced by the meter's own table, or its total tokens when the model has no
# row. A cost that fails to evaluate drops the descriptor silently, so the string
# is generated here and pinned.
REF_USD_PER_M = 1.7
# The rate-limit descriptors B1 (one bucket per verified sub, i.e. per run) and B2.
RUN_BUCKET, FLEET_BUCKET = "agent", "fleet"


def billable_cost(prices):
    """The cost CEL for meter.prices: the meter's formula, row [input, cacheRead, cacheWrite, output].

    A malformed row is left out, so the policy's cost cannot match; AG10 names the row."""
    def num(v):
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    rows = ", ".join(f'"{m}": [{float(p["input"])}, {float(p["cacheRead"])}, '
                     f'{float(p.get("cacheWrite", p["input"]))}, {float(p["output"])}]'
                     for m, p in sorted(prices.items())
                     if isinstance(p, dict) and all(num(p.get(f)) for f in PRICE_FIELDS)
                     and num(p.get("cacheWrite", 0)))
    cached, written = "double(default(llm.cachedInputTokens, 0))", "double(default(llm.cacheCreationInputTokens, 0))"
    return ("{" + rows + "}.with(p, llm.requestModel in p ? p[llm.requestModel].with(r, uint(("
            f"(double(default(llm.inputTokens, 0)) - {cached} - {written}) * r[0] + {cached} * r[1] + {written} * r[2]"
            f" + double(default(llm.outputTokens, 0)) * r[3]) / {REF_USD_PER_M})) : uint(llm.totalTokens))")
# Design D8, plan I.1: the agent names, on every agent-router listener.
AGENT_MODELS = ("agent-default", "tier-light", "tier-standard", "tier-frontier")
MODEL_HEADER = "x-ar-model"
MODEL_ALLOWLIST = (f'("{MODEL_HEADER}" in request.headers ? request.headers["{MODEL_HEADER}"] : llmRequest.model)'
                   f".with(m, m in {json.dumps(list(AGENT_MODELS))} ? m : null)")
# AG14: the model a call reaches, read where the route's authorization runs, before the backend parses
# the body (1.6 has no llm.requestModel there): the header MODEL_ALLOWLIST reads, else the body's.
EFFECTIVE_MODEL = (f'("{MODEL_HEADER}" in request.headers ? request.headers["{MODEL_HEADER}"] '
                   f": json(request.body).model)")
MODEL_MUTATIONS = ("overrides", "defaults")
# Identity design T4: the internal listener's GitHub route reads, never writes. Git's
# smart-HTTP fetch is these two requests; a push is GET ?service=git-receive-pack then
# POST /git-receive-pack, and the REST API is not routed at all. The repositories are
# the octo-sts opt-in: REPOSITORIES feeds both, and each repository's trust policies accept only
# its own audiences. A third repository needs a second sts listener (design, security analysis).
REPOSITORIES = ("Smana/cloud-native-ref", "Smana/ai-native-ref")
_REPOS = "(" + "|".join(r.split("/")[1] for r in REPOSITORIES) + ")"
GITHUB_READ_MATCHES = (
    {"method": "GET", "path": {"type": "RegularExpression", "value": rf"^/Smana/{_REPOS}\.git/info/refs$"},
     "queryParams": [{"type": "Exact", "name": "service", "value": "git-upload-pack"}]},
    {"method": "POST", "path": {"type": "RegularExpression", "value": rf"^/Smana/{_REPOS}\.git/git-upload-pack$"}},
)
# The run's JWT is already gone (preserveToken off, AG4); these go too, so GitHub sees an anonymous fetch.
GITHUB_STRIPPED = ("authorization", "cookie")
GITHUB_LISTENERS = {"internal"}
CLUSTER = re.compile(r"-((?:aws|gcp)-\d+)-")
# The factory's Helm values, which carry the run meter's query and price overlay (AG10).
FACTORY_NS, FACTORY_VALUES = "agent-system", "agent-factory-helm-values"
PRICE_FIELDS = ("input", "cacheRead", "output")


class Profile(NamedTuple):
    listeners: dict
    routes_ns: str
    aud_prefix: str
    sub_ns: str
    roles: tuple = ROLES
    required: bool = False


# Keyed by Gateway (namespace, name). Phase H removes the PoC with its entry.
PROFILES = {
    ("agent-gateway", "agent-router"): Profile(
        listeners={"public": 8080, "internal": 8081, "sts": 8082},
        routes_ns="agent-system", aud_prefix="agent-router", sub_ns="agents", required=True),
    ("agw-poc", "agent-router-agw"): Profile(
        listeners={"public": 8080, "internal": 8081},
        routes_ns="agw-poc", aud_prefix="agw-poc", sub_ns="agw-poc-clients", roles=("implementer", "reviewer")),
}


def audiences(prof, listener):
    if listener == "sts":
        return {f"octo-sts/{repo}/{r}" for repo in REPOSITORIES for r in prof.roles}
    return {f"{prof.aud_prefix}.{r}.{listener}" for r in prof.roles}


def sub_prefix(prof):
    return f'jwt.sub.startsWith("system:serviceaccount:{prof.sub_ns}:")'


def alternative(prof):
    """The N7 grammar: one role, one target, its tool names. Reused by C.2's scope test."""
    name = r'"[a-z0-9_]+"'
    return re.compile(
        rf'^"{re.escape(prof.aud_prefix)}\.(?P<role>[a-z]+)\.(?P<cls>public|internal)" in jwt\.aud'
        r' && mcp\.tool\.target == "(?P<target>[a-z0-9-]+)"'
        rf' && mcp\.tool\.name (== {name}|in \[{name}(, {name})*\])$')


def meta(obj):
    return obj.get("metadata") or {}


def spec_of(obj):
    return obj.get("spec") or {}


def ref(obj):
    return f"{obj.get('kind')} {meta(obj).get('namespace', '')}/{meta(obj).get('name', '')}"


def key(obj):
    return meta(obj).get("namespace"), meta(obj).get("name")


def kind(objs, k):
    return [o for o in objs if o.get("kind") == k]


def policies(objs):
    return kind(objs, "AgentgatewayPolicy")


def gateways(objs):
    """(Gateway, Profile or None) for every Gateway of class agentgateway."""
    return [(g, PROFILES.get(key(g))) for g in kind(objs, "Gateway") if spec_of(g).get("gatewayClassName") == CLASS]


def profiled(objs):
    return [(g, p) for g, p in gateways(objs) if p]


def gateway_targets(policy, gw):
    """sectionName (or None) of each targetRef naming the Gateway from its own namespace."""
    if meta(policy).get("namespace") != meta(gw).get("namespace"):
        return []
    return [t.get("sectionName") for t in spec_of(policy).get("targetRefs") or []
            if t.get("kind") == "Gateway" and t.get("name") == meta(gw).get("name")]


def parents(route, gw):
    return [p for p in spec_of(route).get("parentRefs") or []
            if p.get("kind", "Gateway") == "Gateway" and p.get("name") == meta(gw).get("name")
            and p.get("namespace", meta(route).get("namespace")) == meta(gw).get("namespace")]


def routes_on(objs, gw):
    return [r for r in objs if r.get("kind") in ROUTE_KINDS and parents(r, gw)]


def listeners_of(route, gw):
    return {p.get("sectionName") for p in parents(route, gw)}


def backend_refs(route, rule_names=None):
    """(namespace, name) of every AgentgatewayBackend the route's (named) rules send to."""
    out = set()
    for rule in spec_of(route).get("rules") or []:
        if rule_names is not None and rule.get("name") not in rule_names:
            continue
        for b in rule.get("backendRefs") or []:
            if b.get("kind") == "AgentgatewayBackend":
                out.add((b.get("namespace", meta(route).get("namespace")), b.get("name")))
    return out


def providers(backend):
    """Every LLM provider block: ai.provider, or each one in ai.groups[].providers[]."""
    ai = spec_of(backend).get("ai") or {}
    found = [ai["provider"]] if ai.get("provider") else []
    return found + [p for g in ai.get("groups") or [] for p in g.get("providers") or []]


def is_zai(backend):
    hosts = [str(p.get("host", "")) for p in providers(backend)]
    return bool(providers(backend)) and (any(h == "z.ai" or h.endswith(".z.ai") for h in hosts)
                                         or "zai" in str(meta(backend).get("name", "")))


def is_anthropic(backend):
    return any("anthropic" in p or str(p.get("host", "")).endswith("anthropic.com") for p in providers(backend))


def provider_name(backend):
    return "Z.ai" if is_zai(backend) else "Anthropic" if is_anthropic(backend) else None


def check_gateway(objs):
    gws = gateways(objs)
    if not gws:
        return [f"AG1: no Gateway of class {CLASS} (zero is a layout regression, not compliance)"]
    out = [f"AG1: required Gateway {ns}/{name} is not rendered (the PoC alone must not pass)"
           for (ns, name), prof in PROFILES.items()
           if prof.required and (ns, name) not in {key(g) for g, _ in gws}]
    for g, prof in gws:
        if prof is None:
            out.append(f"AG1: {ref(g)} is a Gateway of class {CLASS} with no entry in PROFILES")
            continue
        got = {lst.get("name"): lst.get("port") for lst in spec_of(g).get("listeners") or []}
        if got != prof.listeners:
            out.append(f"AG1: {ref(g)} listeners are {got}, expected {prof.listeners}")
        for lst in spec_of(g).get("listeners") or []:
            ns = (lst.get("allowedRoutes") or {}).get("namespaces") or {}
            labels = (ns.get("selector") or {}).get("matchLabels") or {}
            same = ns.get("from") == "Same" and prof.routes_ns == meta(g).get("namespace")
            selected = ns.get("from") == "Selector" and labels == {"kubernetes.io/metadata.name": prof.routes_ns}
            if not (same or selected):
                out.append(f"AG1: {ref(g)} listener {lst.get('name')} must admit routes from {prof.routes_ns} only")
    return out


def check_listener_identity(objs):
    out = []
    listener_policies = set()
    for g, prof in profiled(objs):
        by_listener = {name: [] for name in prof.listeners}
        for p in policies(objs):
            if (spec_of(p).get("traffic") or {}).get("jwtAuthentication") is None:
                continue
            for s in gateway_targets(p, g):
                if s in by_listener:
                    by_listener[s].append(p)
                    listener_policies.add(id(p))
        for listener, found in by_listener.items():
            if len(found) != 1:
                out.append(f"AG2: {ref(g)} listener {listener} has {len(found)} jwtAuthentication policies, expected 1")
                continue
            p = found[0]
            traffic = spec_of(p).get("traffic") or {}
            jwt = traffic.get("jwtAuthentication") or {}
            if jwt.get("mode") != "Strict":
                out.append(f"AG2: {ref(p)} jwtAuthentication.mode must be Strict")
            provs = jwt.get("providers") or []
            auds = {a for prov in provs for a in prov.get("audiences") or []}
            if len(provs) != 1 or auds != audiences(prof, listener):
                out.append(f"AG2: {ref(p)} audiences are {sorted(auds)}, expected {sorted(audiences(prof, listener))}")
            for prov in provs:
                claims = set((prov.get("validation") or {}).get("requiredClaims") or [])
                if not REQUIRED_CLAIMS <= claims:
                    out.append(f"AG2: {ref(p)} requiredClaims {sorted(claims)} must hold exp and sub: "
                               "a sub-less token would share one unlimited rate-limit bucket (#3523)")
            authz = traffic.get("authorization") or {}
            exprs = (authz.get("policy") or {}).get("matchExpressions") or []
            if authz.get("action") != "Require" or exprs != [sub_prefix(prof)]:
                out.append(f"AG2: {ref(p)} must Require exactly {sub_prefix(prof)}")
            sets = ((traffic.get("transformation") or {}).get("request") or {}).get("set") or []
            if {"name": "x-ar-agent", "value": "jwt.sub"} not in sets:
                out.append(f"AG2: {ref(p)} must set x-ar-agent from jwt.sub")
            preserve = jwt.get("preserveToken") is True
            if preserve != (listener == "sts"):
                out.append(f"AG4: {ref(p)} preserveToken is {preserve}; only the sts listener forwards the bearer")
    for p in policies(objs):
        if (spec_of(p).get("traffic") or {}).get("jwtAuthentication") is not None and id(p) not in listener_policies:
            out.append(f"AG5: {ref(p)} carries jwtAuthentication but targets no profiled listener")
    return out


def check_strip(objs):
    out = []
    for g, _ in profiled(objs):
        for p in policies(objs):
            if None not in gateway_targets(p, g):
                continue
            traffic = spec_of(p).get("traffic") or {}
            req = (traffic.get("transformation") or {}).get("request") or {}
            removed = {h.lower() for h in req.get("remove") or []}
            if traffic.get("phase") == "PreRouting" and set(IDENTITY_HEADERS) <= removed:
                break
        else:
            out.append(f"AG3: no Gateway-scoped PreRouting policy on {ref(g)} removes {', '.join(IDENTITY_HEADERS)}")
    return out


def check_token_isolation(objs):
    out = []
    for p in policies(objs):
        traffic = spec_of(p).get("traffic") or {}
        if (traffic.get("jwtAuthentication") or {}).get("preserveToken") is True and not any(
                "sts" in gateway_targets(p, g) for g, _ in profiled(objs)):
            out.append(f"AG4: {ref(p)} sets preserveToken outside an sts listener")
        for section in (traffic, spec_of(p).get("backend") or {}):
            req = (section.get("transformation") or {}).get("request") or {}
            for h in (req.get("set") or []) + (req.get("add") or []):
                if str(h.get("name", "")).lower() == "authorization":
                    out.append(f"AG4: {ref(p)} writes Authorization in a transformation")
    for b in kind(objs, "AgentgatewayBackend"):
        for t in (spec_of(b).get("mcp") or {}).get("targets") or []:
            auth = ((t.get("static") or {}).get("policies") or {}).get("auth")
            if not auth:
                continue
            creds = auth.get("credentials") or []
            headers = [((c.get("location") or {}).get("header") or {}).get("name", "") for c in creds]
            if set(auth) - {"credentials"} or not creds or any(not h or h.lower() == "authorization" for h in headers):
                out.append(f"AG4: {ref(b)} target {t.get('name')} must inject its key in a named header "
                           "other than Authorization")
    return out


def check_routes(objs):
    out = []
    named = {key(b): provider_name(b) for b in kind(objs, "AgentgatewayBackend") if provider_name(b)}
    for g, prof in profiled(objs):
        for r in routes_on(objs, g):
            if meta(r).get("namespace") != prof.routes_ns:
                out.append(f"AG5: {ref(r)} attaches to {ref(g)} from outside {prof.routes_ns}")
            if any(not p.get("sectionName") for p in parents(r, g)):
                out.append(f"AG5: {ref(r)} attaches to {ref(g)} without sectionName (it would bind every listener)")
            for name in sorted({named[b] for b in backend_refs(r) if b in named}):
                allowed = PROVIDER_LISTENERS[name]
                if not listeners_of(r, g) <= allowed:
                    out.append(f"AG5: {ref(r)} reaches {name} from {sorted(listeners_of(r, g))}; "
                               f"{name} is {'/'.join(sorted(allowed))}-only")
            for rule in spec_of(r).get("rules") or []:
                refs = rule.get("backendRefs") or []
                if len(refs) > 1 and any(b.get("kind") == "AgentgatewayBackend" for b in refs):
                    out.append(f"AG5: {ref(r)} rule {rule.get('name')} splits traffic; a rule sends to one backend")
    return out


def check_zai_provider(objs):
    out = []
    for b in kind(objs, "AgentgatewayBackend"):
        if is_zai(b) and any("custom" not in p for p in providers(b)):
            out.append(f"AG5: {ref(b)} serves Z.ai without provider.custom (1.6: openai is for the OpenAI API only)")
    return out


def check_mcp_authz(objs):
    out = []
    for g, prof in profiled(objs):
        grammar = alternative(prof)
        for p in policies(objs):
            authz = ((spec_of(p).get("backend") or {}).get("mcp") or {}).get("authorization")
            names = {t.get("name") for t in spec_of(p).get("targetRefs") or [] if t.get("kind") in ROUTE_KINDS}
            routes = [r for r in routes_on(objs, g) if meta(r).get("name") in names
                      and meta(r).get("namespace") == meta(p).get("namespace")]
            if authz is None or not routes:
                continue
            classes = {s for r in routes for s in listeners_of(r, g)}
            if authz.get("action") != "Allow":
                out.append(f"AG6: {ref(p)} MCP authorization must be an Allow list (deny by default)")
            for e in (authz.get("policy") or {}).get("matchExpressions") or []:
                m = grammar.match(e.strip())
                if "||" in e or not m:
                    out.append(f"AG6: {ref(p)} expression is not one complete alternative: {e}")
                elif m.group("cls") not in classes:
                    out.append(f"AG6: {ref(p)} grants a {m.group('cls')} audience on {sorted(classes)} routes: {e}")
    return out


def exact_models_rules(route):
    return {rule.get("name") for rule in spec_of(route).get("rules") or []
            if any(m.get("path") == {"type": "Exact", "value": "/v1/models"} for m in rule.get("matches") or [])}


def check_models_list(objs):
    out = []
    llm = {key(b) for b in kind(objs, "AgentgatewayBackend") if providers(b)}
    for g, _ in profiled(objs):
        routes = routes_on(objs, g)
        llm_listeners = {s for r in routes if backend_refs(r) & llm for s in listeners_of(r, g)}
        answered = set()
        for p in policies(objs):
            if ((spec_of(p).get("traffic") or {}).get("directResponse") or {}).get("status") != 404:
                continue
            for t in spec_of(p).get("targetRefs") or []:
                for r in routes:
                    if t.get("kind") not in ROUTE_KINDS or t.get("name") != meta(r).get("name") \
                            or meta(p).get("namespace") != meta(r).get("namespace"):
                        continue
                    rules = exact_models_rules(r)
                    if rules and (t.get("sectionName") is None or t.get("sectionName") in rules):
                        answered |= listeners_of(r, g)
        for listener in sorted(llm_listeners - answered):
            out.append(f"AG7: {ref(g)} listener {listener} serves an LLM route but no Exact /v1/models "
                       "404 direct response")
    return out


def ratelimit_configs(objs):
    configs = {}
    for cm in kind(objs, "ConfigMap"):
        raw = (cm.get("data") or {}).get("config.yaml")
        if not raw:
            continue
        try:
            cfg = yaml.safe_load(raw)
        except yaml.YAMLError:
            continue
        if isinstance(cfg, dict) and cfg.get("domain") and isinstance(cfg.get("descriptors"), list):
            configs[cfg["domain"]] = (cm, cfg)
    return configs


def required_claims(objs, policy):
    """Claims that every listener the policy covers refuses a token without (#3523's workaround)."""
    sets = []
    for g, prof in profiled(objs):
        sections = gateway_targets(policy, g)
        listeners = set(prof.listeners) if None in sections else set(sections)
        for p in policies(objs):
            jwt = (spec_of(p).get("traffic") or {}).get("jwtAuthentication")
            if jwt is None or not listeners & set(gateway_targets(p, g)):
                continue
            sets += [set((prov.get("validation") or {}).get("requiredClaims") or [])
                     | ({"aud"} if prov.get("audiences") else set())
                     for prov in jwt.get("providers") or []]
    return set.intersection(*sets) if sets else set()


def unrequired_reads(expr, required):
    """What a key expression reads beyond the required claims: a claim, or any other variable."""
    claims = set(re.findall(r'\bjwt\s*\[\s*"([^"]+)"\s*\]', expr)) | set(re.findall(r"\bjwt\.(\w+)", expr))
    rest = re.sub(r'\bjwt\s*\[\s*"[^"]*"\s*\]|\bjwt\.\w+', "", expr)
    rest = re.sub(r'"(?:[^"\\]|\\.)*"' + r"|'(?:[^'\\]|\\.)*'", "", rest)
    roots = {m.group(1) for m in re.finditer(r"(?<![\w.])([A-Za-z_]\w*)\b(?!\s*\()", rest)}
    bound = set(re.findall(r"\.(?:all|exists|exists_one|map|filter)\(\s*(\w+)\s*,", rest))
    return sorted(claims - required) + sorted(roots - bound - {"true", "false", "null"})


def mounting_servers(objs, cm):
    """Deployments in the ConfigMap's namespace that mount it: its rate-limit servers."""
    return [d for d in kind(objs, "Deployment") if meta(d).get("namespace") == meta(cm).get("namespace")
            and any((v.get("configMap") or {}).get("name") == meta(cm).get("name")
                    for v in ((spec_of(d).get("template") or {}).get("spec") or {}).get("volumes") or [])]


def server_modes(server):
    """Each container's SHADOW_MODE, None where it is unset (the server then enforces)."""
    containers = ((spec_of(server).get("template") or {}).get("spec") or {}).get("containers") or []
    return [next((e.get("value") for e in c.get("env") or [] if e.get("name") == "SHADOW_MODE"), None)
            for c in containers]


def factory_values(objs):
    cm = next((c for c in kind(objs, "ConfigMap")
               if meta(c).get("namespace") == FACTORY_NS and meta(c).get("name") == FACTORY_VALUES), None)
    if cm is None:
        return None
    return (yaml.load((cm.get("data") or {}).get("values.yaml") or "", Loader=YAML_LOADER) or {}).get("config") or {}


def factory_floors(cfg):
    """The smallest B1 and B2 that never refuse before the factory: (run, fleet) in reference tokens."""
    tiers = [t for t in (cfg.get("tiers") or {}).values() if isinstance(t, dict)]
    run = max((max(round(t.get("runUSD", 0) * 1e6 / REF_USD_PER_M), t.get("runTokens", 0)) for t in tiers), default=0)
    fleet = (cfg.get("budgets") or {}).get("factoryDaily", 0) + (cfg.get("caps") or {}).get("concurrentRuns", 0) * run
    return run, fleet


def raw_run_ceiling(objs, cfg):
    """The raw tokens of the largest run the factory admits (OD-8's floor).

    A tier without runUSD caps at runTokens counted at REF (agent-platform), so
    that is its USD cap. A model without a price falls back to runTokens."""
    prices = (cfg.get("meter") or {}).get("prices") or {}
    aliases = [((spec_of(b).get("policies") or {}).get("ai") or {}).get("modelAliases") or {}
               for b in kind(objs, "AgentgatewayBackend")]
    ceiling = 0
    for t in (cfg.get("tiers") or {}).values():
        if not isinstance(t, dict):
            continue
        name = t.get("model", "agent-default")
        served = {str(a[name]) for a in aliases if name in a} or set(prices)
        rates = [prices[m]["cacheRead"] for m in served
                 if isinstance(prices.get(m), dict) and isinstance(prices[m].get("cacheRead"), (int, float))
                 and prices[m]["cacheRead"] > 0]
        usd = t.get("runUSD", t.get("runTokens", 0) * REF_USD_PER_M / 1e6)
        ceiling = max(ceiling, t.get("runTokens", 0), round(usd * 1e6 / min(rates)) if rates else 0)
    return ceiling


def check_budgets(objs):
    out = []
    configs = ratelimit_configs(objs)
    for p in policies(objs):
        rate_limit = (spec_of(p).get("traffic") or {}).get("rateLimit") or {}
        required = required_claims(objs, p)
        for lim in rate_limit.get("local") or []:
            if "key" not in lim:
                out.append(f"AG8: {ref(p)} local limit has no key: every caller would share one bucket")
            elif extra := unrequired_reads(lim["key"], required):
                out.append(f"AG8: {ref(p)} local key reads {extra}, which the JWT policy does not require: "
                           "an unevaluable key falls into one shared bucket (#3523)")
            # Only the real router serves runs; the PoC's limits are test values.
            serves_runs = any(prof.required and gateway_targets(p, g) for g, prof in profiled(objs))
            factory = factory_values(objs)
            if serves_runs and factory is not None and lim.get("tokens", 0) < (floor := raw_run_ceiling(objs, factory)):
                out.append(f"AG8: {ref(p)} local limit is {lim.get('tokens', 0)} raw tokens, below the {floor} the "
                           "largest admitted run can spend: it refuses whatever SHADOW_MODE says")
        glob = rate_limit.get("global")
        if glob is None:
            continue
        if glob.get("failureMode") != "FailOpen":
            out.append(f"AG8: {ref(p)} must set failureMode FailOpen (a store outage must not stop agents)")
        domain = glob.get("domain")
        if domain not in configs:
            out.append(f"AG8: {ref(p)} domain {domain!r} has no rate-limit ConfigMap in the bundle")
            continue
        cm, cfg = configs[domain]
        servers = mounting_servers(objs, cm)
        if not servers:
            out.append(f"AG8: no rate-limit server mounts {ref(cm)}")
        modes = {m for s in servers for m in server_modes(s)}
        if len(modes) > 1 or modes - {"true", "false"}:
            out.append(f"AG8: every server mounting {ref(cm)} must set SHADOW_MODE, all \"true\" or all \"false\": "
                       f"got {sorted(map(str, modes))}")
        for d in cfg["descriptors"]:
            if "shadow_mode" in d:
                out.append(f"AG8: {ref(cm)} descriptor {d.get('key')} sets shadow_mode: SHADOW_MODE is the one switch")
        factory = factory_values(objs)
        if factory is None:
            out.append(f"AG8: no {FACTORY_NS}/{FACTORY_VALUES}: the budgets have no price table or caps to follow")
            continue
        cost = billable_cost((factory.get("meter") or {}).get("prices") or {})
        floors = dict(zip((RUN_BUCKET, FLEET_BUCKET), factory_floors(factory)))
        for d in cfg["descriptors"]:
            limit = (d.get("rate_limit") or {}).get("requests_per_unit", 0)
            if d.get("key") in floors and limit < floors[d["key"]]:
                out.append(f"AG8: {ref(cm)} bucket {d['key']} is {limit} reference tokens, below the factory's "
                           f"{floors[d['key']]}: the gateway would refuse first")
        rules = {d.get("key"): d for d in cfg["descriptors"]}
        for d in glob.get("descriptors") or []:
            if d.get("unit") != "Tokens":
                out.append(f"AG8: {ref(p)} descriptor must charge unit Tokens")
            elif d.get("cost") != cost:
                out.append(f"AG8: {ref(p)} Tokens descriptor must charge reference tokens at meter.prices: cost: {cost}")
            for entry in d.get("entries") or []:
                expr = entry.get("expression", "")
                if re.search(r"route|backend|request\.path", f"{entry.get('name', '')} {expr}"):
                    out.append(f"AG8: {ref(p)} descriptor entry {entry.get('name')} keys on a route; "
                               "buckets must be shared")
                if extra := unrequired_reads(expr, required):
                    out.append(f"AG8: {ref(p)} descriptor entry {entry.get('name')} reads {extra}, which the JWT "
                               "policy does not require: a descriptor whose CEL fails is dropped, unlimited (#3523)")
                if entry.get("name") not in rules:
                    out.append(f"AG8: {ref(p)} entry {entry.get('name')} has no descriptor in {ref(cm)}")
    return out


def check_parameters(objs):
    out = []
    for g, _ in profiled(objs):
        pref = (spec_of(g).get("infrastructure") or {}).get("parametersRef") or {}
        params = next((p for p in kind(objs, "AgentgatewayParameters")
                       if key(p) == (meta(g).get("namespace"), pref.get("name"))), None)
        if params is None or pref.get("kind") != "AgentgatewayParameters":
            out.append(f"AG9: {ref(g)} has no AgentgatewayParameters in {meta(g).get('namespace')}")
            continue
        s = spec_of(params)
        dep = (s.get("deployment") or {}).get("spec") or {}
        pod = (dep.get("template") or {}).get("spec") or {}
        container = next((c for c in pod.get("containers") or [] if c.get("name") == "agentgateway"), {})
        shutdown = {k: v for k, v in (s.get("shutdown") or {}).items() if k in SHUTDOWN}
        checks = [
            ((dep.get("replicas") or 0) >= 2, "2 replicas"),
            (((pod.get("securityContext") or {}).get("seccompProfile") or {}).get("type") == "RuntimeDefault",
             "pod seccompProfile RuntimeDefault"),
            (((container.get("securityContext") or {}).get("seccompProfile") or {}).get("type") == "RuntimeDefault",
             "container seccompProfile RuntimeDefault"),
            (bool(container.get("livenessProbe")), "a liveness probe"),
            (bool(((s.get("resources") or {}).get("limits") or {}).get("memory")), "a memory limit"),
            ((((s.get("service") or {}).get("spec") or {}).get("type")) == "ClusterIP", "service type ClusterIP"),
            (bool((s.get("podDisruptionBudget") or {}).get("spec")), "a PodDisruptionBudget"),
            (bool((s.get("image") or {}).get("digest")), "a digest-pinned image"),
            (shutdown == SHUTDOWN, f"shutdown {SHUTDOWN} (got {s.get('shutdown')})"),
        ]
        out += [f"AG9: {ref(params)} lacks {what}" for ok, what in checks if not ok]
    return out


def check_provider_paths(objs):
    out = []
    for b in kind(objs, "AgentgatewayBackend"):
        for prov in providers(b):
            if not prov.get("host"):
                continue
            formats = (prov.get("custom") or {}).get("formats") or []
            pathed = prov.get("path") or prov.get("pathPrefix") or (formats and all(f.get("path") for f in formats))
            if not pathed:
                out.append(f"AG11: {ref(b)} overrides host {prov['host']} without a path; 1.6 sends `/`")
        if not is_zai(b):
            continue
        routes = ((spec_of(b).get("policies") or {}).get("ai") or {}).get("routes") or {}
        if not routes:
            out.append(f"AG11: {ref(b)} serves Z.ai without typed policies.ai.routes (#3853)")
        for path, typ in routes.items():
            if typ in UNTYPED_ROUTES:
                out.append(f"AG11: {ref(b)} routes {path} as {typ}; Z.ai takes typed routes only (#3853)")
    return out


def ai_policy(spec):
    return (spec.get("policies") or {}).get("ai") or {}


def router_backends(objs):
    """(namespace, name) of every backend a route on a required Gateway (the agent router) sends to."""
    return {b for g, p in profiled(objs) if p.required for r in routes_on(objs, g) for b in backend_refs(r)}


def check_model_pinning(objs):
    out = []
    routed = router_backends(objs)
    for b in kind(objs, "AgentgatewayBackend"):
        provs = providers(b)
        if not provs:
            continue
        if len(provs) > 1:
            out.append(f"AG12: {ref(b)} has {len(provs)} providers; an agent name maps to one provider model")
        ai = ai_policy(spec_of(b))
        aliases = ai.get("modelAliases") or {}
        fixed = any(isinstance(v, dict) and v.get("model") for p in provs for v in p.values())
        if key(b) not in routed:
            if fixed and aliases:
                out.append(f"AG12: {ref(b)} fixes a provider model, which pre-empts every alias")
            elif not fixed and "*" not in aliases:
                out.append(f"AG12: {ref(b)} needs a fixed model or a `*` catch-all alias: a request could name "
                           "any model the key can buy")
            continue
        if fixed:
            out.append(f"AG12: {ref(b)} fixes a provider model, which replaces every requested name")
        wild = sorted(n for n in aliases if "*" in n)
        if wild:
            out.append(f"AG12: {ref(b)} aliases {wild}: a catch-all gives an unlisted name a model")
        if set(aliases) - set(wild) != set(AGENT_MODELS):
            out.append(f"AG12: {ref(b)} must alias exactly {list(AGENT_MODELS)}, got {sorted(aliases)}")
        xfm = {t.get("field"): t.get("expression") for t in ai.get("transformations") or []}
        if xfm.get("model") != MODEL_ALLOWLIST:
            out.append(f"AG12: {ref(b)} needs the `model` transformation {MODEL_ALLOWLIST!r} to refuse "
                       "unlisted names before any upstream call")
        for field in MODEL_MUTATIONS:
            if "model" in (ai.get(field) or {}):
                out.append(f"AG12: {ref(b)} sets model in {field}, which gives an unlisted name a model")
    for p in policies(objs):
        ai = (spec_of(p).get("backend") or {}).get("ai") or {}
        xfm = {t.get("field") for t in ai.get("transformations") or []}
        if ai.get("modelAliases") or "model" in xfm or any("model" in (ai.get(f) or {}) for f in MODEL_MUTATIONS):
            out.append(f"AG12: {ref(p)} maps model names; names live on the backend, where AG12 reads them")
    for o in objs:
        if (is_agentgateway(o) or o.get("kind") in ROUTE_KINDS) and removes(o, MODEL_HEADER):
            out.append(f"AG12: {ref(o)} removes {MODEL_HEADER}: the backend would then take the body's model "
                       "while AG14's rule judged the header")
    return out


def removes(node, header):
    """Whether any `remove` list under node names the header."""
    if isinstance(node, dict):
        return any((k == "remove" and isinstance(v, list) and header in [str(h).lower() for h in v])
                   or removes(v, header) for k, v in node.items())
    return isinstance(node, list) and any(removes(v, header) for v in node)


ALTERNATIVE = re.compile(r'\("(?P<aud>[^"]+)" in jwt\.aud && m in (?P<models>\[[^\]]*\])\)')


def model_rule_ok(expr, auds):
    """One model Require, exactly as gen-capabilities.py renders it: EFFECTIVE_MODEL bound to m, one
    `(aud in jwt.aud && m in [...])` alternative per audience, joined by ||, nothing before or after."""
    head, tail = f"{EFFECTIVE_MODEL}.with(m, ", ")"
    if not (expr.startswith(head) and expr.endswith(tail)):
        return False
    parts = expr[len(head):-len(tail)].split(" || ")
    found = [ALTERNATIVE.fullmatch(p) for p in parts]
    if not all(found) or sorted(m["aud"] for m in found) != sorted(auds):
        return False
    for alt in found:
        try:
            models = json.loads(alt["models"])
        except ValueError:  # a non-literal entry such as `m`, which would open the rule
            return False
        if not (isinstance(models, list) and models and all(isinstance(x, str) for x in models)
                and len(set(models)) == len(models) and set(models) <= set(AGENT_MODELS)):
            return False
    return True


def check_model_authz(objs):
    out = []
    llm = {key(b) for b in kind(objs, "AgentgatewayBackend") if providers(b)}
    tiers = ((factory_values(objs) or {}).get("tiers") or {}).values()
    pinned = sorted({t["model"] for t in tiers if isinstance(t, dict) and t.get("model")})
    for g, prof in profiled(objs):
        if not prof.required:
            continue
        if not pinned:
            out.append(f"AG14: no {FACTORY_NS}/{FACTORY_VALUES} tier pins a model: the rule on {ref(g)} cannot be "
                       "checked to hold every model the factory's tiers pin")
        if not any(None in gateway_targets(p, g) and ((spec_of(p).get("frontend") or {}).get("http") or {})
                   .get("maxBufferSize") for p in policies(objs)):
            out.append(f"AG14: no Gateway-scoped frontend policy on {ref(g)} sets http.maxBufferSize: the model rule "
                       "would read 2 MiB of a body the backend reads up to 32 MiB of")
        for r in routes_on(objs, g):
            covering = {}
            for p in policies(objs):
                authz = (spec_of(p).get("traffic") or {}).get("authorization")
                if authz is None or meta(p).get("namespace") != meta(r).get("namespace"):
                    continue
                for t in spec_of(p).get("targetRefs") or []:
                    if t.get("kind") == r.get("kind") and t.get("name") == meta(r).get("name"):
                        covering.setdefault(t.get("sectionName"), []).append((p, authz))
            answered = {t.get("sectionName") for p in policies(objs)
                        if "directResponse" in (spec_of(p).get("traffic") or {})
                        for t in spec_of(p).get("targetRefs") or []
                        if t.get("kind") == r.get("kind") and t.get("name") == meta(r).get("name")}
            for rule in spec_of(r).get("rules") or []:
                name = rule.get("name")
                if not backend_refs(r, {name}) & llm:
                    continue
                found = covering.get(name, []) + covering.get(None, [])
                if name in answered or None in answered:
                    for p, authz in found:
                        if "request.body" in json.dumps(authz):
                            out.append(f"AG14: {ref(p)} reads the body on {ref(r)} rule {name}, which a directResponse "
                                       "answers: its GET would be refused 403 before its 404")
                    continue
                for listener in sorted(listeners_of(r, g)):
                    if len(found) != 1:
                        out.append(f"AG14: {ref(r)} rule {name} on {listener} has {len(found)} route-level "
                                   "authorization policies, expected 1 (gen-capabilities.py renders it)")
                        continue
                    p, authz = found[0]
                    exprs = (authz.get("policy") or {}).get("matchExpressions") or []
                    if authz.get("action") != "Require" or sub_prefix(prof) not in exprs:
                        out.append(f"AG14: {ref(p)} must Require {sub_prefix(prof)}: the listener's rule, repeated")
                    rules = [e for e in exprs if e.startswith(EFFECTIVE_MODEL)]
                    if len(rules) != 1 or not model_rule_ok(rules[0], sorted(audiences(prof, listener))):
                        out.append(f"AG14: {ref(p)} needs one model Require over {EFFECTIVE_MODEL} with an alternative "
                                   f"for each of {sorted(audiences(prof, listener))}")
                        continue
                    for alt in ALTERNATIVE.finditer(rules[0]):
                        missing = [x for x in pinned if x not in json.loads(alt["models"])]
                        if missing:
                            out.append(f"AG14: {ref(p)} refuses {missing} to {alt['aud']}, which the factory's tiers "
                                       "pin: every such run would be refused at its first call")
    return out


def is_github(backend):
    host = str((spec_of(backend).get("static") or {}).get("host", "")).lower()
    return host == "github.com" or host.endswith((".github.com", ".githubusercontent.com"))


def check_github_route(objs):
    out = []
    github = {key(b): b for b in kind(objs, "AgentgatewayBackend") if is_github(b)}
    for b in github.values():
        pol = spec_of(b).get("policies") or {}
        if "tls" not in pol:
            out.append(f"AG13: {ref(b)} dials GitHub without TLS")
        if set(pol) - {"tls"}:
            out.append(f"AG13: {ref(b)} carries {sorted(set(pol) - {'tls'})}: the GitHub route forwards no credential")
    routes = [r for r in objs if r.get("kind") in ROUTE_KINDS and backend_refs(r) & set(github)]
    targeted = {(meta(r).get("namespace"), r.get("kind"), meta(r).get("name")) for r in routes} | \
               {(ns, "AgentgatewayBackend", name) for ns, name in github}
    for p in policies(objs):
        for t in spec_of(p).get("targetRefs") or []:
            if (meta(p).get("namespace"), t.get("kind"), t.get("name")) in targeted:
                out.append(f"AG13: {ref(p)} is a policy on the GitHub route or backend; it could add a credential "
                           "or a write")
    for r in routes:
        sections = {p.get("sectionName") for p in spec_of(r).get("parentRefs") or []}
        if not sections or not sections <= GITHUB_LISTENERS:
            out.append(f"AG13: {ref(r)} reaches GitHub from {sorted(map(str, sections))}; it is internal-only")
        for rule in spec_of(r).get("rules") or []:
            for m in rule.get("matches") or [{}]:
                if m not in GITHUB_READ_MATCHES:
                    out.append(f"AG13: {ref(r)} rule {rule.get('name')} match {m} is not a read-only fetch "
                               "of an opted-in repository")
            removed = {h.lower() for f in rule.get("filters") or [] if f.get("type") == "RequestHeaderModifier"
                       for h in (f.get("requestHeaderModifier") or {}).get("remove") or []}
            if not set(GITHUB_STRIPPED) <= removed:
                out.append(f"AG13: {ref(r)} rule {rule.get('name')} must remove {', '.join(GITHUB_STRIPPED)} "
                           "(Authorization reaches GitHub otherwise)")
    return out


def pinned_models(backend):
    """The provider models a backend can send to: its alias targets and any fixed model."""
    aliases = ((spec_of(backend).get("policies") or {}).get("ai") or {}).get("modelAliases") or {}
    fixed = {v["model"] for p in providers(backend) for v in p.values() if isinstance(v, dict) and v.get("model")}
    return sorted({str(m) for m in aliases.values()} | fixed)


def check_meter_prices(objs):
    pins = [(b, m) for b in kind(objs, "AgentgatewayBackend") for m in pinned_models(b)]
    if not pins:
        return []
    factory = factory_values(objs)
    if factory is None:
        return [f"AG10: no ConfigMap {FACTORY_NS}/{FACTORY_VALUES} beside the LLM backends: no run would be priced"]
    out = []
    meter = factory.get("meter") or {}
    if "gen_ai_request_model" not in str(meter.get("query", "")):
        out.append("AG10: meter.query does not group by gen_ai_request_model: a run would be priced by "
                   "its agent name, whatever model served it")
    prices = meter.get("prices") or {}
    for b, model in pins:
        row = prices.get(model)
        if not isinstance(row, dict):
            out.append(f"AG10: {ref(b)} pins {model}, which has no meter.prices row")
            continue
        fields = PRICE_FIELDS + (("cacheWrite",) if is_anthropic(b) else ())
        for f in fields:
            v = row.get(f)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or v <= 0:
                out.append(f"AG10: meter.prices.{model} ({ref(b)}) needs a positive {f}")
    return out


CHECKS = (check_gateway, check_listener_identity, check_strip, check_token_isolation, check_routes,
          check_zai_provider, check_mcp_authz, check_models_list, check_budgets, check_parameters,
          check_meter_prices, check_provider_paths, check_model_pinning, check_github_route, check_model_authz)


def run(objs):
    """Violations for one cluster's objects, each starting with its check id."""
    return list(dict.fromkeys(v for check in CHECKS for v in check(objs)))


def is_agentgateway(obj):
    return str(obj.get("apiVersion", "")).startswith(API_GROUP + "/") or (
        obj.get("kind") == "Gateway" and spec_of(obj).get("gatewayClassName") == CLASS)


def load_clusters(bundle_dir):
    """Objects per cluster, from the renders whose file name carries one (base renders repeat them)."""
    clusters = {}
    for path in sorted(pathlib.Path(bundle_dir).glob("*.yaml")):
        m = CLUSTER.search(path.name)
        if not m:
            continue
        for doc in yaml.load_all(path.read_text(), Loader=YAML_LOADER):
            if isinstance(doc, dict) and doc.get("kind"):
                clusters.setdefault(m.group(1), []).append(doc)
    return clusters


def main(argv):
    bundle = pathlib.Path(argv[1] if len(argv) > 1 else ".bundle")
    if not bundle.is_dir():
        print(f"error: bundle directory {bundle} not found; run render-bundle.py first", file=sys.stderr)
        return 2
    in_scope = {c: objs for c, objs in load_clusters(bundle).items() if any(map(is_agentgateway, objs))}
    if in_scope:
        violations = [f"{v.split(':', 1)[0]}: [{c}]{v.split(':', 1)[1]}"
                      for c, objs in sorted(in_scope.items()) for v in run(objs)]
    else:
        violations = [f"AG1: no agentgateway object in any cluster's render (a vacuous pass is N10)"]
    for v in violations:
        print(f"FAIL {v}", file=sys.stderr)
    print(f"assert-agent-gateway: {len(CHECKS)} checks, {len(violations)} violations "
          f"(clusters: {', '.join(sorted(in_scope)) or 'none'})")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
