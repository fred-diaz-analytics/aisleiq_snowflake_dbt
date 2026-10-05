"""Pure ingestion logic, with no Snowflake dependency.

`ingest.py` imports these functions and handles only what needs a connection
(PUT, COPY INTO, DDL). Everything here is unit-tested offline in
tests/test_ingest_lib.py.
"""
import re
from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class Domain:
    """One daily-file domain: where its files live and where they land."""

    table: str  # RAW table name
    file_regex: str  # matches the daily file name; group 1 is the YYYYMMDD date


DOMAINS = {
    "atendimento": Domain(table="atendimentos", file_regex=r"(\d{8}).*atendimento.*\.parquet$"),
    "execucao_pdv": Domain(table="execucao_pdv", file_regex=r"(\d{8}).*execucao_pdv.*\.parquet$"),
}


def parse_source_date(date_str: str) -> date:
    """Turn 'YYYYMMDD' (taken from the file name) into a date."""
    return datetime.strptime(date_str, "%Y%m%d").date()  # noqa: DTZ007 (a calendar date, no time zone)


def _base_name(name: str) -> str:
    return name.replace("\\", "/").split("/")[-1]


def source_date_from_name(name: str, domain: Domain) -> date:
    """Source date encoded in a daily file name (a stage path is accepted).

    Raises ValueError when the name does not belong to the domain or holds an
    impossible calendar date.
    """
    match = re.search(domain.file_regex, _base_name(name))
    if not match:
        raise ValueError(f"file name does not match the domain pattern: {name}")
    return parse_source_date(match.group(1))


def select_files_to_upload(local_names: list[str], staged_names: list[str], domain: Domain) -> list[str]:
    """Daily files of the domain that are not in the stage yet, oldest first.

    Staged names may carry the stage path (as LIST returns them); only the
    file name is compared. Nothing here touches the network.
    """
    staged = {_base_name(n) for n in staged_names}
    pattern = re.compile(domain.file_regex)
    candidates = []
    for name in local_names:
        match = pattern.search(name)
        if match and name not in staged:
            candidates.append((match.group(1), name))
    return [name for _, name in sorted(candidates)]


def build_source_date_update(domain: Domain, source_files: list[str]) -> tuple[str, list]:
    """One UPDATE that dates every given file at once, with its bind parameters.

    One statement for all files instead of one per file: the full backfill has
    158 files and per-file updates took minutes. Only rows still without a date
    are touched, so a rerun is harmless. Raises ValueError for a name that does
    not belong to the domain.
    """
    params: list = []
    for source_file in source_files:
        params += [source_file, source_date_from_name(source_file, domain)]
    rows = ", ".join(["(%s, %s)"] * len(source_files))
    sql = (
        f"UPDATE {domain.table} AS t SET source_date = d.source_date "
        f"FROM (SELECT column1 AS source_file, column2::DATE AS source_date FROM VALUES {rows}) AS d "
        "WHERE t.source_file = d.source_file AND t.source_date IS NULL"
    )
    return sql, params
