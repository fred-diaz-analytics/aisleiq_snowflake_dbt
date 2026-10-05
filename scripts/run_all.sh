#!/usr/bin/env bash
# Single command that refreshes everything: generate (if needed), load RAW,
# then dbt seed + build. Usage:
#   bash scripts/run_all.sh [--target dev|prod] [--docs] [--regenerate]
# Connection variables (SNOWFLAKE_*) must already be in the environment, e.g.
#   set -a; source ~/.aisleiq/aisleiq.env; set +a
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

for d in .venv/Scripts .venv/bin; do
  [[ -d "$d" ]] && PATH="$PWD/$d:$PATH"
done
export PATH

target=dev docs=0 regenerate=0
while (( $# )); do
  case "$1" in
    --target) target="${2:?--target needs dev or prod}"; shift 2 ;;
    --docs) docs=1; shift ;;
    --regenerate) regenerate=1; shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
case "$target" in dev|prod) ;; *) echo "target must be dev or prod" >&2; exit 2 ;; esac

# The load must hit the same database dbt builds in.
export SNOWFLAKE_DATABASE="AISLEIQ_${target^^}"

section() { printf '\n== %s\n' "$1"; }

if (( regenerate )) || [[ ! -d generator/output ]]; then
  section "generate synthetic files (deterministic)"
  python generator/backfill_2026.py
fi

section "ingest into $SNOWFLAKE_DATABASE.RAW"
python ingestion/ingest.py

section "dbt seed + build (target $target)"
(
  cd dbt
  [[ -f profiles.yml ]] || cp profiles.yml.example profiles.yml
  export DBT_PROFILES_DIR="$PWD"
  dbt seed --target "$target"
  dbt build --target "$target"
  if (( docs )); then
    dbt docs generate --target "$target"
  fi
)

printf '\nDone (%s).\n' "$target"
