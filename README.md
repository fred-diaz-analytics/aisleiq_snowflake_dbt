# AisleIQ on Snowflake + dbt

[Leia em português](README.pt-BR.md)

Point-of-sale execution analytics (trade marketing) over 100% synthetic data: how products are displayed, priced and signposted in stores, and how field promoters carry out their visits. This is the Snowflake + dbt rebuild of AisleIQ, with the same domain and the same synthetic generator as the original Databricks version. No real data or PII.

Business terms stay in Portuguese (see [`GLOSSARY.md`](GLOSSARY.md)); technical conventions are in English.

## How it works

```
generator (parquet, daily files)
   -> ingestion/ingest.py (PUT to stage, COPY INTO)  -> RAW
   -> dbt seeds (master data)                         -> SEEDS
   -> dbt staging (typing, dedupe, quality flags)     -> STAGING
   -> dbt marts (indicators, dimensions, scores)      -> MARTS
```

Full picture, layer map and lineage: [`docs/architecture.md`](docs/architecture.md).

## Documentation

| Document | What it covers |
|---|---|
| [`docs/architecture.md`](docs/architecture.md) | Layers, bronze/silver/gold to RAW/STAGING/MARTS map, lineage |
| [`docs/indicators.md`](docs/indicators.md) | Data dictionary: indicators, dimensions, score graph |
| [`docs/dialect-guide.md`](docs/dialect-guide.md) | Databricks to Snowflake SQL differences found in the migration |
| [`docs/dbt-conventions.md`](docs/dbt-conventions.md) | Naming, tests, materialization decisions |
| [`docs/setup.md`](docs/setup.md) | Build the environment from scratch (also after the trial expires) |
| [`docs/orchestration.md`](docs/orchestration.md) | Single command, daily GitHub Actions schedule, secrets in a public repo |

## Quick start

```bash
python -m venv .venv && .venv/Scripts/python.exe -m pip install -r requirements-dev.txt   # Windows
bash scripts/setup_snowflake.sh            # guided provisioning, once per account
set -a; source ~/.aisleiq/aisleiq.env; set +a
bash scripts/run_all.sh                    # generate, ingest, dbt seed + build (dev)
```

`bash scripts/run_all.sh --docs` also generates the dbt documentation site; serve it with `dbt docs serve` inside `dbt/`.

## Acceptance

The migration is accepted when `dbt build` passes in `AISLEIQ_DEV` and the KPIs in `MARTS` recover the planted truth (`dbt/tests/verdade_plantada.sql`).

## Checks

`bash scripts/check.sh` runs ruff, yamllint, sqlfluff (Snowflake dialect), shellcheck, `dbt parse`, pytest and a leak scan, with no credentials. CI runs the same script.

## Ideas to continue

- Run the same project on dbt Cloud (free tier) to try its managed scheduler and CI.
- Run it on dbt Fusion and compare with dbt-core.
- Try Snowflake Tasks as the scheduler and compare with GitHub Actions.
