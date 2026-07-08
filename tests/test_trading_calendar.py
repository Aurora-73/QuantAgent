"""Tests for P0.2: Trading Calendar module.

Covers:
  - is_trading_day (weekend, holiday, weekday)
  - last_trading_day / next_trading_day (boundaries)
  - trading_days_between
  - refresh (mocked AKShare)
  - fallback (AKShare unavailable)
"""
from __future__ import annotations

from datetime import date
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

from data.storage import DataStorage
from data.trading_calendar import TradingCalendar, _FALLBACK_HOLIDAYS


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


# 已知的测试交易日（跳过周末和节假日）
# 2026-07-06(周一) 07-07(周二) 07-08(周三) 07-09(周四) 07-10(周五)
# 07-13(周一) 07-14(周二)
TEST_TRADING_DAYS = [
    date(2026, 7, 6), date(2026, 7, 7), date(2026, 7, 8),
    date(2026, 7, 9), date(2026, 7, 10),
    date(2026, 7, 13), date(2026, 7, 14),
]


# ============================================================
# is_trading_day
# ============================================================

class TestIsTradingDay:
    def test_weekday_is_trading_day(self, temp_storage: DataStorage):
        _seed_calendar(temp_storage, TEST_TRADING_DAYS)
        cal = TradingCalendar(storage=temp_storage)
        assert cal.is_trading_day(date(2026, 7, 8)) is True

    def test_weekend_not_trading_day(self, temp_storage: DataStorage):
        _seed_calendar(temp_storage, TEST_TRADING_DAYS)
        cal = TradingCalendar(storage=temp_storage)
        assert cal.is_trading_day(date(2026, 7, 11)) is False  # Saturday
        assert cal.is_trading_day(date(2026, 7, 12)) is False  # Sunday

    def test_holiday_not_trading_day(self, temp_storage: DataStorage):
        _seed_calendar(temp_storage, TEST_TRADING_DAYS)
        cal = TradingCalendar(storage=temp_storage)
        # 2026-10-01 is National Day (not in TEST_TRADING_DAYS)
        assert cal.is_trading_day(date(2026, 10, 1)) is False

    def test_default_today(self, temp_storage: DataStorage):
        _seed_calendar(temp_storage, TEST_TRADING_DAYS)
        cal = TradingCalendar(storage=temp_storage)
        today = date.today()
        result = cal.is_trading_day()
        assert result == (today in set(TEST_TRADING_DAYS))


# ============================================================
# last_trading_day / next_trading_day
# ============================================================

class TestLastNextTradingDay:
    def test_last_trading_day_on_trading_day(self, temp_storage: DataStorage):
        _seed_calendar(temp_storage, TEST_TRADING_DAYS)
        cal = TradingCalendar(storage=temp_storage)
        # 2026-07-08 is a trading day → last_trading_day should be itself
        assert cal.last_trading_day(date(2026, 7, 8)) == date(2026, 7, 8)

    def test_last_trading_day_on_weekend(self, temp_storage: DataStorage):
        _seed_calendar(temp_storage, TEST_TRADING_DAYS)
        cal = TradingCalendar(storage=temp_storage)
        # Saturday 2026-07-11 → last trading day is Friday 2026-07-10
        assert cal.last_trading_day(date(2026, 7, 11)) == date(2026, 7, 10)

    def test_last_trading_day_before_range(self, temp_storage: DataStorage):
        _seed_calendar(temp_storage, TEST_TRADING_DAYS)
        cal = TradingCalendar(storage=temp_storage)
        # Before any trading day in cache
        assert cal.last_trading_day(date(2020, 1, 1)) is None

    def test_next_trading_day_on_trading_day(self, temp_storage: DataStorage):
        _seed_calendar(temp_storage, TEST_TRADING_DAYS)
        cal = TradingCalendar(storage=temp_storage)
        # 2026-07-08 (Wed) → next is 2026-07-09 (Thu)
        assert cal.next_trading_day(date(2026, 7, 8)) == date(2026, 7, 9)

    def test_next_trading_day_on_weekend(self, temp_storage: DataStorage):
        _seed_calendar(temp_storage, TEST_TRADING_DAYS)
        cal = TradingCalendar(storage=temp_storage)
        # Saturday 2026-07-11 → next is Monday 2026-07-13
        assert cal.next_trading_day(date(2026, 7, 11)) == date(2026, 7, 13)

    def test_next_trading_day_after_range(self, temp_storage: DataStorage):
        _seed_calendar(temp_storage, TEST_TRADING_DAYS)
        cal = TradingCalendar(storage=temp_storage)
        # After all trading days in cache
        assert cal.next_trading_day(date(2030, 1, 1)) is None

    def test_boundary_friday_to_monday(self, temp_storage: DataStorage):
        _seed_calendar(temp_storage, TEST_TRADING_DAYS)
        cal = TradingCalendar(storage=temp_storage)
        # Friday 07-10 → next is Monday 07-13
        assert cal.next_trading_day(date(2026, 7, 10)) == date(2026, 7, 13)


# ============================================================
# trading_days_between
# ============================================================

class TestTradingDaysBetween:
    def test_full_range(self, temp_storage: DataStorage):
        _seed_calendar(temp_storage, TEST_TRADING_DAYS)
        cal = TradingCalendar(storage=temp_storage)
        result = cal.trading_days_between(date(2026, 7, 6), date(2026, 7, 10))
        assert result == [
            date(2026, 7, 6), date(2026, 7, 7), date(2026, 7, 8),
            date(2026, 7, 9), date(2026, 7, 10),
        ]

    def test_range_with_weekend(self, temp_storage: DataStorage):
        _seed_calendar(temp_storage, TEST_TRADING_DAYS)
        cal = TradingCalendar(storage=temp_storage)
        # 07-09 to 07-13 spans a weekend
        result = cal.trading_days_between(date(2026, 7, 9), date(2026, 7, 13))
        assert result == [date(2026, 7, 9), date(2026, 7, 10), date(2026, 7, 13)]

    def test_empty_range(self, temp_storage: DataStorage):
        _seed_calendar(temp_storage, TEST_TRADING_DAYS)
        cal = TradingCalendar(storage=temp_storage)
        result = cal.trading_days_between(date(2026, 8, 1), date(2026, 8, 5))
        assert result == []


# ============================================================
# refresh (mocked AKShare)
# ============================================================

class TestRefresh:
    def test_refresh_from_akshare(self, temp_storage: DataStorage):
        """refresh() pulls from AKShare and caches to DuckDB."""
        mock_df = pd.DataFrame({
            "trade_date": pd.to_datetime(["2026-07-06", "2026-07-07", "2026-07-08"])
        })

        cal = TradingCalendar(storage=temp_storage)
        with patch("akshare.tool_trade_date_hist_sina", return_value=mock_df):
            count = cal.refresh()

        assert count == 3
        assert cal.is_trading_day(date(2026, 7, 6)) is True
        assert cal.is_trading_day(date(2026, 7, 8)) is True

        # Verify persisted to DuckDB
        result = temp_storage.conn.execute(
            "SELECT COUNT(*) FROM trading_calendar"
        ).fetchone()
        assert result[0] == 3

    def test_refresh_empty_akshare(self, temp_storage: DataStorage):
        """refresh() with empty AKShare response returns 0."""
        cal = TradingCalendar(storage=temp_storage)
        with patch("akshare.tool_trade_date_hist_sina",
                   return_value=pd.DataFrame({"trade_date": []})):
            count = cal.refresh()
        assert count == 0


# ============================================================
# fallback (AKShare unavailable)
# ============================================================

class TestFallback:
    def test_fallback_when_no_cache_no_akshare(self, temp_storage: DataStorage):
        """When DuckDB cache empty and AKShare unavailable, use hardcoded holidays."""
        cal = TradingCalendar(storage=temp_storage)

        # Block AKShare by making import fail
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "akshare":
                raise ImportError("No module named 'akshare'")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            days = cal._load_trading_days()

        # Should have days (from hardcoded fallback logic)
        assert len(days) > 0
        # Weekend should not be a trading day
        assert cal.is_trading_day(date(2026, 7, 11)) is False  # Saturday
        # Known holiday should not be a trading day
        assert cal.is_trading_day(date(2026, 1, 1)) is False   # New Year
        # A regular weekday should be a trading day
        assert cal.is_trading_day(date(2026, 7, 8)) is True    # Wednesday
