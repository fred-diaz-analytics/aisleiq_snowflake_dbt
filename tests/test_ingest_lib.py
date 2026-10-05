"""Unit tests for the pure ingestion logic (ingestion/ingest_lib.py).

No credentials, no network, no Snowflake: they run anywhere, including CI.
`ingest_lib` is resolved through `pythonpath` in pyproject.toml.
"""
from datetime import date

import pytest
from ingest_lib import (
    DOMAINS,
    parse_source_date,
    select_files_to_upload,
    source_date_from_name,
)

ATENDIMENTO = DOMAINS["atendimento"]
EXECUCAO = DOMAINS["execucao_pdv"]


class TestParseSourceDate:
    def test_valid_format(self):
        assert parse_source_date("20260115") == date(2026, 1, 15)

    def test_iso_format_is_rejected(self):
        with pytest.raises(ValueError):
            parse_source_date("2026-01-15")

    def test_empty_string_is_rejected(self):
        with pytest.raises(ValueError):
            parse_source_date("")


class TestSourceDateFromName:
    def test_plain_file_name(self):
        assert source_date_from_name("20260101_atendimento_synth.parquet", ATENDIMENTO) == date(2026, 1, 1)

    def test_stage_path_uses_only_the_file_name(self):
        name = "atendimento/20260810_atendimento_synth.parquet"
        assert source_date_from_name(name, ATENDIMENTO) == date(2026, 8, 10)

    def test_name_from_another_domain_is_rejected(self):
        with pytest.raises(ValueError):
            source_date_from_name("20260101_execucao_pdv_bronze_synth.parquet", ATENDIMENTO)

    def test_impossible_calendar_date_is_rejected(self):
        with pytest.raises(ValueError):
            source_date_from_name("20261345_atendimento_synth.parquet", ATENDIMENTO)


class TestSelectFilesToUpload:
    def test_picks_matching_files_in_date_order(self):
        local = [
            "20260105_atendimento_synth.parquet",
            "20260101_atendimento_synth.parquet",
            "README.md",
            "20260101_execucao_pdv_bronze_synth.parquet",
        ]
        assert select_files_to_upload(local, [], ATENDIMENTO) == [
            "20260101_atendimento_synth.parquet",
            "20260105_atendimento_synth.parquet",
        ]

    def test_skips_files_already_staged(self):
        local = ["20260101_atendimento_synth.parquet", "20260102_atendimento_synth.parquet"]
        staged = ["20260101_atendimento_synth.parquet"]
        assert select_files_to_upload(local, staged, ATENDIMENTO) == ["20260102_atendimento_synth.parquet"]

    def test_staged_names_may_carry_the_stage_path(self):
        local = ["20260101_atendimento_synth.parquet", "20260102_atendimento_synth.parquet"]
        staged = ["landing/atendimento/20260101_atendimento_synth.parquet"]
        assert select_files_to_upload(local, staged, ATENDIMENTO) == ["20260102_atendimento_synth.parquet"]

    def test_everything_staged_means_nothing_to_upload(self):
        local = ["20260101_execucao_pdv_bronze_synth.parquet"]
        assert select_files_to_upload(local, local, EXECUCAO) == []

    def test_empty_inputs(self):
        assert select_files_to_upload([], [], EXECUCAO) == []
