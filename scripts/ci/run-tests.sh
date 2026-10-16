#!/usr/bin/env bash
# Runs this repository's suites inside .composite/ (scripts/ci/host-profile.sh), where the
# host's fixtures and scripts they read exist. Same contract as the host's run.sh: honours
# the first `# requires:` line, exit 77 is a SKIP, a skip is printed, zero suites fails.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.." || exit 1
OUT="${COMPOSITE_DIR:-.composite}"
[ -d "$OUT" ] || { echo "error: no $OUT/; run scripts/ci/host-profile.sh first" >&2; exit 1; }

pass=0 skip=0 fail=0 rc=0
while IFS= read -r rel; do
  case "$rel" in
    *.sh) interpreter=bash ;;
    *.py) interpreter=python3 ;;
    *) continue ;;
  esac
  name="${rel#scripts/ci/tests/}"; name="${name%.*}"
  t="$OUT/$rel"
  missing=""
  command -v "$interpreter" >/dev/null 2>&1 || missing="$missing $interpreter"
  for tool in $(sed -n 's/^# requires:[[:space:]]*//p' "$t" | head -1); do
    command -v "$tool" >/dev/null 2>&1 || missing="$missing $tool"
  done
  if [ -n "$missing" ]; then
    printf 'SKIP  %-42s missing:%s\n' "$name" "$missing"; skip=$((skip + 1)); continue
  fi
  SECONDS=0
  out="$("$interpreter" "$t" 2>&1)"; code=$?
  if [ "$code" -eq 0 ]; then
    printf 'PASS  %-42s (%ds)\n' "$name" "$SECONDS"; pass=$((pass + 1))
  elif [ "$code" -eq 77 ]; then
    reason="${out##*$'\n'}"
    printf 'SKIP  %-42s %s\n' "$name" "${reason:-no reason given}"; skip=$((skip + 1))
  else
    printf 'FAIL  %-42s (%ds)\n' "$name" "$SECONDS"
    printf '%s\n' "$out" | sed 's/^/      /'
    fail=$((fail + 1)); rc=1
  fi
done < <(git ls-files 'scripts/ci/tests/*')

printf '%d passed, %d skipped, %d failed\n' "$pass" "$skip" "$fail"
[ $((pass + skip + fail)) -gt 0 ] || { echo "no suites found" >&2; exit 1; }
exit "$rc"
