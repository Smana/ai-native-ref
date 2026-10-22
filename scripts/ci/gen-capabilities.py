#!/usr/bin/env python3
"""Render the agent router's MCP Allow lists from the capability profiles (capability profiles design, P1).

One profile per role and data class, infrastructure/base/agent-gateway/profiles/<role>.<dataClass>.yaml:

    role: reviewer
    dataClass: internal
    models: [agent-default, tier-light, tier-standard, tier-frontier]
    tools:
      flux-operator-mcp:
        - search_flux_docs

This script owns the `matchExpressions` items of each MCP authorization policy in
infrastructure/base/agent-gateway/mcp.yaml and nothing else in that file. A policy's class is the
listener its HTTPRoute attaches to; its list holds one expression per profile of that class (roles
in name order) and target (in the agent-mcp backend's order) the profile names, with the tools in
the profile's order: the N7 grammar gate AG6 enforces. A tool no expression names is hidden from
tools/list and answers `Unknown tool`.

P1 renders `tools` only. `models` is carried and checked, not rendered: until P2 compiles it into a
route-level authorization, it names every alias the LLM backends serve, since any role may ask for
any of them today. `egress`, `readOnly` and a tool's `when` are refused until the steps that render
them: a field nothing enforces must not read as a rule.

Usage: gen-capabilities.py [--write] [ROOT]    (ROOT defaults to this repository)
Exit:  0 the committed lists are the rendering (or --write wrote it), 1 drift or a bad profile.
"""
import difflib
import pathlib
import re
import sys
from typing import NamedTuple

import yaml

GATEWAY = pathlib.PurePosixPath("infrastructure/base/agent-gateway")
PROFILES = GATEWAY / "profiles"
MCP = GATEWAY / "mcp.yaml"
AUD_PREFIX = "agent-router"
KEYS = ("role", "dataClass", "models", "tools")
# Rendered from the agent-capability-profiles ConfigMap step on; refused until then.
CONFIGMAP_KEYS = ("egress", "readOnly")
FILE = re.compile(r"^(?P<role>[a-z]+)\.(?P<cls>[a-z]+)\.yaml$")
TOOL = re.compile(r"^[a-z0-9_]+$")
SEPARATOR = re.compile(r"^---\n", re.M)
LIST = re.compile(r"^(?P<indent> *)matchExpressions:\n(?:(?P=indent)  - .*\n)+", re.M)


class Profile(NamedTuple):
    path: str
    role: str
    data_class: str
    tools: dict


def expression(role, cls, target, tools):
    """One N7 alternative: one role's audience, one target, its tool names."""
    names = ", ".join(f'"{t}"' for t in tools)
    return f'"{AUD_PREFIX}.{role}.{cls}" in jwt.aud && mcp.tool.target == "{target}" && mcp.tool.name in [{names}]'


def served_aliases(root):
    """Every model alias an LLM backend beside mcp.yaml serves (AG12 pins them to AGENT_MODELS)."""
    aliases = set()
    for path in sorted((root / GATEWAY).glob("*.yaml")):
        for doc in yaml.safe_load_all(path.read_text()):
            if isinstance(doc, dict) and doc.get("kind") == "AgentgatewayBackend":
                ai = (((doc.get("spec") or {}).get("policies") or {}).get("ai") or {})
                aliases |= set(ai.get("modelAliases") or {})
    return aliases


def load_profile(root, path, targets, aliases, errors):
    rel = path.relative_to(root).as_posix()
    doc = yaml.safe_load(path.read_text())
    if not isinstance(doc, dict):
        errors.append(f"{rel}: a profile is a mapping of {', '.join(KEYS)}")
        return None
    for key in sorted(set(doc) - set(KEYS)):
        errors.append(f"{rel}: {key} arrives with the agent-capability-profiles ConfigMap; a field nothing renders "
                      "must not read as a rule" if key in CONFIGMAP_KEYS
                      else f"{rel}: unknown key {key}; a profile holds {', '.join(KEYS)}")
    for key in KEYS:
        if key not in doc:
            errors.append(f"{rel}: missing {key}")
    m = FILE.match(path.name)
    if not m or (doc.get("role"), doc.get("dataClass")) != (m["role"], m["cls"]):
        errors.append(f"{rel}: a profile is named <role>.<dataClass>.yaml after its own role and dataClass")
    models = doc.get("models")
    if not isinstance(models, list) or len(set(map(str, models))) != len(models) or set(map(str, models)) != aliases:
        errors.append(f"{rel}: models must name each alias the LLM backends serve once, {sorted(aliases)}: it is "
                      "checked, not rendered, until P2, and today any role may ask for any of them")
    tools = doc.get("tools")
    if not isinstance(tools, dict) or not tools:
        errors.append(f"{rel}: tools maps each MCP target to its tool names")
        return None
    for target, names in tools.items():
        if target not in targets:
            errors.append(f"{rel}: {target} is not a target of the agent-mcp backend ({', '.join(targets)})")
        if not isinstance(names, list) or not names:
            errors.append(f"{rel}: {target} lists no tool; leave the target out instead")
            continue
        for n in names:
            if isinstance(n, dict):
                errors.append(f"{rel}: {target} {n.get('name')}: argument constraints (when) arrive with P3, "
                              "after spike S0")
            elif not isinstance(n, str) or not TOOL.match(n):
                errors.append(f"{rel}: {target} names {n!r}, which is not a tool name")
        twice = sorted({n for n in names if isinstance(n, str) and names.count(n) > 1})
        if twice:
            errors.append(f"{rel}: {target} lists {', '.join(twice)} twice")
    return Profile(rel, str(doc.get("role")), str(doc.get("dataClass")), tools)


def render(root):
    """(mcp.yaml as the profiles render it, None) or (None, the errors that prevent it)."""
    root = pathlib.Path(root)
    errors = []
    chunks = SEPARATOR.split((root / MCP).read_text())
    docs = [yaml.safe_load(c) or {} for c in chunks]
    backends = [d for d in docs if d.get("kind") == "AgentgatewayBackend" and (d.get("spec") or {}).get("mcp")]
    if len(backends) != 1:
        return None, [f"{MCP}: expected one MCP AgentgatewayBackend, found {len(backends)}"]
    targets = [t.get("name") for t in backends[0]["spec"]["mcp"].get("targets") or []]
    aliases = served_aliases(root)
    if not aliases:
        errors.append(f"{GATEWAY}: no LLM backend serves a model alias")
    files = sorted((root / PROFILES).glob("*.yaml"))
    if not files:
        errors.append(f"{PROFILES}: no profile")
    profiles = [p for p in (load_profile(root, f, targets, aliases, errors) for f in files) if p]
    routes = {d["metadata"]["name"]: {p.get("sectionName") for p in d["spec"].get("parentRefs") or []}
              for d in docs if d.get("kind") == "HTTPRoute"}
    served = set()
    for i, d in enumerate(docs):
        authz = (((d.get("spec") or {}).get("backend") or {}).get("mcp") or {}).get("authorization")
        if d.get("kind") != "AgentgatewayPolicy" or authz is None:
            continue
        name = d["metadata"]["name"]
        sections = set().union(*(routes.get(t.get("name"), set()) for t in d["spec"].get("targetRefs") or []
                                 if t.get("kind") == "HTTPRoute"))
        if len(sections) != 1:
            errors.append(f"{MCP}: {name} must target routes on one listener, got {sorted(map(str, sections))}")
            continue
        cls = sections.pop()
        served.add(cls)
        exprs = [expression(p.role, cls, t, p.tools[t])
                 for p in sorted((p for p in profiles if p.data_class == cls), key=lambda p: p.role)
                 for t in targets if t in p.tools]
        found = list(LIST.finditer(chunks[i]))
        if not exprs:
            errors.append(f"{MCP}: no profile of class {cls} for {name}")
        elif len(found) != 1:
            errors.append(f"{MCP}: {name} must hold one block-style matchExpressions list, found {len(found)}")
        else:
            m, indent = found[0], found[0]["indent"]
            items = "".join(f"{indent}  - '{e}'\n" for e in exprs)
            spliced = f"{chunks[i][:m.start()]}{indent}matchExpressions:\n{items}{chunks[i][m.end():]}"
            # The splice replaces the run of plain items only: whatever else sits in the list (a comment, a
            # multi-line item, a last item with no newline) would survive it, so the list must parse back to
            # exactly the rendering.
            # Skipped once a profile is refused: its names may not be renderable at all.
            held = None if errors else ((((yaml.safe_load(spliced) or {}).get("spec") or {}).get("backend") or {}
                                         ).get("mcp") or {}).get("authorization", {}).get("policy", {}
                                                                                           ).get("matchExpressions")
            if not errors and held != exprs:
                errors.append(f"{MCP}: policy {name}: matchExpressions holds items the generator does not own "
                              "(a comment or a multi-line item inside the list?): move them above matchExpressions:")
            chunks[i] = spliced
    for p in profiles:
        if p.data_class not in served:
            errors.append(f"{p.path}: no MCP Allow policy in {MCP} serves the {p.data_class} listener")
    return (None, errors) if errors else ("---\n".join(chunks), [])


def main(argv):
    args = argv[1:]
    write = "--write" in args
    paths = [a for a in args if a != "--write"]
    root = pathlib.Path(paths[0]) if paths else pathlib.Path(__file__).resolve().parents[2]
    rendered, errors = render(root)
    for e in errors:
        print(f"FAIL {e}", file=sys.stderr)
    if errors:
        return 1
    current = (root / MCP).read_text()
    if rendered == current:
        print(f"gen-capabilities: {MCP} is its profiles' rendering")
        return 0
    if write:
        (root / MCP).write_text(rendered)
        print(f"gen-capabilities: wrote {MCP}")
        return 0
    sys.stderr.writelines(difflib.unified_diff(current.splitlines(True), rendered.splitlines(True),
                                               f"{MCP} (committed)", f"{MCP} (rendered from {PROFILES})"))
    print(f"FAIL {MCP} differs from its profiles' rendering: edit the profiles, run "
          "python3 scripts/ci/gen-capabilities.py --write and commit both", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
