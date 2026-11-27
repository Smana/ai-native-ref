#!/usr/bin/env python3
"""Generate post-Hugo cross-domain HTML redirect stubs from website/data/redirects.yaml.

Runs after `hugo --gc --minify` so redirect pages stay completely out of Hextra's
sidebar, FlexSearch index, and sitemap.xml. Refuses any collision with a live
Hugo-generated page, duplicate `from` entries, path traversal, or non-maku.ogenki.io
targets.

Usage:
  python3 scripts/ci/build-redirects.py --public website/public --map website/data/redirects.yaml
  python3 scripts/ci/build-redirects.py --map website/data/redirects.yaml --verify-live
"""
import argparse
import html
import pathlib
import re
import sys
import urllib.error
import urllib.request

ALLOWED_PREFIX = "https://maku.ogenki.io/"
SAFE_SEGMENT_RE = re.compile(r"^[A-Za-z0-9._-]+$")

TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Moved to Maku documentation</title>
  <meta name="robots" content="noindex">
  <link rel="canonical" href="{target}">
  <meta http-equiv="refresh" content="0; url={target}">
</head>
<body>
  <p>This page moved to <a href="{target}">{target}</a>.</p>
</body>
</html>
"""


def parse_redirects_yaml(path: pathlib.Path) -> list[tuple[str, str]]:
    """Parse a flat YAML list of `{from: ..., to: ...}` entries using stdlib only."""
    entries: list[tuple[str, str]] = []
    cur: dict[str, str] = {}

    def flush():
        if cur:
            if "from" not in cur or "to" not in cur:
                raise ValueError(f"{path}: incomplete redirect entry: {cur}")
            entries.append((cur["from"], cur["to"]))
            cur.clear()

    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("- "):
            flush()
            line = line[2:].strip()
        if ":" not in line:
            raise ValueError(f"{path}:{lineno}: expected key: value, got {raw!r}")
        key, val = line.split(":", 1)
        key = key.strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
            val = val[1:-1]
        if key not in ("from", "to"):
            raise ValueError(f"{path}:{lineno}: unexpected key {key!r}")
        cur[key] = val
    flush()
    return entries


def normalize_from(raw: str) -> str:
    stripped = raw.strip().strip("/")
    if not stripped:
        raise ValueError(f"invalid empty redirect source: {raw!r}")
    parts = stripped.split("/")
    for part in parts:
        if part in ("", ".", "..") or not SAFE_SEGMENT_RE.match(part):
            raise ValueError(f"invalid redirect source path: {raw!r}")
    return "/".join(parts)


def validate_entries(entries: list[tuple[str, str]]) -> list[tuple[str, str]]:
    seen: set[str] = set()
    cleaned: list[tuple[str, str]] = []
    for raw_from, raw_to in entries:
        norm = normalize_from(raw_from)
        if norm in seen:
            raise ValueError(f"duplicate redirect source: /{norm}/")
        seen.add(norm)
        target = raw_to.strip()
        if not target.startswith(ALLOWED_PREFIX):
            raise ValueError(
                f"redirect target for /{norm}/ must start with {ALLOWED_PREFIX!r}, got {target!r}"
            )
        cleaned.append((norm, target))
    return cleaned


def verify_live(entries: list[tuple[str, str]]) -> list[str]:
    failures: list[str] = []
    seen_targets = sorted({to for _, to in entries})
    for url in seen_targets:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "airef-redirect-check/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status != 200:
                    failures.append(f"HTTP {resp.status}: {url}")
        except urllib.error.HTTPError as exc:
            if exc.code == 405:
                try:
                    with urllib.request.urlopen(url, timeout=15) as resp:
                        if resp.status != 200:
                            failures.append(f"HTTP {resp.status}: {url}")
                except Exception as inner:
                    failures.append(f"ERR ({inner}): {url}")
            else:
                failures.append(f"HTTP {exc.code}: {url}")
        except Exception as exc:
            failures.append(f"ERR ({exc}): {url}")
    return failures


def write_stubs(public_dir: pathlib.Path, entries: list[tuple[str, str]]) -> int:
    if not public_dir.is_dir():
        raise FileNotFoundError(f"public directory does not exist: {public_dir}")
    # Check all collisions before writing anything.
    collisions: list[str] = []
    for norm, _ in entries:
        out = public_dir / norm / "index.html"
        if out.exists():
            collisions.append(f"/{norm}/ (collides with {out})")
    if collisions:
        raise RuntimeError("redirect collision with live Hugo page(s):\n  " + "\n  ".join(collisions))

    for norm, target in entries:
        out = public_dir / norm / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        escaped = html.escape(target, quote=True)
        out.write_text(TEMPLATE.format(target=escaped), encoding="utf-8")
    return len(entries)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Build post-Hugo cross-domain redirect stubs.")
    parser.add_argument("--public", type=pathlib.Path, help="Hugo output directory (e.g. website/public)")
    parser.add_argument(
        "--map",
        dest="map_path",
        type=pathlib.Path,
        default=pathlib.Path("website/data/redirects.yaml"),
        help="Path to redirects.yaml",
    )
    parser.add_argument(
        "--verify-live",
        action="store_true",
        help="Verify every unique redirect target returns HTTP 200 on live maku.ogenki.io",
    )
    args = parser.parse_args(argv[1:])

    try:
        raw_entries = parse_redirects_yaml(args.map_path)
        entries = validate_entries(raw_entries)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.verify_live:
        failures = verify_live(entries)
        if failures:
            print("ERROR: live redirect verification failed:", file=sys.stderr)
            for item in failures:
                print(f"  {item}", file=sys.stderr)
            return 1
        print(f"==> Live check: {len({to for _, to in entries})} unique maku.ogenki.io targets returned HTTP 200.")

    if args.public is not None:
        try:
            count = write_stubs(args.public, entries)
        except Exception as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        print(f"==> Generated {count} cross-domain redirect stubs in {args.public}.")
    elif not args.verify_live:
        print("ERROR: specify --public, --verify-live, or both", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
