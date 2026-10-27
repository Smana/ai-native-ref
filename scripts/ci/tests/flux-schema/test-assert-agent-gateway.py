#!/usr/bin/env python3
"""Tests for assert-agent-gateway.py, the agentgateway agent router's cross-object gate.

Each invariant is pinned both ways: the compliant bundle passes, and each way of
breaking it fails with a message naming the check.

Run: python3 scripts/ci/tests/flux-schema/test-assert-agent-gateway.py
"""
import contextlib
import copy
import datetime
import importlib.util
import io
import pathlib
import sys
import tempfile

import yaml

HERE = pathlib.Path(__file__).resolve().parent
SUBJECT_DIR = HERE.parent.parent / "flux-schema"
sys.path.insert(0, str(SUBJECT_DIR))
spec = importlib.util.spec_from_file_location("assert_agent_gateway", SUBJECT_DIR / "assert-agent-gateway.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

FAILURES = []
REAL = ("agent-gateway", "agent-router")
POC = ("agw-poc", "agent-router-agw")
B6 = 'jwt.aud.exists(a, a.endsWith(".internal")) ? "anthropic" : "none"'
ZAI_PAGE = {"source": "https://docs.z.ai/guides/overview/pricing", "checkedAt": "2026-10-16"}
CLAUDE_PAGE = {"source": "https://platform.claude.com/docs/en/about-claude/pricing", "checkedAt": "2026-10-16"}
PRICES = {"glm-5.3": {"input": 1.40, "cacheRead": 0.26, "output": 4.40, **ZAI_PAGE},
          "glm-5.3-flash": {"input": 0.15, "cacheRead": 0.03, "output": 0.50, **ZAI_PAGE},
          "claude-opus-5-5": {"input": 4, "cacheRead": 0.20, "cacheWrite": 5, "output": 20, **CLAUDE_PAGE},
          "claude-haiku-5-5": {"input": 0.50, "cacheRead": 0.05, "cacheWrite": 0.625, "output": 2.50, **CLAUDE_PAGE}}
COST = gate.billable_cost(PRICES)


def check(name, condition, detail=""):
    print(f"  {'ok  ' if condition else 'FAIL'} {name}{'' if condition or not detail else ' -- ' + detail}")
    if not condition:
        FAILURES.append(name)


def obj(kind, ns, name, spec, api="agentgateway.dev/v1alpha1"):
    return {"apiVersion": api, "kind": kind, "metadata": {"namespace": ns, "name": name}, "spec": spec}


def agent_aliases(model):
    return {name: model for name in gate.AGENT_MODELS}


def model_rule(prof, listener, auds=None):
    """A P2 model rule as gen-capabilities.py renders it: one alternative per audience."""
    alts = " || ".join(f'("{a}" in jwt.aud && m in ["agent-default"])'
                       for a in (auds if auds is not None else sorted(gate.audiences(prof, listener))))
    return f"{gate.EFFECTIVE_MODEL}.with(m, {alts})"


def argument(prof, listener, value="secret"):
    """A P3 argument rule as gen-capabilities.py renders it."""
    return (f'!("{prof.aud_prefix}.reviewer.{listener}" in jwt.aud && default(mcp.tool.target, "") == "room-broker"'
            f' && default(mcp.tool.name, "") == "room_read") || default(mcp.tool.arguments.kind, "").lowerAscii() != "{value}"')


def compliant(key=REAL):
    gw_ns, gw_name = key
    prof = gate.PROFILES[key]
    rns = prof.routes_ns
    gw_ref = {"group": "gateway.networking.k8s.io", "kind": "Gateway", "name": gw_name}

    def listener_policy(section):
        jwt = {"mode": "Strict", "providers": [{
            "issuer": "https://issuer.example", "audiences": sorted(gate.audiences(prof, section)),
            "jwks": {"remote": {"url": "https://issuer.example/jwks"}},
            "validation": {"requiredClaims": ["exp", "sub"]}}]}
        if section == "sts":
            jwt["preserveToken"] = True
        return obj("AgentgatewayPolicy", gw_ns, f"listener-{section}", {
            "targetRefs": [dict(gw_ref, sectionName=section)],
            "traffic": {"jwtAuthentication": jwt,
                        "authorization": {"action": "Require",
                                          "policy": {"matchExpressions": [gate.sub_prefix(prof)]}},
                        "transformation": {"request": {"set": [{"name": "x-ar-agent", "value": "jwt.sub"}]}}}})

    def route(name, section, rules):
        return obj("HTTPRoute", rns, name, {
            "parentRefs": [dict(gw_ref, namespace=gw_ns, sectionName=section)], "rules": rules},
            api="gateway.networking.k8s.io/v1")

    def backend_ref(name):
        return [{"group": "agentgateway.dev", "kind": "AgentgatewayBackend", "name": name, "namespace": "agent-system"}]

    selector = ({"from": "Same"} if rns == gw_ns else
                {"from": "Selector", "selector": {"matchLabels": {"kubernetes.io/metadata.name": rns}}})
    allow = f'"{prof.aud_prefix}.implementer.public" in jwt.aud && mcp.tool.target == "room-broker"'
    return [
        obj("Gateway", gw_ns, gw_name, {
            "gatewayClassName": "agentgateway",
            "listeners": [{"name": n, "port": p, "protocol": "HTTP", "allowedRoutes": {"namespaces": selector}}
                          for n, p in prof.listeners.items()],
            "infrastructure": {"parametersRef": {"group": "agentgateway.dev", "kind": "AgentgatewayParameters",
                                                 "name": gw_name}}}, api="gateway.networking.k8s.io/v1"),
        obj("AgentgatewayParameters", gw_ns, gw_name, {
            "image": {"digest": "sha256:" + "0" * 64}, "shutdown": {"min": 10, "max": 660},
            "resources": {"limits": {"cpu": "1", "memory": "1Gi"}},
            "service": {"spec": {"type": "ClusterIP"}}, "podDisruptionBudget": {"spec": {"minAvailable": 1}},
            "deployment": {"spec": {"replicas": 2, "template": {"spec": {
                "securityContext": {"seccompProfile": {"type": "RuntimeDefault"}},
                "containers": [{"name": "agentgateway",
                                "securityContext": {"seccompProfile": {"type": "RuntimeDefault"}},
                                "livenessProbe": {"httpGet": {"path": "/healthz/ready", "port": 15021}}}]}}}}}),
        obj("AgentgatewayPolicy", gw_ns, "frontend", {
            "targetRefs": [gw_ref], "frontend": {"http": {"maxBufferSize": "8Mi"}}}),
        obj("AgentgatewayPolicy", gw_ns, "strip-identity-headers", {
            "targetRefs": [gw_ref],
            "traffic": {"phase": "PreRouting",
                        "transformation": {"request": {"remove": list(gate.IDENTITY_HEADERS)}}}}),
        *[listener_policy(s) for s in prof.listeners],
        obj("AgentgatewayBackend", "agent-system", "zai", {
            "ai": {"provider": {"custom": {"formats": [
                {"type": "Completions", "path": "/api/paas/v4/chat/completions"}]},
                "host": "api.z.ai", "port": 443}},
            "policies": {"auth": {"secretRef": {"name": "zai-api-key", "key": "apiKey"}},
                         "ai": {"routes": {"/v1/chat/completions": "Completions", "/v1/messages": "Messages"},
                                "modelAliases": agent_aliases("glm-5.3"),
                                "transformations": [{"field": "model", "expression": gate.MODEL_ALLOWLIST}]}}}),
        obj("AgentgatewayBackend", "agent-system", "anthropic", {
            "ai": {"provider": {"anthropic": {}}},
            "policies": {"auth": {"secretRef": {"name": "anthropic-api-key", "key": "apiKey"}},
                         "ai": {"modelAliases": agent_aliases("claude-opus-5-5"),
                                "transformations": [{"field": "model", "expression": gate.MODEL_ALLOWLIST}]}}}),
        route("agent-models-internal", "internal", [
            {"name": "models", "matches": [{"path": {"type": "Exact", "value": "/v1/models"}}],
             "backendRefs": backend_ref("anthropic")},
            {"name": "openai", "matches": [{"path": {"type": "PathPrefix", "value": "/v1"}}],
             "backendRefs": backend_ref("anthropic")}]),
        obj("AgentgatewayPolicy", rns, "agent-models-list-internal", {
            "targetRefs": [{"group": "gateway.networking.k8s.io", "kind": "HTTPRoute", "name": "agent-models-internal",
                            "sectionName": "models"}],
            "traffic": {"directResponse": {"status": 404, "body": '{"error":"model listing is not served"}'}}}),
        route("agent-models", "public", [
            {"name": "models", "matches": [{"path": {"type": "Exact", "value": "/v1/models"}}],
             "backendRefs": backend_ref("zai")},
            {"name": "openai", "matches": [{"path": {"type": "PathPrefix", "value": "/v1"}}],
             "backendRefs": backend_ref("zai")}]),
        obj("AgentgatewayPolicy", rns, "agent-models-list", {
            "targetRefs": [{"group": "gateway.networking.k8s.io", "kind": "HTTPRoute", "name": "agent-models",
                            "sectionName": "models"}],
            "traffic": {"directResponse": {"status": 404, "body": '{"error":"model listing is not served"}'}}}),
        *[obj("AgentgatewayPolicy", rns, f"capabilities-{section}", {
            "targetRefs": [{"group": "gateway.networking.k8s.io", "kind": "HTTPRoute", "name": route_name,
                            "sectionName": "openai"}],
            "traffic": {"authorization": {"action": "Require", "policy": {"matchExpressions": [
                gate.sub_prefix(prof), model_rule(prof, section)]}}}})
          for section, route_name in (("internal", "agent-models-internal"), ("public", "agent-models"))],
        obj("AgentgatewayBackend", rns, "agent-mcp", {"mcp": {"sessionRouting": "Stateless", "targets": [
            {"name": "room-broker", "static": {
                "host": "room-broker.agent-system.svc.cluster.local", "port": 8090, "path": "/mcp",
                "protocol": "StreamableHTTP", "policies": {"auth": {"credentials": [
                    {"location": {"header": {"name": "x-room-mcp-key"}},
                     "secretRef": {"name": "room-broker-mcp-key", "key": "apiKey"}}]}}}}]}}),
        route("agent-mcp-public", "public", [{"matches": [{"path": {"type": "PathPrefix", "value": "/mcp"}}],
                                              "backendRefs": [{"group": "agentgateway.dev",
                                                               "kind": "AgentgatewayBackend", "name": "agent-mcp"}]}]),
        obj("AgentgatewayPolicy", rns, "agent-mcp-public", {
            "targetRefs": [{"group": "gateway.networking.k8s.io", "kind": "HTTPRoute", "name": "agent-mcp-public"}],
            "backend": {"mcp": {"authorization": {"action": "Allow", "policy": {"matchExpressions": [
                allow + ' && mcp.tool.name in ["room_read", "room_post"]',
                allow + ' && mcp.tool.name == "room_read"']}}}}}),
        obj("AgentgatewayPolicy", rns, "capabilities-mcp-public", {
            "targetRefs": [{"group": "gateway.networking.k8s.io", "kind": "HTTPRoute", "name": "agent-mcp-public"}],
            "traffic": {"authorization": {"action": "Require", "policy": {"matchExpressions": [
                gate.sub_prefix(prof), argument(prof, "public")]}}}}),
        obj("AgentgatewayBackend", rns, "github", {
            "static": {"host": "github.com", "port": 443}, "policies": {"tls": {"sni": "github.com"}}}),
        route("github-internal", "internal", [
            {"name": name, "matches": [copy.deepcopy(m)],
             "filters": [{"type": "RequestHeaderModifier",
                          "requestHeaderModifier": {"remove": list(gate.GITHUB_STRIPPED)}},
                         {"type": "URLRewrite", "urlRewrite": {"hostname": "github.com"}}],
             "backendRefs": [{"group": "agentgateway.dev", "kind": "AgentgatewayBackend", "name": "github"}]}
            for name, m in zip(("refs", "upload-pack"), gate.GITHUB_READ_MATCHES)]),
        obj("AgentgatewayPolicy", gw_ns, "token-budgets", {
            "targetRefs": [gw_ref],
            "traffic": {"rateLimit": {
                "global": {
                    "backendRef": {"name": "agent-ratelimit", "port": 8081}, "domain": "agent-router",
                    "failureMode": "FailOpen", "descriptors": [
                        {"entries": [{"name": "agent", "expression": "jwt.sub"}], "unit": "Tokens",
                         "cost": COST},
                        {"entries": [{"name": "fleet", "expression": '"agents"'}], "unit": "Tokens",
                         "cost": COST},
                        {"entries": [{"name": "provider", "expression": B6}], "unit": "Tokens",
                         "cost": COST}]},
                "local": [{"tokens": 40000000, "unit": "Hours", "key": "jwt.sub"}]}}}),
        {"apiVersion": "v1", "kind": "ConfigMap", "metadata": {"namespace": gw_ns, "name": "agent-ratelimit-config"},
         "data": {"config.yaml": yaml.safe_dump({"domain": "agent-router", "descriptors": [
             {"key": "agent", "rate_limit": {"unit": "day", "requests_per_unit": 5000000}},
             {"key": "fleet", "value": "agents", "rate_limit": {"unit": "day", "requests_per_unit": 41000000}},
             {"key": "provider", "value": "anthropic", "rate_limit": {"unit": "day", "requests_per_unit": 10000000}}]})}},
        {"apiVersion": "v1", "kind": "ConfigMap", "metadata": {"namespace": "agent-system", "name": gate.FACTORY_VALUES},
         "data": {"values.yaml": yaml.safe_dump({"config": {"meter": {
             "query": "sum by (ar_agent, gen_ai_request_model, gen_ai_token_type) (gen_ai_client_token_usage_sum)",
             "prices": PRICES},
             "tiers": {"light": {"model": "agent-default", "runTokens": 300000, "runUSD": 0.51},
                       "frontier": {"model": "agent-default", "runTokens": 4000000, "runUSD": 6.80}},
             "budgets": {"factoryDailyUSD": 42.50}, "caps": {"concurrentRuns": 4}}})}},
        {"apiVersion": "apps/v1", "kind": "Deployment", "metadata": {"namespace": gw_ns, "name": "agent-ratelimit"},
         "spec": {"template": {"spec": {
             "containers": [{"name": "ratelimit", "env": [{"name": "SHADOW_MODE", "value": "true"}]}],
             "volumes": [{"name": "config", "configMap": {"name": "agent-ratelimit-config"}}]}}}},
    ]


def find(objs, kind, name):
    return next(o for o in objs if o["kind"] == kind and o["metadata"]["name"] == name)


def spec_at(objs, kind, name, *path):
    node = find(objs, kind, name)["spec"]
    for key in path:
        node = node[key]
    return node


def expect(name, mutate, code, needle=""):
    objs = copy.deepcopy(compliant())
    mutate(objs)
    v = gate.run(objs)
    check(name, any(x.startswith(code) and needle in x for x in v), f"got {v}")


def jwt_of(o, listener):
    return spec_at(o, "AgentgatewayPolicy", f"listener-{listener}", "traffic", "jwtAuthentication")


def zai(o):
    return find(o, "AgentgatewayBackend", "zai")["spec"]


def params(o):
    return spec_at(o, "AgentgatewayParameters", "agent-router")


print("compliant bundles")
got = gate.run(compliant(REAL))
check("compliant agent-gateway/agent-router passes", got == [], f"got {got}")
got = gate.run(compliant(REAL) + compliant(POC))
check("the PoC beside the real Gateway passes", got == [], f"got {got}")
check("fifteen checks", len(gate.CHECKS) == 15, f"got {len(gate.CHECKS)}")

print("AG1 gateway")
expect("no Gateway fails", lambda o: o.remove(find(o, "Gateway", "agent-router")), "AG1")
expect("a dropped listener fails", lambda o: spec_at(o, "Gateway", "agent-router", "listeners").pop(), "AG1")
expect("routes from All fails", lambda o: spec_at(o, "Gateway", "agent-router", "listeners")[0]
       ["allowedRoutes"].update({"namespaces": {"from": "All"}}), "AG1")
got = gate.run(compliant(POC))
check("the PoC without the real Gateway fails AG1",
      any(v.startswith("AG1: required Gateway agent-gateway/agent-router") for v in got), f"got {got}")
expect("an unknown agentgateway Gateway fails", lambda o: o.append(
    obj("Gateway", "elsewhere", "shadow", {"gatewayClassName": "agentgateway", "listeners": []},
        api="gateway.networking.k8s.io/v1")), "AG1")

print("AG2 listener identity")
expect("a missing listener policy fails", lambda o: o.remove(find(o, "AgentgatewayPolicy", "listener-internal")), "AG2")
expect("an internal audience on public fails", lambda o: jwt_of(o, "public")["providers"][0]["audiences"]
       .append("agent-router.implementer.internal"), "AG2")
expect("Allow instead of Require fails", lambda o: spec_at(o, "AgentgatewayPolicy", "listener-public", "traffic",
                                                           "authorization").update({"action": "Allow"}), "AG2")
expect("no x-ar-agent set fails", lambda o: spec_at(o, "AgentgatewayPolicy", "listener-sts", "traffic")
       .pop("transformation"), "AG2")
expect("requiredClaims without sub fails", lambda o: jwt_of(o, "public")["providers"][0]["validation"]
       .update({"requiredClaims": ["exp"]}), "AG2")
expect("no validation (1.6 stores no default) fails", lambda o: jwt_of(o, "internal")["providers"][0]
       .pop("validation"), "AG2")

print("AG3 strip")
expect("a strip missing agent-session-id fails", lambda o: spec_at(
    o, "AgentgatewayPolicy", "strip-identity-headers", "traffic", "transformation", "request", "remove")
    .remove("agent-session-id"), "AG3")
expect("no PreRouting phase fails", lambda o: spec_at(o, "AgentgatewayPolicy", "strip-identity-headers", "traffic")
       .pop("phase"), "AG3")

print("AG4 token isolation")
expect("preserveToken on public fails", lambda o: jwt_of(o, "public").update({"preserveToken": True}), "AG4")
expect("no preserveToken on sts fails", lambda o: jwt_of(o, "sts").pop("preserveToken"), "AG4")
expect("an MCP key in Authorization fails", lambda o: spec_at(o, "AgentgatewayBackend", "agent-mcp", "mcp", "targets")[0]
       ["static"]["policies"]["auth"]["credentials"][0]["location"]["header"].update({"name": "Authorization"}), "AG4")
expect("auth.secretRef on an MCP target fails", lambda o: spec_at(o, "AgentgatewayBackend", "agent-mcp", "mcp", "targets")[0]
       ["static"]["policies"].update({"auth": {"secretRef": {"name": "k"}}}), "AG4")

print("AG5 routes and the Z.ai provider")
expect("no sectionName fails", lambda o: spec_at(o, "HTTPRoute", "agent-models", "parentRefs")[0].pop("sectionName"), "AG5")
expect("zai on internal fails", lambda o: spec_at(o, "HTTPRoute", "agent-models", "parentRefs")[0]
       .update({"sectionName": "internal"}), "AG5")
expect("route-level jwtAuthentication fails", lambda o: spec_at(o, "AgentgatewayPolicy", "agent-mcp-public")
       .update({"traffic": {"jwtAuthentication": {"mode": "Strict"}}}), "AG5")
expect("Z.ai on the openai provider fails", lambda o: zai(o)["ai"].update(
    {"provider": {"openai": {"model": "glm-5.3"}, "host": "api.z.ai", "port": 443, "path": "/api/paas/v4/chat/completions"}}), "AG5")


def rename_to_openai(o):
    b = find(o, "AgentgatewayBackend", "zai")
    b["metadata"]["name"] = "glm"
    provider = b["spec"]["ai"]["provider"]
    provider.pop("custom")
    provider.update({"openai": {}, "path": "/api/paas/v4/chat/completions"})


expect("a Z.ai backend found by host, not name, is judged", rename_to_openai, "AG5")

print("AG6 MCP authorization")


def add_expr(e):
    return lambda o: spec_at(o, "AgentgatewayPolicy", "agent-mcp-public", "backend", "mcp", "authorization", "policy",
                             "matchExpressions").append(e)


expect("a role-only expression fails", add_expr('"agent-router.reviewer.public" in jwt.aud'), "AG6")
expect("an || expression fails", add_expr('"agent-router.reviewer.public" in jwt.aud || mcp.tool.name == "room_post"'), "AG6")
expect("an internal audience on a public route fails", add_expr(
    '"agent-router.implementer.internal" in jwt.aud && mcp.tool.target == "room-broker" && mcp.tool.name in ["room_read"]'),
    "AG6")
expect("a Deny action fails", lambda o: spec_at(o, "AgentgatewayPolicy", "agent-mcp-public", "backend", "mcp",
                                                "authorization").update({"action": "Deny"}), "AG6")

print("AG7 /v1/models")
expect("no /v1/models answer fails", lambda o: o.remove(find(o, "AgentgatewayPolicy", "agent-models-list")), "AG7")
expect("a 404 on another rule fails", lambda o: spec_at(o, "AgentgatewayPolicy", "agent-models-list", "targetRefs")[0]
       .update({"sectionName": "openai"}), "AG7")

print("AG8 budgets")


def glob(o):
    return spec_at(o, "AgentgatewayPolicy", "token-budgets", "traffic", "rateLimit", "global")


def edit_rl(edit):
    def mutate(o):
        cm = find(o, "ConfigMap", "agent-ratelimit-config")
        cfg = yaml.safe_load(cm["data"]["config.yaml"])
        edit(cfg["descriptors"])
        cm["data"]["config.yaml"] = yaml.safe_dump(cfg)
    return mutate




expect("FailClosed fails", lambda o: glob(o).update({"failureMode": "FailClosed"}), "AG8")
expect("no explicit failureMode fails", lambda o: glob(o).pop("failureMode"), "AG8")
expect("a request-unit descriptor fails", lambda o: glob(o)["descriptors"][0].update({"unit": "Requests"}), "AG8")
expect("a route-keyed entry fails", lambda o: glob(o)["descriptors"][0]["entries"].append(
    {"name": "route", "expression": "request.path"}), "AG8")
expect("a descriptor with its own shadow_mode fails", edit_rl(lambda ds: ds[0].update({"shadow_mode": True})),
       "AG8", "one switch")
expect("a missing ConfigMap fails", lambda o: o.remove(find(o, "ConfigMap", "agent-ratelimit-config")), "AG8")


def server_env(o):
    return find(o, "Deployment", "agent-ratelimit")["spec"]["template"]["spec"]["containers"][0]["env"]


def local(o):
    return spec_at(o, "AgentgatewayPolicy", "token-budgets", "traffic", "rateLimit", "local")


print("AG8 SHADOW_MODE is the one switch (runbook 04, Part D)")
expect("a server without SHADOW_MODE fails", lambda o: server_env(o).clear(), "AG8", "SHADOW_MODE")
expect("a SHADOW_MODE that is not a boolean fails", lambda o: server_env(o)[0].update({"value": "${shadow}"}),
       "AG8", "SHADOW_MODE")


def second_server(mode):
    def mutate(o):
        twin = copy.deepcopy(find(o, "Deployment", "agent-ratelimit"))
        twin["metadata"]["name"] = "agent-ratelimit-2"
        twin["spec"]["template"]["spec"]["containers"][0]["env"][0]["value"] = mode
        o.append(twin)
    return mutate


expect("two servers that disagree fail", second_server("false"), "AG8", "all")
expect("no server reading the ConfigMap fails", lambda o: o.remove(find(o, "Deployment", "agent-ratelimit")),
       "AG8", "mounts")
got = copy.deepcopy(compliant())
server_env(got)[0].update({"value": "false"})
check("an enforcing server passes", gate.run(got) == [], f"got {gate.run(got)}")

print("AG8 buckets at or above the factory's caps (the gateway never refuses first)")
expect("B1 below the frontier run cap fails",
       edit_rl(lambda ds: ds[0]["rate_limit"].update({"requests_per_unit": 3999999})), "AG8", "refuse first")
expect("B2 below factoryDailyUSD plus the in-flight runs fails",
       edit_rl(lambda ds: ds[1]["rate_limit"].update({"requests_per_unit": 40999999})), "AG8", "fleet")

print("AG8 reference tokens (design D11, OD-6)")
expect("a Tokens descriptor without cost fails", lambda o: glob(o)["descriptors"][0].pop("cost"), "AG8",
       "reference tokens")
expect("a raw-token cost fails", lambda o: glob(o)["descriptors"][1].update({"cost": "llm.totalTokens"}), "AG8",
       "reference tokens")
expect("the catalog's price fails", lambda o: glob(o)["descriptors"][0].update(
    {"cost": "has(llm.cost) ? uint(llm.cost.total / 0.0000017) : uint(llm.totalTokens)"}), "AG8", "meter.prices")

print("AG8 required claims (#3523: a descriptor whose CEL fails is dropped, unlimited)")
expect("a descriptor reading an unrequired claim fails",
       lambda o: glob(o)["descriptors"][0]["entries"][0].update({"expression": "jwt.team"}), "AG8", "#3523")
expect("a descriptor reading a bracketed unrequired claim fails",
       lambda o: glob(o)["descriptors"][0]["entries"][0].update({"expression": 'jwt["team"]'}), "AG8", "#3523")
expect("a descriptor reading a header fails",
       lambda o: glob(o)["descriptors"][0]["entries"][0].update({"expression": 'request.headers["x-ar-agent"]'}),
       "AG8", "#3523")
expect("sub no longer required on one listener fails",
       lambda o: jwt_of(o, "sts")["providers"][0]["validation"].update({"requiredClaims": ["exp"]}), "AG8", "#3523")
expect("an unkeyed local token limit fails", lambda o: local(o)[0].pop("key"), "AG8", "key")
expect("a local key reading an unrequired claim fails", lambda o: local(o)[0].update({"key": "jwt.team"}),
       "AG8", "#3523")
got = gate.run([o if o["kind"] != "AgentgatewayPolicy" or o["metadata"]["name"] != "token-budgets" else
                {**o, "spec": {**o["spec"], "traffic": {"rateLimit": {**o["spec"]["traffic"]["rateLimit"], "global": {
                    **o["spec"]["traffic"]["rateLimit"]["global"], "descriptors": [
                        {"entries": [{"name": "agent", "expression": 'jwt["sub"].lowerAscii()'}], "unit": "Tokens",
                         "cost": COST}]}}}}}
                for o in compliant()])
check("a required claim read with a method call passes", got == [], f"got {got}")

print("AG9 parameters")
expect("a LoadBalancer Service fails", lambda o: params(o)["service"]["spec"].update({"type": "LoadBalancer"}), "AG9")
expect("the default drain fails", lambda o: params(o).update({"shutdown": {"min": 10, "max": 60}}), "AG9")
expect("N1's old min 120 fails", lambda o: params(o).update({"shutdown": {"min": 120, "max": 660}}), "AG9")
expect("no shutdown (1.6 stores no default) fails", lambda o: params(o).pop("shutdown"), "AG9")
expect("no liveness probe fails", lambda o: params(o)["deployment"]["spec"]["template"]["spec"]["containers"][0]
       .pop("livenessProbe"), "AG9")
expect("a tag-only image fails", lambda o: params(o).update({"image": {"tag": "v1.6.0"}}), "AG9")

print("AG11 provider paths")
expect("a custom format without a path fails", lambda o: zai(o)["ai"]["provider"]["custom"]["formats"][0].pop("path"), "AG11")
expect("a host-overridden openai provider without a path fails", lambda o: o.append(obj(
    "AgentgatewayBackend", "agent-system", "proxy", {"ai": {"provider": {"openai": {}, "host": "llm.example", "port": 443}}})),
    "AG11")
expect("a Z.ai Detect route fails", lambda o: zai(o)["policies"]["ai"]["routes"].update({"/v1": "Detect"}), "AG11")
expect("a Z.ai Passthrough route fails", lambda o: zai(o)["policies"]["ai"]["routes"].update({"/v1/x": "Passthrough"}), "AG11")
expect("a Z.ai backend without typed routes fails", lambda o: zai(o)["policies"].pop("ai"), "AG11")


print("AG5 each provider on its own listener (ADR-0054), each rule on one backend")
expect("anthropic on public fails", lambda o: spec_at(o, "HTTPRoute", "agent-models-internal", "parentRefs")[0]
       .update({"sectionName": "public"}), "AG5", "Anthropic")


def anthropic_by_host(o):
    b = find(o, "AgentgatewayBackend", "anthropic")
    b["metadata"]["name"] = "claude"
    b["spec"]["ai"]["provider"] = {"custom": {"formats": [{"type": "Messages", "path": "/v1/messages"}]},
                                   "host": "api.anthropic.com", "port": 443}
    for rule in spec_at(o, "HTTPRoute", "agent-models-internal", "rules"):
        rule["backendRefs"][0]["name"] = "claude"
    spec_at(o, "HTTPRoute", "agent-models-internal", "parentRefs")[0].update({"sectionName": "public"})


expect("an Anthropic backend found by host, not provider, is judged", anthropic_by_host, "AG5", "Anthropic")
expect("a rule split across two backends fails", lambda o: spec_at(o, "HTTPRoute", "agent-models", "rules")[1]
       ["backendRefs"].append({"group": "agentgateway.dev", "kind": "AgentgatewayBackend", "name": "zai-b",
                               "weight": 10}), "AG5", "one backend")

print("AG7 /v1/models on internal")
expect("no /v1/models answer on internal fails",
       lambda o: o.remove(find(o, "AgentgatewayPolicy", "agent-models-list-internal")), "AG7", "internal")

print("AG12 model pinning (design D8)")


def anthropic_spec(o):
    return find(o, "AgentgatewayBackend", "anthropic")["spec"]


def zai_ai(o):
    return zai(o)["policies"]["ai"]


expect("a provider model beside aliases fails", lambda o: anthropic_spec(o)["ai"]["provider"]["anthropic"]
       .update({"model": "claude-opus-5-5"}), "AG12", "replaces every requested name")
expect("a `*` catch-all alias fails", lambda o: zai_ai(o)["modelAliases"].update({"*": "glm-5.3"}),
       "AG12", "catch-all")
expect("a glob alias fails", lambda o: zai_ai(o)["modelAliases"].update({"claude-*": "glm-5.3"}),
       "AG12", "catch-all")
expect("an unlisted name fails", lambda o: zai_ai(o)["modelAliases"].update({"gpt-4o": "glm-5.3"}),
       "AG12", "exactly")
expect("a missing agent name fails", lambda o: zai_ai(o)["modelAliases"].pop("tier-frontier"), "AG12", "exactly")
expect("no aliases fails", lambda o: anthropic_spec(o)["policies"].pop("ai"), "AG12", "exactly")
expect("no model allowlist fails", lambda o: zai_ai(o).pop("transformations"), "AG12", "refuse")
expect("a model transformation that passes every name fails", lambda o: zai_ai(o)["transformations"][0]
       .update({"expression": "llmRequest.model"}), "AG12", "refuse")
expect("a model override fails", lambda o: zai_ai(o).update({"overrides": {"model": "glm-5.3"}}), "AG12",
       "overrides")
expect("a model default fails", lambda o: zai_ai(o).update({"defaults": {"model": "glm-5.3"}}), "AG12",
       "defaults")
expect("a policy's catch-all alias fails", lambda o: o.append(obj("AgentgatewayPolicy", "agent-system", "aliases", {
    "targetRefs": [{"group": "agentgateway.dev", "kind": "AgentgatewayBackend", "name": "anthropic"}],
    "backend": {"ai": {"modelAliases": {"*": "claude-opus-5-5"}}}})), "AG12", "names live on the backend")
expect("provider groups fail", lambda o: anthropic_spec(o)["ai"].update(
    {"groups": [{"providers": [{"anthropic": {}}, {"anthropic": {}}]}]}), "AG12", "one provider")
poc = [o if o["kind"] != "AgentgatewayBackend" or o["metadata"]["name"] != "anthropic" else
       {**o, "spec": {"ai": {"provider": {"anthropic": {"model": "claude-opus-5-5"}}},
                      "policies": {"auth": o["spec"]["policies"]["auth"]}}} for o in compliant(POC)]
got = gate.check_model_pinning(poc)
check("a fixed model passes on a backend the agent router does not route to",
      not any("anthropic" in v for v in got), f"got {got}")
got = gate.check_model_pinning([o for o in poc if not (o["kind"] == "AgentgatewayBackend"
                                                       and o["metadata"]["name"] == "zai")] +
                               [{**find(poc, "AgentgatewayBackend", "zai"),
                                 "spec": {**zai(poc), "policies": {"ai": {"modelAliases": {"x": "glm-5.3"}}}}}])
check("off the agent router, aliases without a catch-all still fail", any("catch-all" in v for v in got),
      f"got {got}")

print("AG13 the read-only GitHub route (identity design T4)")


def github_rules(o):
    return spec_at(o, "HTTPRoute", "github-internal", "rules")


def github_parents(o):
    return spec_at(o, "HTTPRoute", "github-internal", "parentRefs")


expect("the GitHub route on public fails", lambda o: github_parents(o)[0].update({"sectionName": "public"}),
       "AG13", "internal")
expect("a second parent on sts fails", lambda o: github_parents(o).append(dict(github_parents(o)[0], sectionName="sts")),
       "AG13", "internal")
expect("a receive-pack POST fails", lambda o: github_rules(o)[1]["matches"][0]["path"].update(
    {"value": r"^/Smana/cloud-native-ref\.git/git-receive-pack$"}), "AG13", "read-only")
expect("a PathPrefix match fails", lambda o: github_rules(o)[0]["matches"].append(
    {"path": {"type": "PathPrefix", "value": "/Smana"}}), "AG13", "read-only")
expect("a match without a method fails", lambda o: github_rules(o)[1]["matches"][0].pop("method"), "AG13", "read-only")
expect("a receive-pack advertisement fails", lambda o: github_rules(o)[0]["matches"][0]["queryParams"][0].update(
    {"value": "git-receive-pack"}), "AG13", "read-only")
expect("another repository fails", lambda o: github_rules(o)[0]["matches"][0]["path"].update(
    {"value": r"^/Smana/[^/]+\.git/info/refs$"}), "AG13", "read-only")
expect("a rule that keeps Authorization fails", lambda o: github_rules(o)[0]["filters"].pop(0), "AG13", "Authorization")
expect("a credential on the GitHub backend fails", lambda o: spec_at(o, "AgentgatewayBackend", "github", "policies")
       .update({"auth": {"secretRef": {"name": "gh", "key": "token"}}}), "AG13", "credential")
expect("a policy on the GitHub route fails", lambda o: o.append(obj("AgentgatewayPolicy", "agent-system", "gh", {
    "targetRefs": [{"group": "gateway.networking.k8s.io", "kind": "HTTPRoute", "name": "github-internal"}],
    "traffic": {"headerModifiers": {"request": {"set": [{"name": "Authorization", "value": "token x"}]}}}})),
    "AG13", "policy")
expect("a policy on the GitHub backend fails", lambda o: o.append(obj("AgentgatewayPolicy", "agent-system", "gh", {
    "targetRefs": [{"group": "agentgateway.dev", "kind": "AgentgatewayBackend", "name": "github"}],
    "backend": {"auth": {"secretRef": {"name": "gh", "key": "token"}}}})), "AG13", "policy")
expect("a GitHub backend without TLS fails", lambda o: find(o, "AgentgatewayBackend", "github")["spec"].pop("policies"),
       "AG13", "TLS")
refs, pack = (m["path"]["value"] for m in gate.GITHUB_READ_MATCHES)
check("the refs regex takes the repository's advertisement path",
      all(gate.re.fullmatch(refs, f"/{r}.git/info/refs") for r in gate.REPOSITORIES))
check("the pack regex takes upload-pack only",
      gate.re.fullmatch(pack, "/Smana/cloud-native-ref.git/git-upload-pack") is not None
      and gate.re.fullmatch(pack, "/Smana/cloud-native-ref.git/git-receive-pack") is None)
check("no regex takes another repository or a traversal",
      not any(gate.re.fullmatch(r, p) for r in (refs, pack) for p in (
          "/Smana/other.git/info/refs", "/Smana/cloud-native-ref.git/../x/git-upload-pack",
          "/Smana/cloud-native-refXgit/info/refs", "/attacker/cloud-native-ref.git/git-upload-pack",
          "/Smana/xai-native-ref.git/info/refs", "/Smana/ai-native-ref.git/git-receive-pack")))

print("AG10 every pinned model has its price in the meter's overlay (plan J.1, J-AC4)")


def meter_cfg(o):
    return yaml.safe_load(find(o, "ConfigMap", gate.FACTORY_VALUES)["data"]["values.yaml"])["config"]["meter"]


def edit_config(edit):
    def mutate(o):
        cm = find(o, "ConfigMap", gate.FACTORY_VALUES)
        values = yaml.safe_load(cm["data"]["values.yaml"])
        edit(values["config"])
        cm["data"]["values.yaml"] = yaml.safe_dump(values)
    return mutate


def edit_meter(edit):
    return edit_config(lambda c: edit(c["meter"]))


print("AG8 the gateway follows the factory's values (J-AC2, never refusing first)")
expect("a meter price change the gateway's cost misses fails",
       edit_meter(lambda m: m["prices"]["glm-5.3"].update({"input": 1.50})), "AG8", "meter.prices")
fixture = yaml.safe_load(find(compliant(), "ConfigMap", gate.FACTORY_VALUES)["data"]["values.yaml"])["config"]
check("the fleet floor from factoryDailyUSD $42.50 is B2's 41M: 25M plus 4 frontier runs at 4M",
      gate.factory_floors(fixture) == (4000000, 41000000), f"got {gate.factory_floors(fixture)}")
expect("a raised factoryDailyUSD without B2 fails ($1.70 more is 1M more)",
       edit_config(lambda c: c["budgets"].update({"factoryDailyUSD": 44.20})), "AG8", "fleet")
expect("no factoryDailyUSD fails: the release's default is not in the values",
       edit_config(lambda c: c["budgets"].pop("factoryDailyUSD")), "AG8", "budgets.factoryDailyUSD")
expect("a zero factoryDailyUSD fails", edit_config(lambda c: c["budgets"].update({"factoryDailyUSD": 0})),
       "AG8", "budgets.factoryDailyUSD")
expect("an infinite factoryDailyUSD fails, not an OverflowError", edit_config(lambda c: c["budgets"].update({"factoryDailyUSD": float("inf")})),
       "AG8", "budgets.factoryDailyUSD")
expect("factoryDaily in tokens fails, naming its USD key",
       edit_config(lambda c: c["budgets"].update({"factoryDaily": 25000000})), "AG8", "Use budgets.factoryDailyUSD")
expect("humanDaily in tokens fails, naming its USD key",
       edit_config(lambda c: c["budgets"].update({"humanDaily": 5000000})), "AG8", "Use budgets.humanDailyUSD")
expect("perPerson.dailyTokens fails, naming its USD key",
       edit_config(lambda c: c["budgets"].update({"perPerson": {"enabled": True, "dailyTokens": 5000000}})),
       "AG8", "Use budgets.perPerson.dailyUSD")
got = copy.deepcopy(compliant())
edit_config(lambda c: c["budgets"].update({"humanDailyUSD": 8.50, "perPerson": {"enabled": True, "dailyUSD": 4.25}}))(got)
check("the USD person keys pass", gate.run(got) == [], f"got {gate.run(got)}")
expect("a local limit below an all-cache-read Opus run fails (34M)",
       lambda o: local(o)[0].update({"tokens": 30000000}), "AG8", "34000000")
poc = compliant(REAL) + compliant(POC)
next(o for o in poc if o["kind"] == "AgentgatewayPolicy" and o["metadata"]["namespace"] == POC[0]
     and o["metadata"]["name"] == "token-budgets")["spec"]["traffic"]["rateLimit"]["local"][0]["tokens"] = 200000
got = [v for v in gate.run(poc) if "local limit" in v]
check("the PoC's test-sized local limit passes (it serves no run)", got == [], f"got {got}")
expect("a tier's name reaching a cheaper cache rate without the local limit fails",
       lambda o: zai(o)["policies"]["ai"]["modelAliases"].update({"agent-default": "glm-5.3-flash"}),
       "AG8", "local limit")
expect("a dearer frontier tier without B1 fails",
       edit_config(lambda c: c["tiers"]["frontier"].update({"runUSD": 9})), "AG8", "agent")
print("AG10 every pinned model has its price in the meter's overlay (continued)")

expect("a pinned model without a price fails", edit_meter(lambda m: m["prices"].pop("claude-opus-5-5")),
       "AG10", "claude-opus-5-5")
expect("a price without its cache-read rate fails", edit_meter(lambda m: m["prices"]["glm-5.3"].pop("cacheRead")),
       "AG10", "cacheRead")
expect("an Anthropic price without its cache-write rate fails",
       edit_meter(lambda m: m["prices"]["claude-opus-5-5"].pop("cacheWrite")), "AG10", "cacheWrite")
expect("a zero output price fails", edit_meter(lambda m: m["prices"]["glm-5.3"].update({"output": 0})),
       "AG10", "output")
expect("a query not grouped by the served model fails",
       edit_meter(lambda m: m.update({"query": "sum by (ar_agent, gen_ai_token_type) (x)"})), "AG10",
       "gen_ai_request_model")
expect("a fixed provider model without a price fails", lambda o: (
    anthropic_spec(o)["policies"]["ai"].pop("modelAliases"),
    anthropic_spec(o)["ai"]["provider"]["anthropic"].update({"model": "claude-sonnet-5-5"})), "AG10", "claude-sonnet-5-5")
expect("no factory values beside the backends fails",
       lambda o: o.remove(find(o, "ConfigMap", gate.FACTORY_VALUES)), "AG10", gate.FACTORY_VALUES)
print("AG10 every row says where and when it was read (truthful costs TC1)")
for name, value in (("an http source", "http://docs.z.ai/guides/overview/pricing"),
                    ("a source without a host", "https:///pricing"),
                    ("a source with credentials", "https://u:p@docs.z.ai/guides/overview/pricing"),
                    ("a source that is not a URL", "docs.z.ai pricing")):
    expect(f"{name} fails", edit_meter(lambda m, v=value: m["prices"]["glm-5.3"].update({"source": v})),
           "AG10", "meter.prices.glm-5.3 needs source")
for name, value in (("no such month", "2026-13-01"), ("another layout", "16/10/2026"),
                    ("no dashes", "20261016"), ("a timestamp", "2026-10-16T00:00:00Z"),
                    ("an unquoted date, which YAML reads as a date", datetime.date(2026, 10, 16))):
    expect(f"checkedAt as {name} fails", edit_meter(lambda m, v=value: m["prices"]["glm-5.3"].update({"checkedAt": v})),
           "AG10", "meter.prices.glm-5.3 needs checkedAt")
expect("a row without source fails", edit_meter(lambda m: m["prices"]["claude-opus-5-5"].pop("source")),
       "AG10", "claude-opus-5-5 needs source")
expect("a row without checkedAt fails", edit_meter(lambda m: m["prices"]["claude-opus-5-5"].pop("checkedAt")),
       "AG10", "claude-opus-5-5 needs checkedAt")
expect("a row no backend pins needs them too: every row",
       edit_meter(lambda m: m["prices"].update({"glm-5.3-flashx": {"input": 0.37, "cacheRead": 0.075, "output": 1.25}})),
       "AG10", "glm-5.3-flashx needs source")
got = gate.run([o for o in compliant() if o["kind"] not in ("AgentgatewayBackend", "ConfigMap")
                or o["metadata"]["name"] != gate.FACTORY_VALUES and o["kind"] == "ConfigMap"])
check("no LLM backend, no factory values: AG10 has nothing to judge", not any(v.startswith("AG10") for v in got),
      f"got {got}")

print("AG8 B6 reads the verified audience")


def drop_b6_rule(o):
    cm = find(o, "ConfigMap", "agent-ratelimit-config")
    cfg = yaml.safe_load(cm["data"]["config.yaml"])
    cfg["descriptors"] = [d for d in cfg["descriptors"] if d["key"] != "provider"]
    cm["data"]["config.yaml"] = yaml.safe_dump(cfg)


expect("B6 without its descriptor in the ConfigMap fails", drop_b6_rule, "AG8", "provider")
expect("aud read where a covered listener checks no audience fails",
       lambda o: jwt_of(o, "sts")["providers"][0].pop("audiences"), "AG8", "aud")


def run_main(d):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = gate.main(["x", d])
    return code, out.getvalue() + err.getvalue()


print("AG12 the model header (capability profiles P4)")
expect("the strip removing x-ar-model fails", lambda o: spec_at(
    o, "AgentgatewayPolicy", "strip-identity-headers", "traffic", "transformation", "request", "remove")
    .append("X-AR-Model"), "AG12", "removes x-ar-model")
expect("a route filter removing x-ar-model fails", lambda o: spec_at(o, "HTTPRoute", "agent-models", "rules")[1]
       .update({"filters": [{"type": "RequestHeaderModifier", "requestHeaderModifier": {"remove": ["x-ar-model"]}}]}),
       "AG12", "removes x-ar-model")
expect("a transformation that ignores the header fails", lambda o: zai(o)["policies"]["ai"]["transformations"][0]
       .update({"expression": 'llmRequest.model in ["agent-default"] ? llmRequest.model : null'}), "AG12", "refuse")

def caps(o, listener):
    return spec_at(o, "AgentgatewayPolicy", f"capabilities-{listener}", "traffic", "authorization")


def second_policy(o):
    extra = copy.deepcopy(find(o, "AgentgatewayPolicy", "capabilities-public"))
    extra["metadata"]["name"] = "capabilities-public-copy"
    o.append(extra)


def tier_model(model):
    def change(o):
        cm = find(o, "ConfigMap", gate.FACTORY_VALUES)
        values = yaml.safe_load(cm["data"]["values.yaml"])
        values["config"]["tiers"]["frontier"]["model"] = model
        cm["data"]["values.yaml"] = yaml.safe_dump(values)
    return change


print("AG14 model authorization (capability profiles P2)")
gen_spec = importlib.util.spec_from_file_location("gen_capabilities", HERE.parent.parent / "gen-capabilities.py")
gen = importlib.util.module_from_spec(gen_spec)
gen_spec.loader.exec_module(gen)
check("EFFECTIVE_MODEL equals the generator's", gate.EFFECTIVE_MODEL == gen.EFFECTIVE_MODEL)
expect("an LLM rule with no authorization fails", lambda o: o.remove(find(o, "AgentgatewayPolicy", "capabilities-internal")),
       "AG14", "has 0 route-level")
expect("two authorizations on one rule fail", second_policy, "AG14", "has 2 route-level")
expect("no repeated sub prefix fails", lambda o: caps(o, "internal")["policy"]["matchExpressions"].pop(0),
       "AG14", "must Require")
expect("Allow instead of Require fails", lambda o: caps(o, "public").update({"action": "Allow"}), "AG14", "must Require")
expect("a model rule missing an audience fails", lambda o: caps(o, "internal")["policy"]["matchExpressions"]
       .__setitem__(1, model_rule(None, "internal", ["agent-router.implementer.internal"])), "AG14", "an alternative")
expect("an appended || true fails", lambda o: caps(o, "public")["policy"]["matchExpressions"]
       .__setitem__(1, caps(o, "public")["policy"]["matchExpressions"][1][:-1] + " || true)"), "AG14", "one model Require")
expect("&& between alternatives fails", lambda o: caps(o, "public")["policy"]["matchExpressions"]
       .__setitem__(1, caps(o, "public")["policy"]["matchExpressions"][1].replace(" || ", " && ")), "AG14", "one model Require")
expect("an alternative for a foreign audience fails", lambda o: caps(o, "internal")["policy"]["matchExpressions"]
       .__setitem__(1, model_rule(None, "internal", sorted(gate.audiences(gate.PROFILES[REAL], "internal")) + ["x.y"])),
       "AG14", "one model Require")
expect("a non-literal entry in a model list fails cleanly", lambda o: caps(o, "public")["policy"]["matchExpressions"]
       .__setitem__(1, caps(o, "public")["policy"]["matchExpressions"][1].replace('["agent-default"]', '["agent-default", m]', 1)),
       "AG14", "one model Require")
expect("an unknown alias in a model list fails", lambda o: caps(o, "public")["policy"]["matchExpressions"]
       .__setitem__(1, caps(o, "public")["policy"]["matchExpressions"][1].replace('["agent-default"]', '["gpt-9"]', 1)),
       "AG14", "one model Require")
expect("no tier pinning a model fails", lambda o: find(o, "ConfigMap", gate.FACTORY_VALUES)["data"].update(
    {"values.yaml": yaml.safe_dump({"config": {"tiers": {}}})}), "AG14", "pins a model")
expect("llm.requestModel, which 1.6 lacks there, fails", lambda o: caps(o, "public")["policy"]["matchExpressions"]
       .__setitem__(1, caps(o, "public")["policy"]["matchExpressions"][1]
                    .replace(gate.EFFECTIVE_MODEL, "llm.requestModel")), "AG14", "one model Require")
expect("a body read on /v1/models fails", lambda o: spec_at(o, "AgentgatewayPolicy", "capabilities-internal",
                                                            "targetRefs").append(
    {"group": "gateway.networking.k8s.io", "kind": "HTTPRoute", "name": "agent-models-internal",
     "sectionName": "models"}), "AG14", "403 before its 404")
expect("a tier pinning a model a role refuses fails", tier_model("tier-frontier"), "AG14", "which the factory's tiers pin")
expect("no frontend buffer fails", lambda o: o.remove(find(o, "AgentgatewayPolicy", "frontend")), "AG14", "maxBufferSize")
expect("a whole-route authorization reaches /v1/models and fails", lambda o: spec_at(
    o, "AgentgatewayPolicy", "capabilities-public", "targetRefs")[0].pop("sectionName"), "AG14", "403 before its 404")

print("AG6 argument rules (capability profiles P3)")


def arg_authz(o):
    return spec_at(o, "AgentgatewayPolicy", "capabilities-mcp-public", "traffic", "authorization")


def arg_expr(o, value):
    arg_authz(o)["policy"]["matchExpressions"][1] = value


R = gate.PROFILES[REAL]
expect("an upper-case value, which the folded argument never equals, fails",
       lambda o: arg_expr(o, argument(R, "public", "Secret")), "AG6", "not one argument rule")
expect("the unfolded form fails", lambda o: arg_expr(o, 'mcp.tool.arguments.kind != "Secret"'), "AG6", "not one argument rule")
expect("an appended || true fails", lambda o: arg_expr(o, argument(R, "public") + " || true"), "AG6", "not one argument rule")
expect("a body read fails", lambda o: arg_authz(o)["policy"]["matchExpressions"].append(
    'json(request.body).method != "tools/call"'), "AG6", "not one argument rule")
expect("an internal audience on a public MCP route fails",
       lambda o: arg_expr(o, argument(R, "internal")), "AG6", "binds a internal audience")
expect("Allow instead of Require fails", lambda o: arg_authz(o).update({"action": "Allow"}), "AG6", "must Require")
expect("no repeated sub prefix fails", lambda o: arg_authz(o)["policy"]["matchExpressions"].pop(0), "AG6", "must Require")
check("the gate's grammar takes the generator's rule", bool(gate.argument_rule(R).match(
    gen.argument_rule("reviewer", "internal", "flux-operator-mcp", "get_kubernetes_resources", "kind", "Secret"))))

print("main")
with tempfile.TemporaryDirectory() as d:
    # base and both clusters render the same objects: one world per cluster, so no double count.
    for name in ("overlay-infrastructure-base-agent-gateway.yaml", "overlay-infrastructure-aws-0-agent-gateway.yaml",
                 "overlay-infrastructure-gcp-0-agent-gateway.yaml"):
        pathlib.Path(d, name).write_text(yaml.safe_dump_all(compliant()))
    code, out = run_main(d)
    check("main exits 0 on per-cluster duplicates", code == 0, out)
    check("main prints 15 checks", "assert-agent-gateway: 15 checks, 0 violations" in out, out)
    pathlib.Path(d, "overlay-infrastructure-gcp-0-agent-gateway.yaml").write_text(
        yaml.safe_dump_all([o for o in compliant() if o["kind"] != "Gateway"]))
    code, out = run_main(d)
    check("a cluster with agentgateway objects but no Gateway fails AG1", code == 1 and "AG1" in out, out)
with tempfile.TemporaryDirectory() as d:
    pathlib.Path(d, "overlay-infrastructure-aws-0-other.yaml").write_text(
        yaml.safe_dump({"apiVersion": "v1", "kind": "ConfigMap", "metadata": {"name": "x", "namespace": "y"}}))
    code, out = run_main(d)
    check("no agentgateway object fails, not passes", code == 1 and "AG1" in out, out)
    check("main exits 2 on a missing bundle", run_main(d + "/missing")[0] == 2)

if FAILURES:
    print(f"\n{len(FAILURES)} failure(s)")
    sys.exit(1)
print("\nall passed")
