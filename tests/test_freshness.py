"""Tests for P0.3: storage layer freshness API.

Covers:
  - FreshnessStatus enum
  - get_freshness (empty table, fresh, stale, outdated)
  - FRESHNESS_RULES (trading day vs calendar day tables)
  - get_freshness for events (calendar day) and financials (90-day lag)
"""
from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import patch

import pandas as pd
import pytest

from data.storage import DataStorage, FreshnessStatus, FRESHNESS_RULES


def _seed_trading_calendar(storage: DataStorage, dates: list[date]):
    """Populate trading_calendar table for freshness trading-day calculations."""
    storage.conn.execute("""
        CREATE TABLE IF NOT EXISTS trading_calendar (
            trade_date DATE PRIMARY KEY
        )
    """)
    df = pd.DataFrame({"trade_date": dates})
    storage.conn.execute("DELETE FROM trading_calendar")
    storage.conn.execute("INSERT INTO trading_calendar SELECT * FROM df")


def _seed_stock_data(storage: DataStorage, ticker: str, last_date: date):
    """Insert one row of stock data on last_date."""
    df = pd.DataFrame({
        "date": [last_date.isoformat()],
        "open": [10.0], "high": [11.0], "low": [9.5], "close": [10.5],
        "volume": [10000], "amount": [1e5], "pct_change": [0.05],
        "turnover": [0.01],
    })
    storage.save_stock_daily(ticker, df)


def _seed_index_data(storage: DataStorage, index_code: str, last_date: date):
    df = pd.DataFrame({
        "date": [last_date.isoformat()],
        "open": [4000.0], "high": [4050.0], "low": [3980.0],
        "close": [4030.0], "volume": [5e8],
    })
    storage.save_index_daily(index_code, df)


# ============================================================
# FreshnessStatus enum
# ============================================================

class TestFreshnessStatus:
    def test_enum_values(self):
        assert FreshnessStatus.FRESH.value == "fresh"
        assert FreshnessStatus.STALE.value == "stale"
        assert FreshnessStatus.OUTDATED.value == "outdated"

    def test_enum_distinct(self):
        values = {s.value for s in FreshnessStatus}
        assert len(values) == 3


# ============================================================
# FRESHNESS_RULES
# ============================================================

class TestFreshnessRules:
    def test_stock_daily_uses_trading_days(self):
        use_td, lag = FRESHNESS_RULES["stock_daily"]
        assert use_td is True
        assert lag == 1

    def test_events_uses_calendar_days(self):
        use_td, lag = FRESHNESS_RULES["events"]
        assert use_td is False
        assert lag == 1

    def test_financials_has_90_day_lag(self):
        use_td, lag = FRESHNESS_RULES["financials"]
        assert use_td is False
        assert lag == 90

    def test_all_supported_tables(self):
        expected = {"stock_daily", "index_daily", "factors", "events", "financials"}
        assert set(FRESHNESS_RULES.keys()) == expected


# ============================================================
# get_freshness
# ============================================================

class TestGetFreshness:
    def test_empty_table_outdated(self, temp_storage: DataStorage):
        info = temp_storage.get_freshness("stock_daily")
        assert info["last_date"] is None
        assert info["staleness_days"] is None
        assert info["status"] == "outdated"
        assert info["allowed_lag"] == 1

    def test_unsupported_table_raises(self, temp_storage: DataStorage):
        with pytest.raises(ValueError, match="无 freshness 规则"):
            temp_storage.get_freshness("nonexistent")

    def test_fresh_data(self, temp_storage: DataStorage):
        """Data from the most recent trading day → FRESH."""
        today = date.today()
        # Seed trading calendar with today as a trading day
        _seed_trading_calendar(temp_storage, [today, today - timedelta(days=1)])
        _seed_stock_data(temp_storage, "TEST001", today)

        info = temp_storage.get_freshness("stock_daily")
        assert info["last_date"] == today
        assert info["staleness_days"] == 0
        assert info["status"] == "fresh"

    def test_stale_data(self, temp_storage: DataStorage):
        """Data 2 trading days behind → STALE (allowed_lag=1, 2x=2)."""
        today = date.today()
        # Trading days: today, today-1, today-2 (3 trading days)
        cal_days = [today, today - timedelta(days=1), today - timedelta(days=2)]
        _seed_trading_calendar(temp_storage, cal_days)
        # Data is from 2 trading days ago → staleness = 2 → STALE
        _seed_stock_data(temp_storage, "TEST001", today - timedelta(days=2))

        info = temp_storage.get_freshness("stock_daily")
        assert info["staleness_days"] == 2
        assert info["status"] == "stale"

    def test_outdated_data(self, temp_storage: DataStorage):
        """Data 5 trading days behind → OUTDATED (> 2x allowed_lag)."""
        today = date.today()
        cal_days = [today - timedelta(days=i) for i in range(6)]
        _seed_trading_calendar(temp_storage, cal_days)
        _seed_stock_data(temp_storage, "TEST001", today - timedelta(days=5))

        info = temp_storage.get_freshness("stock_daily")
        assert info["staleness_days"] == 5
        assert info["status"] == "outdated"

    def test_events_calendar_day_calculation(self, temp_storage: DataStorage):
        """Events table uses calendar days, not trading days."""
        today = date.today()
        # Insert an event 3 days ago
        from datetime import datetime
        storage = temp_storage
        storage.conn.execute("""
            INSERT INTO events (event_id, timestamp, source, event_type, ticker,
                              company, detail, sentiment, confidence)
            VALUES (?, ?, 'test', 'news', 'TEST', 'TestCo', 'detail', 'neutral', 0.5)
        """, ["evt1", datetime(today.year, today.month, today.day) - timedelta(days=3)])

        info = storage.get_freshness("events")
        assert info["use_trading_days"] is False
        assert info["staleness_days"] == 3
        assert info["status"] == "outdated"  # 3 > 2*1

    def test_financials_90_day_lag(self, temp_storage: DataStorage):
        """Financials allows 90-day lag."""
        today = date.today()
        # Insert financial data 30 days ago → should be FRESH (30 <= 90)
        old_date = today - timedelta(days=30)
        storage = temp_storage
        storage.conn.execute("""
            INSERT INTO research.financials (ticker, report_date, report_type,
                              revenue, net_profit, roe, total_assets, equity, eps)
            VALUES (?, ?, 'quarterly', 1e8, 1e7, 0.15, 1e9, 5e8, 1.0)
        """, ["TEST001", old_date])

        info = storage.get_freshness("financials")
        assert info["allowed_lag"] == 90
        assert info["staleness_days"] == 30
        assert info["status"] == "fresh"

    def test_index_daily_freshness(self, temp_storage: DataStorage):
        """Index daily uses trading day calendar like stock_daily."""
        today = date.today()
        _seed_trading_calendar(temp_storage, [today])
        _seed_index_data(temp_storage, "000300", today)

        info = temp_storage.get_freshness("index_daily")
        assert info["last_date"] == today
        assert info["staleness_days"] == 0
        assert info["status"] == "fresh"


# ============================================================
# _trading_day_lag fallback
# ============================================================

class TestTradingDayLagFallback:
    def test_fallback_to_calendar_days(self, temp_storage: DataStorage):
        """When TradingCalendar fails, fall back to calendar day calculation."""
        today = date.today()
        _seed_stock_data(temp_storage, "TEST001", today - timedelta(days=5))

        # Patch TradingCalendar to raise
        with patch("data.trading_calendar.TradingCalendar",
                   side_effect=Exception("mock failure")):
            info = temp_storage.get_freshness("stock_daily")

        # Should still return a result (fallback to calendar days)
        assert info["last_date"] == today - timedelta(days=5)
        assert info["staleness_days"] == 5
        assert info["status"] == "outdated"
