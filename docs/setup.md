# Environment setup

Rebuilds the environment from scratch (also useful when the trial expires). Everything secret lives **outside the repo**, in `~/.aisleiq` (override with the `CONN_DIR` environment variable).

## 1. Python environment

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt   # Windows
```

Versions are pinned in `requirements.txt`: `dbt-core 1.12.5` and `dbt-snowflake 1.12.1`.

## 2. Provision Snowflake

```bash
bash scripts/setup_snowflake.sh
```

The wizard asks for the account identifier and the credit cap, generates the key pair in that folder, builds the final SQL (`infra/provision.sql` + public key) and walks you through running it in Snowsight as `ACCOUNTADMIN`. The SQL is idempotent.

Objects created:

| Object | Name |
|---|---|
| Databases | `AISLEIQ_DEV`, `AISLEIQ_PROD` (each with `RAW`, `SEEDS`, `STAGING`, `MARTS`) |
| Roles | `AISLEIQ_LOADER` (writes to `RAW`), `AISLEIQ_TRANSFORMER` (reads `RAW`, writes to `SEEDS`, `STAGING` and `MARTS`) |
| Warehouse | `AISLEIQ_WH` (X-Small, Gen1, 60s auto-suspend, no query acceleration) |
| Resource monitor | `AISLEIQ_RM` (monthly cap; notifies at 75%, suspends at 100%) |
| Internal stage | `RAW.LANDING` in each database |
| Service user | `AISLEIQ_SVC` (key pair, no password) |

## 3. Run dbt

```bash
set -a; source ~/.aisleiq/aisleiq.env; set +a
cd dbt
DBT_PROFILES_DIR=. ../.venv/Scripts/dbt.exe debug
```

`dbt/profiles.yml` is copied from `profiles.yml.example` (only `env_var`, no real values) and is in `.gitignore`.

## 4. Generate and load the daily data

```bash
python generator/backfill_2026.py          # deterministic parquets in generator/output (git-ignored)
set -a; source ~/.aisleiq/aisleiq.env; set +a
python ingestion/ingest.py                 # PUT to @RAW.LANDING, COPY INTO RAW, as AISLEIQ_LOADER
```

- The generator is the original one, ported; the same seeds reproduce the same data (checked frame by frame against the original files; the `pytest` suite covers its rules).
- `ingest.py` is idempotent: `PUT` never overwrites a staged file and `COPY INTO` keeps a load history per file, so a second run loads nothing and generating new days uploads only those days. It loads by column name and fills `source_file` (Snowflake metadata) and `source_date` (parsed from the file name by the tested `ingest_lib.py`).
- `COPY INTO` remembers a file for 64 days. A file staged longer ago than that is treated as "load status uncertain" and skipped, never loaded twice.
- The load role is `SNOWFLAKE_LOADER_ROLE` (default `AISLEIQ_LOADER`); dbt keeps using `AISLEIQ_TRANSFORMER`.

Then `dbt seed && dbt build` (inside `dbt/`), and `dbt source freshness` to check that `RAW` is up to date.

- `source_date` is not filled by `COPY INTO` itself, which only records `source_file` and `ingested_at`. A follow-up `UPDATE` (one statement for all files) fills it from the file name, only for rows still without a date, so a run that died after the load heals on the next one.
- Freshness thresholds in `dbt/models/staging/_sources.yml` (warn after 2 days, error after 7) are a production-like default, not from the spec. The synthetic data ends on 2026-08-10, so `dbt source freshness` reports an error until `RAW` is reloaded with newer days; that is expected for a static data set, not a pipeline fault.

## Environment conventions

- Dev (`AISLEIQ_DEV`) is the default target. Prod is only built by CI/orchestration.
- Schemas have clean names (`SEEDS`, `STAGING`, `MARTS`) in both environments: `dbt/macros/generate_schema_name.sql`.

## Checks and hooks

```bash
bash scripts/check.sh           # ruff, yamllint, sqlfluff, shellcheck, dbt parse, pytest, leak scan, text hygiene
bash scripts/install_hooks.sh   # once per clone: pre-commit leak scan + commit-msg format
```

CI runs exactly `scripts/check.sh`, plus a gitleaks scan, so a green local run means a green CI run. Commit messages must follow conventional commits (`feat: ...`) in plain ASCII English; accented text is only allowed in `GLOSSARY.md`.
