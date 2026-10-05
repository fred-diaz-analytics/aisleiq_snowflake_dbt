"""Unit tests for the pure catch-up logic of the daily job (generator/job_diario.py)."""
from datetime import date

from job_diario import dias_uteis_faltantes


def test_no_history_generates_only_the_end_date():
    assert dias_uteis_faltantes(None, date(2026, 8, 12)) == [date(2026, 8, 12)]


def test_catch_up_skips_weekends():
    # 2026-08-10 is a Monday; 08-15 and 08-16 are Saturday and Sunday.
    assert dias_uteis_faltantes(date(2026, 8, 10), date(2026, 8, 17)) == [
        date(2026, 8, 11),
        date(2026, 8, 12),
        date(2026, 8, 13),
        date(2026, 8, 14),
        date(2026, 8, 17),
    ]


def test_up_to_date_returns_nothing():
    assert dias_uteis_faltantes(date(2026, 8, 12), date(2026, 8, 12)) == []


def test_end_date_on_a_weekend_returns_nothing_new():
    assert dias_uteis_faltantes(date(2026, 8, 14), date(2026, 8, 16)) == []
