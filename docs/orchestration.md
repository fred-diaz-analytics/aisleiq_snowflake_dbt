# Orchestration

## Single command

```bash
set -a; source ~/.aisleiq/aisleiq.env; set +a
bash scripts/run_all.sh [--target dev|prod] [--docs] [--regenerate]
```

It runs, in order: the fixed backfill (only when `generator/output` has no state, or with `--regenerate`), the catch-up `generator/job_diario.py` (every weekday missing up to today), `ingestion/ingest.py`, `dbt seed`, `dbt build`, and optionally `dbt docs generate`. The load goes to the database of the chosen target (`AISLEIQ_DEV` by default), so ingestion and dbt always agree. Ingestion is idempotent, so a repeated run loads nothing twice.

The runner starts empty every day, so the workflow regenerates the backfill and then the catch-up. That is reproducible: the state is chained from the deterministic backfill, and each day is seeded by its date. Only the new weekdays are uploaded and loaded.

## Daily schedule (GitHub Actions)

`.github/workflows/daily.yml` runs every day at 06:17 UTC and on demand (`workflow_dispatch`). It builds `AISLEIQ_PROD` with `scripts/run_all.sh --target prod --docs` and uploads the dbt docs as an artifact.

### Secrets in a public repository

Secrets, kept in a `production` environment (Settings, Environments):

| Secret | Content |
|---|---|
| `SNOWFLAKE_ACCOUNT` | account identifier |
| `SNOWFLAKE_USER` | the service user |
| `SNOWFLAKE_PRIVATE_KEY` | the full text of the private key (`.p8`) |

Only the key pair is used, with no password. How the exposure is limited:

- The workflow has no `pull_request` trigger and is limited to `main`. Forks do not receive secrets, and nobody without write access can start it.
- The key is written to a temporary file with mode 600 and deleted at the end of the job, even on failure. It never goes into a log: GitHub masks secret values.
- `permissions: contents: read` only. In the `production` environment, restrict deployment to the `main` branch.
- The service user holds only `AISLEIQ_LOADER` and `AISLEIQ_TRANSFORMER`, which reach the two AISLEIQ databases and nothing else (the same key can write dev and prod), and the resource monitor caps the monthly credits, so a leaked key has a bounded cost.

Remaining risks, to accept or mitigate:

- Anyone with write access can change the workflow on a branch of the same repository and read the secrets. Keep collaborators to a minimum, protect `main`, and add required reviewers to the `production` environment if others get access.
- A compromised third-party action runs with the secrets. Actions here are pinned by major version; pin by commit SHA for stricter control.
- If the key leaks, rotate it: generate a new pair with the wizard, `ALTER USER ... SET RSA_PUBLIC_KEY`, update the secret.
- GitHub disables scheduled workflows after 60 days without repository activity; re-enable it in the Actions tab.
- The trial expires. After that, the schedule fails until you rebuild the environment (`docs/setup.md`) and update the secrets.

## Not in scope

Snowflake Tasks, Snowpipe and dynamic tables as orchestration. dbt Cloud and dbt Fusion are optional studies (README, ideas to continue).
