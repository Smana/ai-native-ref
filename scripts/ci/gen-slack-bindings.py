#!/usr/bin/env python3
"""Render the Slack channel binding's consumers from its one declaration (CD24, proof 16).

tooling/base/agent-factory/slack-bindings.yaml names the workspace (`teamID`) and each channel the
factory's App serves, `{repositories, maxCostUSD, notify}` and an optional boolean `approvals`. This script owns one region of each
consumer and preserves every other byte:

  the App's config         `teamID:`, its line replaced whole; `channels:`, replaced whole by one line
                           per channel, sorted by id: `<id>: {repositories: […], maxCostUSD: …, notify: […]}`,
                           with `approvals: true` before notify only when the channel sets it
  the sponsored values     api.sponsored[slack-app].repositories: the sorted union of the channels'
  the broker's config      webhooks[slack-app].repositories: the same union; .events: the union of the
                           channels' `notify`, in declaration order

The sponsored values and the broker's config are per cloud: either cloud in CLOUDS may serve the App,
so each gets the same rendering, and a channel's maxCostUSD is held to the lower principal's.

Each splice is verified by re-parsing the file: the decoded value must be the rendering, and the
decoded document must be the committed one with only that value changed.

The declaration is refused, before any file is written, on: a channel id outside ^[CG][A-Z0-9]{2,20}$;
a teamID outside ^T[A-Z0-9]{2,20}$; no channel; an empty `repositories`; a repository outside
^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$, or one no Repository of the factory names (it fails here,
not in the cluster); a maxCostUSD under 0.01 or above the sponsored principal's maxCostUSD; a `notify`
entry outside the ten event names the App draws a line for; a notify union that is empty (the broker
refuses `events: []`; one channel's `notify: []`, told nothing, is fine); a duplicate entry or channel;
an unknown key; an `approvals` that is not a boolean. A consumer without its `slack-app` entry, or one
that does not parse, fails too.

`approvals` is not in the plan's declaration (a deliberate deviation): `channels:` is replaced whole, so
a hand-kept `approvals: true` in the App config would be erased by the next --write. Maku decodes it
omitempty, so false renders as absent and a declaration without it renders as before.

Usage: gen-slack-bindings.py [--write] [ROOT]    (ROOT defaults to this repository)
Exit:  0 the committed files are the rendering (or --write wrote it), 1 drift or a bad declaration.
"""
import copy
import difflib
import pathlib
import re
import sys

import yaml

DECLARATION = "tooling/base/agent-factory/slack-bindings.yaml"
APP = "tooling/base/agent-factory/slack-app/config.yaml"
# One Slack App serves one cloud at a time (its one Request URL), but either may be the one.
CLOUDS = ("aws-0", "gcp-0")
SPONSORED = tuple(f"tooling/{c}/agent-factory/helm-values-sponsored.yaml" for c in CLOUDS)
BROKER = tuple(f"infrastructure/{c}/room-broker/config.yaml" for c in CLOUDS)
# The factory's Repository objects (Maku factory resources): what a channel may serve.
FACTORY = "tooling/base/agent-factory/resources"
PRINCIPAL = "slack-app"
CHANNEL = re.compile(r"^[CG][A-Z0-9]{2,20}$")
TEAM = re.compile(r"^T[A-Z0-9]{2,20}$")
REPOSITORY = re.compile(r"^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$")
MIN_COST = 0.01
# What a channel's notify may name, a closed list: Maku internal/webhook/events.go `types` (the
# thirteen webhook.Types() returns) less the three internal/slackapp/config.go refuses because the App
# draws no line for them: room.task_received, room.run_ended, room.monitor_verdict.
EVENTS = ("room.task_triaged", "room.run_started", "room.waiting_for_human", "room.pr_opened",
          "room.verdict_posted", "room.merged", "room.reverted", "room.budget_reached", "room.ended",
          "room.approval_closed")
CHANNEL_KEYS = {"repositories", "maxCostUSD", "notify"}
OPTIONAL_KEYS = {"approvals"}


class ConfigError(Exception):
    pass


class _UniqueLoader(yaml.SafeLoader):
    """SafeLoader that refuses a mapping key written twice: safe_load keeps the last one silently."""


def _mapping(loader, node, deep=False):
    keys = [loader.construct_object(k, deep=deep) for k, _ in node.value]
    for k in sorted({k for k in keys if keys.count(k) > 1}, key=str):
        raise ConfigError(f"{k}: duplicate entry")
    return yaml.SafeLoader.construct_mapping(loader, node, deep)


_UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
                              lambda loader, node: dict(_mapping(loader, node)))


def load_declaration(text):
    """The declaration's mapping, a key written twice refused."""
    try:
        return yaml.load(text, Loader=_UniqueLoader) or {}  # noqa: S506 -- a SafeLoader subclass
    except yaml.YAMLError as e:
        raise ConfigError(f"does not parse ({e})")


def _number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _list(at, v):
    if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
        raise ConfigError(f"{at} is a list of strings")
    for x in sorted({x for x in v if v.count(x) > 1}):
        raise ConfigError(f"{at}: {x} is a duplicate entry")
    return v


def validate(declaration, served, ceiling):
    """The declaration's channels, or ConfigError."""
    if not isinstance(declaration, dict) or set(declaration) != {"teamID", "channels"}:
        extra = sorted(map(str, set(declaration) - {"teamID", "channels"})) if isinstance(declaration, dict) else []
        raise ConfigError(f"holds exactly teamID and channels{' (unknown: ' + ', '.join(extra) + ')' if extra else ''}")
    team = declaration["teamID"]
    if not isinstance(team, str) or not TEAM.fullmatch(team):
        raise ConfigError(f"teamID {team!r} is not {TEAM.pattern}")
    channels = declaration["channels"]
    if not isinstance(channels, dict) or not channels:
        raise ConfigError("channels names no channel")
    for cid, ch in channels.items():
        if not isinstance(cid, str) or not CHANNEL.fullmatch(cid):
            raise ConfigError(f"channel {cid!r} is not {CHANNEL.pattern}")
        if not isinstance(ch, dict):
            raise ConfigError(f"channels.{cid} is a mapping")
        if missing := CHANNEL_KEYS - set(ch):
            raise ConfigError(f"channels.{cid} names no {', '.join(sorted(missing))}")
        if unknown := set(ch) - CHANNEL_KEYS - OPTIONAL_KEYS:
            raise ConfigError(f"channels.{cid}: unknown key {', '.join(sorted(map(str, unknown)))}")
        if not isinstance(ch.get("approvals", False), bool):
            raise ConfigError(f"channels.{cid}.approvals {ch['approvals']!r} is not a boolean")
        repos = _list(f"channels.{cid}.repositories", ch["repositories"])
        if not repos:
            raise ConfigError(f"channels.{cid}.repositories is empty")
        for r in repos:
            if not REPOSITORY.fullmatch(r):
                raise ConfigError(f"channels.{cid}.repositories: {r!r} is not owner/name")
            if r not in served:
                raise ConfigError(f"channels.{cid}.repositories: {r} is not a repository the factory's "
                                  f"Repository in {FACTORY} names")
        cost = ch["maxCostUSD"]
        if not _number(cost) or cost < MIN_COST or cost > ceiling:
            raise ConfigError(f"channels.{cid}.maxCostUSD {cost!r} is not in [{MIN_COST}, {ceiling}], "
                              f"the lowest {PRINCIPAL} principal's maxCostUSD ({', '.join(SPONSORED)})")
        for e in _list(f"channels.{cid}.notify", ch["notify"]):
            if e not in EVENTS:
                raise ConfigError(f"channels.{cid}.notify: {e!r} is not an event name the App draws a line for")
    if not notify_union(channels):
        raise ConfigError("no channel's notify names an event: the broker refuses an empty events list")
    return channels


def _scalar(v):
    return repr(v) if isinstance(v, float) else str(v)


def _flow(items):
    return "[" + ", ".join(items) + "]"


def channels_block(channels):
    """The App config's `channels:` region, as lines: one per channel, sorted by id."""
    return ["channels:"] + [f"  {cid}: {{repositories: {_flow(ch['repositories'])}, "
                            f"maxCostUSD: {_scalar(ch['maxCostUSD'])}, {'approvals: true, ' if ch.get('approvals') else ''}"
                            f"notify: {_flow(ch['notify'])}}}"
                            for cid, ch in sorted(channels.items())]


def notify_union(channels):
    """Every channel's `notify`, once each, in declaration order."""
    return list(dict.fromkeys(e for ch in channels.values() for e in ch["notify"]))


def repositories_union(channels):
    """Every channel's repositories, once each, sorted."""
    return sorted({r for ch in channels.values() for r in ch["repositories"]})


def _parse(path, decode, text):
    """decode(text), a parse error a ConfigError naming path."""
    try:
        return decode(text)
    except yaml.YAMLError as e:
        raise ConfigError(f"{path}: does not parse ({str(e).splitlines()[0]})")


def _values(text):
    """A values ConfigMap's decoded data["values.yaml"]."""
    return yaml.safe_load(((yaml.safe_load(text) or {}).get("data") or {}).get("values.yaml") or "") or {}


def _entry(items, at):
    """The `slack-app` entry of a list of named entries, or ConfigError."""
    found = [i for i in items or [] if isinstance(i, dict) and i.get("name") == PRINCIPAL]
    if len(found) != 1:
        raise ConfigError(f"{at}: {'no' if not found else 'more than one'} {PRINCIPAL} entry")
    return found[0]


def registries(root):
    """(the repositories the factory's Repository objects name, the lowest slack-app principal's maxCostUSD)."""
    root = pathlib.Path(root)
    kustomization = _parse(f"{FACTORY}/kustomization.yaml", yaml.safe_load, (root / FACTORY / "kustomization.yaml").read_text())
    served = set()
    for f in (kustomization or {}).get("resources") or []:
        for d in _parse(f"{FACTORY}/{f}", lambda t: list(yaml.safe_load_all(t)), (root / FACTORY / f).read_text()):
            if isinstance(d, dict) and d.get("kind") == "Repository":
                served.add((d.get("spec") or {}).get("repository"))
    ceilings = []
    for path in SPONSORED:
        sponsored = _parse(path, _values, (root / path).read_text())
        entry = _entry(((sponsored.get("config") or {}).get("api") or {}).get("sponsored"),
                       f"{path} config.api.sponsored")
        if not _number(entry.get("maxCostUSD")):
            raise ConfigError(f"{path}: the {PRINCIPAL} principal names no maxCostUSD")
        ceilings.append(entry["maxCostUSD"])
    return served, min(ceilings)


def _indent(line):
    return len(line) - len(line.lstrip(" "))


def _region(lines, i):
    """The end of the region line i opens: every following non-blank line indented deeper than it."""
    j = i + 1
    while j < len(lines) and lines[j].strip() and _indent(lines[j]) > _indent(lines[i]):
        j += 1
    return j


def _key(lines, key, lo, hi, indent=None):
    found = [n for n in range(lo, hi) if re.match(rf"^ *{re.escape(key)}:(\s|$)", lines[n])
             and (indent is None or _indent(lines[n]) == indent)]
    if len(found) != 1:
        raise ConfigError(f"{'no' if not found else 'more than one'} `{key}:` line")
    return found[0]


def splice(text, key, rendered, parent=None):
    """text with `key:`'s whole region (its line and every line indented deeper) replaced by `rendered`,
    lines written at the key's indent. Without parent the key is a top-level one; with parent, it is the
    key of the `- name: slack-app` item of the one `parent:` list. Every other byte is kept."""
    lines = text.splitlines(True)
    if parent is None:
        at = _key(lines, key, 0, len(lines), indent=0)
    else:
        p = _key(lines, parent, 0, len(lines))
        end = _region(lines, p)
        items = [n for n in range(p + 1, end) if re.match(rf"^ *- name: {PRINCIPAL}\s*$", lines[n])]
        if len(items) != 1:
            raise ConfigError(f"`{parent}:` has {'no' if not items else 'more than one'} `- name: {PRINCIPAL}` item")
        item = items[0]
        dash = lines[item].index("-")
        at = _key(lines, key, item + 1, _region(lines, item), indent=dash + 2)
    pad = " " * _indent(lines[at])
    return "".join(lines[:at] + [pad + r + "\n" for r in rendered] + lines[_region(lines, at):])


def _held(path, before, after, decode, values):
    """ConfigError unless `after` decodes to `before` with exactly `values` set ({setter: value})."""
    want = copy.deepcopy(_parse(path, decode, before))
    for put, v in values:
        put(want, v)
    try:
        got = decode(after)
    except yaml.YAMLError:
        got = None
    if got != want:
        raise ConfigError(f"{path}: the spliced file does not parse back to its rendering (a comment or a "
                          "multi-line value inside the generated region?)")


def _set(key):
    return lambda doc, v: doc.__setitem__(key, v)


def _at(path, splicing):
    """splicing(), a ConfigError naming path."""
    try:
        return splicing()
    except ConfigError as e:
        raise ConfigError(f"{path}: {e}") from None


def render(declaration, served, ceiling, root=None):
    """{path: text} for every consumer in root (default: this repository), or ConfigError."""
    root = pathlib.Path(root) if root else pathlib.Path(__file__).resolve().parents[2]
    try:
        channels = validate(declaration, served, ceiling)
    except ConfigError as e:
        raise ConfigError(f"{DECLARATION}: {e}") from None
    repos, events = repositories_union(channels), notify_union(channels)
    out = {}

    text = (root / APP).read_text()
    new = _at(APP, lambda: splice(splice(text, "teamID", [f"teamID: {declaration['teamID']}"]),
                                  "channels", channels_block(channels)))
    # As the App decodes it: approvals is omitempty, so a false one is absent.
    decoded = {cid: {k: v for k, v in ch.items() if k != "approvals" or v} for cid, ch in channels.items()}
    _held(APP, text, new, yaml.safe_load,
          [(_set("teamID"), declaration["teamID"]), (_set("channels"), copy.deepcopy(decoded))])
    out[APP] = new

    for path in SPONSORED:
        out[path] = _sponsored(root, path, repos)
    for path in BROKER:
        out[path] = _broker(root, path, repos, events)
    return out


def _sponsored(root, path, repos):
    text = (root / path).read_text()
    new = _at(path, lambda: splice(text, "repositories", [f"repositories: {_flow(repos)}"], parent="sponsored"))

    def sponsored_entry(doc, v):
        _entry(doc["config"]["api"]["sponsored"], f"{path} config.api.sponsored")["repositories"] = v
    _held(path, text, new, _values, [(sponsored_entry, repos)])
    return new


def _broker(root, path, repos, events):
    text = (root / path).read_text()
    new = _at(path, lambda: splice(splice(text, "repositories", [f"repositories: {_flow(repos)}"], parent="webhooks"),
                                   "events", [f"events: {_flow(events)}"], parent="webhooks"))

    def webhook(field):
        def put(doc, v):
            _entry(doc.get("webhooks"), f"{path} webhooks")[field] = v
        return put
    _held(path, text, new, yaml.safe_load, [(webhook("repositories"), repos), (webhook("events"), events)])
    return new


def main(argv):
    args = argv[1:]
    write = "--write" in args
    paths = [a for a in args if a != "--write"]
    root = pathlib.Path(paths[0]) if paths else pathlib.Path(__file__).resolve().parents[2]
    try:
        declaration = _at(DECLARATION, lambda: load_declaration((root / DECLARATION).read_text()))
        served, ceiling = registries(root)
        wanted = render(declaration, served, ceiling, root)
    except ConfigError as e:
        print(f"FAIL {e}", file=sys.stderr)
        return 1
    drift = False
    for path, text in wanted.items():
        target = root / path
        current = target.read_text()
        if text == current:
            print(f"gen-slack-bindings: {path} is its declaration's rendering")
        elif write:
            target.write_text(text)
            print(f"gen-slack-bindings: wrote {path}")
        else:
            drift = True
            sys.stderr.writelines(difflib.unified_diff(current.splitlines(True), text.splitlines(True),
                                                       f"{path} (committed)", f"{path} (rendered from {DECLARATION})"))
            print(f"FAIL {path} differs from its declaration's rendering: edit {DECLARATION}, run "
                  "python3 scripts/ci/gen-slack-bindings.py --write and commit both", file=sys.stderr)
    return 1 if drift else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
