"""Uploads the daily synthetic parquet files to the internal stage and loads them into RAW.

Idempotent: PUT never overwrites a staged file, and COPY INTO keeps a load
history per staged file, so running it twice does not duplicate rows and
running it after new days were generated loads only those days.

Usage:
  python ingestion/ingest.py                         # both domains
  python ingestion/ingest.py --domain atendimento
  python ingestion/ingest.py --data-dir generator/output

Connection (key pair, no password) comes from the same SNOWFLAKE_* variables
as dbt (see .env.example). The load runs as SNOWFLAKE_LOADER_ROLE
(default AISLEIQ_LOADER), the only role that writes to RAW.
"""
import argparse
import os
import sys
from pathlib import Path

import snowflake.connector
from ingest_lib import DOMAINS, Domain, build_source_date_update, select_files_to_upload

STAGE = "LANDING"
DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "generator" / "output"

# Columns mirror the parquet files; the three trailing columns are file metadata.
TABLE_DDL = {
    "atendimento": """
        id_pesquisa_resposta NUMBER, id_usuario NUMBER, nome VARCHAR, cargo VARCHAR,
        id_loja NUMBER, categoria_loja VARCHAR, atendimento VARCHAR,
        data_checkin VARCHAR, hora_checkin VARCHAR, data_checkout VARCHAR, hora_checkout VARCHAR,
        raio_ckin FLOAT, distancia_ckin FLOAT, distancia_ckout FLOAT, tempo_loja FLOAT,
    """,
    "execucao_pdv": """
        id_pesquisa_resposta NUMBER, id_usuario NUMBER, nome VARCHAR, cargo VARCHAR,
        id_loja NUMBER, id_produto NUMBER, produto VARCHAR, marca VARCHAR, categoria_produto VARCHAR,
        indicador VARCHAR, grupo_pesquisa VARCHAR, desc_pergunta VARCHAR, resposta VARCHAR,
        checkin_valido BOOLEAN, dt_pesquisa VARCHAR, dt_gravacao VARCHAR,
    """,
}
METADATA_DDL = "source_file VARCHAR, source_date DATE, ingested_at TIMESTAMP_NTZ"


def connect() -> snowflake.connector.SnowflakeConnection:
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        private_key_file=os.environ["SNOWFLAKE_PRIVATE_KEY_PATH"],
        role=os.environ.get("SNOWFLAKE_LOADER_ROLE", "AISLEIQ_LOADER"),
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        database=os.environ["SNOWFLAKE_DATABASE"],
        schema="RAW",
    )


def ensure_table(cur, name: str, domain: Domain) -> None:
    cur.execute(f"CREATE TABLE IF NOT EXISTS {domain.table} ({TABLE_DDL[name]} {METADATA_DDL})")


def staged_names(cur, name: str) -> list[str]:
    cur.execute(f"LIST @{STAGE}/{name}/")
    return [row[0] for row in cur.fetchall()]


def put_files(cur, name: str, data_dir: Path, files: list[str]) -> None:
    for f in files:
        path = (data_dir / name / f).resolve().as_posix()
        cur.execute(f"PUT 'file://{path}' @{STAGE}/{name}/ AUTO_COMPRESS=FALSE OVERWRITE=FALSE")


def copy_into(cur, name: str, domain: Domain) -> int:
    """Loads the staged files that were not loaded yet; returns the rows loaded."""
    cur.execute(
        f"COPY INTO {domain.table} FROM @{STAGE}/{name}/ "
        "FILE_FORMAT = (TYPE = PARQUET) MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE "
        "INCLUDE_METADATA = (source_file = METADATA$FILENAME, ingested_at = METADATA$START_SCAN_TIME)"
    )
    # One row per file: (file, status, rows_parsed, rows_loaded, ...). A run with
    # nothing new returns a single status message instead.
    return sum(int(r[3]) for r in cur.fetchall() if len(r) > 3 and str(r[1]) == "LOADED")


def fill_source_dates(cur, name: str, domain: Domain) -> int:
    """Sets source_date, taken from the file name, on rows that do not have it yet.

    COPY INTO cannot compute it (INCLUDE_METADATA only carries Snowflake's own
    metadata), so it is filled here with the tested Python parser. Selecting by
    "source_date is null" makes a run that died after COPY heal on the next one.
    """
    cur.execute(f"SELECT DISTINCT source_file FROM {domain.table} WHERE source_date IS NULL")
    pending = [row[0] for row in cur.fetchall()]
    if pending:
        sql, params = build_source_date_update(domain, pending)
        cur.execute(sql, params)
    return len(pending)


def ingest(cur, name: str, data_dir: Path) -> None:
    domain = DOMAINS[name]
    local = sorted(p.name for p in (data_dir / name).glob("*.parquet"))
    ensure_table(cur, name, domain)
    new_files = select_files_to_upload(local, staged_names(cur, name), domain)
    put_files(cur, name, data_dir, new_files)
    loaded = copy_into(cur, name, domain)
    dated = fill_source_dates(cur, name, domain)
    print(f"[{name}] uploaded {len(new_files)} file(s), loaded {loaded} row(s), dated {dated} file(s)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--domain", choices=[*DOMAINS, "todos"], default="todos")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR, help="folder holding <domain>/*.parquet")
    args = parser.parse_args()

    names = list(DOMAINS) if args.domain == "todos" else [args.domain]
    for name in names:
        if not (args.data_dir / name).is_dir():
            print(f"missing folder {args.data_dir / name}; run generator/backfill_2026.py first", file=sys.stderr)
            return 1

    with connect() as conn, conn.cursor() as cur:
        for name in names:
            ingest(cur, name, args.data_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
