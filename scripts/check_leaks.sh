#!/usr/bin/env bash
# Scans tracked files (or only staged ones with --staged) for personal paths,
# key material and real Snowflake hosts. The repo is public, so these must
# never be committed. Exit 1 on any hit.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

if [[ "${1:-}" == "--staged" ]]; then
  files=$(git diff --cached --name-only --diff-filter=ACM)
else
  files=$(git ls-files)
fi

# One ERE per rule: "label|pattern".
rules=(
  'windows drive path|[A-Za-z]:\\[A-Za-z]'
  'personal home path|(/c/Users/|/Users/[a-z]|/home/[a-z]+/)'
  'private key block|BEGIN [A-Z ]*PRIVATE KEY'
  'key body (base64)|MII[A-Za-z0-9+/]{60,}'
  'snowflake account host|[A-Za-z0-9-]+\.snowflakecomputing\.com'
  'snowsight account url|app\.snowflake\.com/[a-z0-9]+/[a-z0-9]+'
)

status=0
while IFS= read -r f; do
  [[ -z "$f" || ! -f "$f" ]] && continue
  # The rules above live in this file and in the hooks, so skip them.
  case "$f" in scripts/check_leaks.sh|.githooks/*) continue ;; esac
  for rule in "${rules[@]}"; do
    label="${rule%%|*}"; pattern="${rule#*|}"
    rc=0; hits=$(grep -InE -- "$pattern" "$f") || rc=$?
    if (( rc == 0 )); then
      printf 'LEAK (%s) in %s:\n%s\n' "$label" "$f" "$hits" >&2
      status=1
    elif (( rc != 1 )); then
      echo "check_leaks: grep failed (exit $rc) on $f" >&2; exit 2
    fi
  done
done <<< "$files"

if (( status )); then
  echo "check_leaks: found forbidden content (see above)." >&2
else
  echo "check_leaks: clean"
fi
exit "$status"
