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
| Databases | `AISLEIQ_DEV`, `AISLEIQ_PROD` (each with `RAW`, `STAGING`, `MARTS`) |
| Roles | `AISLEIQ_LOADER` (writes to `RAW`), `AISLEIQ_TRANSFORMER` (reads `RAW`, writes to `STAGING` and `MARTS`) |
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

## Environment conventions

- Dev (`AISLEIQ_DEV`) is the default target. Prod is only built by CI/orchestration.
- Schemas have clean names (`STAGING`, `MARTS`) in both environments: `dbt/macros/generate_schema_name.sql`.
