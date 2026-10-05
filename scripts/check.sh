#!/usr/bin/env bash
# Single entry point for every check. CI runs exactly this script, so a green
# local run means a green CI run.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

# Prefer the project virtualenv when present (Windows and POSIX layouts).
for d in .venv/Scripts .venv/bin; do
  [[ -d "$d" ]] && PATH="$PWD/$d:$PATH"
done
export PATH

section() { printf '\n== %s\n' "$1"; }

section "ruff"
ruff check .

section "yamllint"
yamllint .

section "sqlfluff"
sqlfluff lint dbt/models dbt/macros --dialect snowflake

section "shellcheck"
shellcheck -S warning scripts/*.sh .githooks/*

section "dbt parse (no credentials)"
(
  cd dbt
  [[ -f profiles.yml ]] || cp profiles.yml.example profiles.yml
  DBT_PROFILES_DIR="$PWD" dbt parse
)

section "pytest"
pytest -q --no-header

section "leak scan"
bash scripts/check_leaks.sh

section "text hygiene"
# scan LABEL PATTERN reads file names on stdin and fails if any file matches.
# grep exit 1 means "no match"; anything above is a grep error, which must
# fail the check instead of passing silently. (grep -P is avoided on purpose:
# Git Bash's grep rejects it under LC_ALL=C.)
scan() {
  local label="$1" pattern="$2" found=0 rc f
  while IFS= read -r f; do
    [[ -f "$f" ]] || continue
    rc=0
    LC_ALL=C grep -qI -e "$pattern" "$f" || rc=$?
    if (( rc == 0 )); then
      echo "$label: $f" >&2; found=1
    elif (( rc != 1 )); then
      echo "grep failed (exit $rc) on $f" >&2; exit 2
    fi
  done
  return "$found"
}
# Control characters (a stray BEL once came from a sed escape).
ctrl=$(printf '[\001-\010\013\014\016-\037]')
git ls-files | scan "control character" "$ctrl"
# Everything is English; only the glossary and the Portuguese README keep Portuguese domain terms, and
# the seeds and the generator's city list, which are master data copied
# unchanged (accented city names, ...).
# Accented Latin letters are 0xC3 0x80-0xBF in UTF-8.
accent=$(printf '\303[\200-\277]')
git ls-files | grep -vE '^(GLOSSARY.md|README.pt-BR.md|dbt/seeds/.*\.csv|generator/cidades_reais\.csv)$' | scan "accented (non-English) text" "$accent"

printf '\nAll checks passed.\n'
