#!/usr/bin/env bash
# Builds .composite/: the host (cloud-native-ref at HOST_REF, checked out in .host/) with
# every file under its ai_paths removed and this repository's tree laid over it. The host's
# own gates then run on the composite unchanged, so they judge exactly what S3 will apply.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."

HOST="${HOST_DIR:-.host}"
OUT="${COMPOSITE_DIR:-.composite}"
want="$(cat HOST_REF)"

if [ ! -d "$HOST/.git" ]; then
  git clone --quiet --filter=blob:none https://github.com/Smana/cloud-native-ref "$HOST"
fi
if [ "$(git -C "$HOST" rev-parse HEAD)" != "$want" ]; then
  git -C "$HOST" fetch --quiet origin "$want"
  git -C "$HOST" checkout --quiet --detach "$want"
fi

rm -rf "$OUT"
cp -a "$HOST" "$OUT"

# The host's own contract decides what is AI, not a copy kept here.
git -C "$OUT" ls-files -z | python3 -c '
import re, sys, yaml
pats = [re.compile(p) for p in yaml.safe_load(open(sys.argv[1]))["ai_paths"]]
for f in sys.stdin.read().split("\0"):
    if f and any(p.search(f) for p in pats):
        sys.stdout.write(f + "\0")
' "$OUT/scripts/ci/flux-schema/ai-boundary.yaml" | (cd "$OUT" && xargs -0 -r rm -f)

for d in clusters infrastructure security tooling observability apps flux scripts/ci; do
  [ -d "$d" ] && rsync -a "$d/" "$OUT/$d/"
done

# validate-vmrules.sh enumerates with `git ls-files`: the index must describe the composite.
git -C "$OUT" add -A
echo "composite: host $(git -C "$HOST" rev-parse --short HEAD) + $(git rev-parse --short HEAD) in $OUT/"
