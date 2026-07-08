"""Tests for B1.3: Scheduler integration for higher-order reports.

Covers:
  - is_last_trading_day_of_month (true/false/non-trading-day)
  - is_last_trading_day_of_quarter (true/false)
  - run_scheduled_reports (non-trading-day skip, Friday weekly, month-end monthly)
"""
from __future__ import annotations

from datetime import date
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

from data.storage import DataStorage
from data.trading_calendar import TradingCalendar
from scripts.scheduler import (
    is_last_trading_day_of_month,
    is_last_trading_day_of_quarter,
    run_scheduled_reports,
)


def _seed_calendar(storage: DataStorage, dates: list[date]):
    """Populate trading_calendar table with known dates."""
    storage.conn.execute("""
        CREATE TABLE IF NOT EXISTS trading_calendar (
            trade_date DATE PRIMARY KEY
        )
    """)
    df = pd.DataFrame({"trade_date": dates})
    storage.conn.execute("DELETE FROM trading_calendar")
    storage.conn.execute("INSERT INTO trading_calendar SELECT * FROM df")


# Trading days spanning month and quarter boundaries:
# 2026-03-30(Mon), 03-31(Tue) <- last of March/Q1
# 2026-04-01(Wed), 04-02(Thu), 04-03(Fri) <- first of April/Q2
# 2026-06-29(Mon), 06-30(Tue) <- last of June/Q2
# 2026-07-01(Wed) <- first of July/Q3
BOUNDARY_DAYS = [
    date(2026, 3, 30), date(2026, 3, 31),
    date(2026, 4, 1), date(2026, 4, 2), date(2026, 4, 3),
    date(2026, 6, 29), date(2026, 6, 30),
    date(2026, 7, 1),
]


# ============================================================
# is_last_trading_day_of_month
# ============================================================

class TestLastTradingDayOfMonth:
    def test_last_day_of_month(self, temp_storage: DataStorage):
        _seed_calendar(temp_storage, BOUNDARY_DAYS)
        cal = TradingCalendar(storage=temp_storage)
        # 2026-03-31 is the last trading day of March (next is 04-01)
        assert is_last_trading_day_of_month(cal, date(2026, 3, 31)) is True

    def test_mid_month_not_last(self, temp_storage: DataStorage):
        _seed_calendar(temp_storage, BOUNDARY_DAYS)
        cal = TradingCalendar(storage=temp_storage)
        # 2026-04-01 is not last (next is 04-02, same month)
        assert is_last_trading_day_of_month(cal, date(2026, 4, 1)) is False

    def test_non_trading_day_returns_false(self, temp_storage: DataStorage):
        _seed_calendar(temp_storage, BOUNDARY_DAYS)
        cal = TradingCalendar(storage=temp_storage)
        # Saturday is not a trading day
        assert is_last_trading_day_of_month(cal, date(2026, 4, 4)) is False

    def test_june_end(self, temp_storage: DataStorage):
        _seed_calendar(temp_storage, BOUNDARY_DAYS)
        cal = TradingCalendar(storage=temp_storage)
        # 2026-06-30 is the last trading day of June
        assert is_last_trading_day_of_month(cal, date(2026, 6, 30)) is True


# ============================================================
# is_last_trading_day_of_quarter
# ============================================================

class TestLastTradingDayOfQuarter:
    def test_end_of_q1(self, temp_storage: DataStorage):
        _seed_calendar(temp_storage, BOUNDARY_DAYS)
        cal = TradingCalendar(storage=temp_storage)
        # 2026-03-31 is last trading day of Q1 (next 04-01 is Q2)
        assert is_last_trading_day_of_quarter(cal, date(2026, 3, 31)) is True

    def test_end_of_q2(self, temp_storage: DataStorage):
        _seed_calendar(temp_storage, BOUNDARY_DAYS)
        cal = TradingCalendar(storage=temp_storage)
        # 2026-06-30 is last trading day of Q2 (next 07-01 is Q3)
        assert is_last_trading_day_of_quarter(cal, date(2026, 6, 30)) is True

    def test_mid_quarter_not_last(self, temp_storage: DataStorage):
        _seed_calendar(temp_storage, BOUNDARY_DAYS)
        cal = TradingCalendar(storage=temp_storage)
        # 2026-04-02 is mid-Q2 (next 04-03 is same quarter)
        assert is_last_trading_day_of_quarter(cal, date(2026, 4, 2)) is False

    def test_non_trading_day_returns_false(self, temp_storage: DataStorage):
        _seed_calendar(temp_storage, BOUNDARY_DAYS)
        cal = TradingCalendar(storage=temp_storage)
        assert is_last_trading_day_of_quarter(cal, date(2026, 4, 4)) is False


# ============================================================
# run_scheduled_reports
# ============================================================

class TestRunScheduledReports:
    def test_non_trading_day_skips(self, temp_storage: DataStorage):
        """Non-trading day should skip report generation entirely."""
        _seed_calendar(temp_storage, BOUNDARY_DAYS)
        cal = TradingCalendar(storage=temp_storage)

        with patch("scripts.scheduler._get_calendar", return_value=cal), \
             patch("research.reporting.save_report") as mock_save:
            run_scheduled_reports()

        mock_save.assert_not_called()

    def test_friday_generates_weekly(self, temp_storage: DataStorage):
        """Friday trading day triggers weekly report."""
        # 2026-04-03 is a Friday
        friday = date(2026, 4, 3)
        _seed_calendar(temp_storage, BOUNDARY_DAYS)
        cal = TradingCalendar(storage=temp_storage)

        from pathlib import Path
        with patch("scripts.scheduler._get_calendar", return_value=cal), \
             patch("scripts.scheduler.date") as mock_date, \
             patch("research.reporting.save_report", return_value=Path("week15-2026.md")) as mock_save:
            mock_date.today.return_value = friday
            mock_date.side_effect = lambda *a, **k: date(*a, **k)
            run_scheduled_reports()

        # weekly report should have been generated
        calls = {c.args[0] for c in mock_save.call_args_list}
        assert "weekly" in calls

    def test_month_end_generates_monthly(self, temp_storage: DataStorage):
        """Last trading day of month triggers monthly report."""
        month_end = date(2026, 3, 31)  # Tuesday, last of March
        _seed_calendar(temp_storage, BOUNDARY_DAYS)
        cal = TradingCalendar(storage=temp_storage)

        from pathlib import Path
        with patch("scripts.scheduler._get_calendar", return_value=cal), \
             patch("scripts.scheduler.date") as mock_date, \
             patch("research.reporting.save_report", return_value=Path("2026-03.md")) as mock_save:
            mock_date.today.return_value = month_end
            mock_date.side_effect = lambda *a, **k: date(*a, **k)
            run_scheduled_reports()

        calls = {c.args[0] for c in mock_save.call_args_list}
        assert "monthly" in calls
