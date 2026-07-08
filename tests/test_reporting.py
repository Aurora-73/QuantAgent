"""Tests for B1.3: Higher-order report generation (weekly/monthly/quarterly).

Covers:
  - Generators don't crash on empty DB (return reasonable markdown)
  - save_report -> load_report roundtrip
  - File naming follows KnowledgeBase.save_report rules
  - list_reports non-empty after generation
  - Seeded factors/events appear in report content
  - Invalid report type raises ValueError
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from data.storage import DataStorage
from data.trading_calendar import TradingCalendar
from knowledge.knowledge_base import KnowledgeBase
from research.reporting import (
    generate_weekly_report,
    generate_monthly_report,
    generate_quarterly_report,
    save_report,
    _safe_pct,
    _safe_float,
)


# ============================================================
# Helpers
# ============================================================

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


def _make_trading_days(start: date, n: int) -> list[date]:
    """Generate n weekdays starting from start (skips weekends)."""
    days = []
    d = start
    while len(days) < n:
        if d.weekday() < 5:
            days.append(d)
        d += __import__("datetime").timedelta(days=1)
    return days


# 70 trading days to cover quarterly (60) window with margin
TEST_DAYS = _make_trading_days(date(2026, 1, 5), 70)


# ============================================================
# Generators on empty DB
# ============================================================

class TestGeneratorsEmptyDB:
    def test_weekly_report_empty_db(self, temp_storage: DataStorage):
        """Weekly report on empty DB returns markdown, does not crash."""
        _seed_calendar(temp_storage, TEST_DAYS)
        cal = TradingCalendar(storage=temp_storage)
        content = generate_weekly_report(date(2026, 4, 10), temp_storage, cal)

        assert isinstance(content, str)
        assert "# 周报" in content
        assert "数据新鲜度" in content
        assert "决策准确率" in content

    def test_monthly_report_empty_db(self, temp_storage: DataStorage):
        """Monthly report on empty DB returns markdown, does not crash."""
        _seed_calendar(temp_storage, TEST_DAYS)
        cal = TradingCalendar(storage=temp_storage)
        content = generate_monthly_report(date(2026, 4, 10), temp_storage, cal)

        assert isinstance(content, str)
        assert "# 月报" in content
        assert "月度决策准确率" in content

    def test_quarterly_report_empty_db(self, temp_storage: DataStorage):
        """Quarterly report on empty DB returns markdown, does not crash."""
        _seed_calendar(temp_storage, TEST_DAYS)
        cal = TradingCalendar(storage=temp_storage)
        content = generate_quarterly_report(date(2026, 4, 10), temp_storage, cal)

        assert isinstance(content, str)
        assert "# 季报" in content
        assert "季度市场风格" in content

    def test_weekly_report_no_trading_days(self, temp_storage: DataStorage):
        """When no trading days available, returns graceful message."""
        from unittest.mock import MagicMock
        cal = MagicMock()
        cal.last_trading_day.return_value = None
        cal.trading_days_between.return_value = []
        content = generate_weekly_report(date(2026, 4, 10), temp_storage, cal)
        assert "无交易日数据" in content


# ============================================================
# save_report -> load_report roundtrip
# ============================================================

class TestSaveReportRoundtrip:
    def test_weekly_save_and_load(self, temp_storage: DataStorage, temp_kb: KnowledgeBase):
        """save_report then load_report returns the same content."""
        _seed_calendar(temp_storage, TEST_DAYS)
        target = date(2026, 4, 10)  # Friday

        path = save_report("weekly", target, storage=temp_storage, kb=temp_kb)
        assert path is not None
        assert path.exists()

        loaded = temp_kb.load_report("weekly", target)
        assert loaded is not None
        assert "# 周报" in loaded

    def test_monthly_save_and_load(self, temp_storage: DataStorage, temp_kb: KnowledgeBase):
        """Monthly report roundtrip."""
        _seed_calendar(temp_storage, TEST_DAYS)
        target = date(2026, 4, 10)

        path = save_report("monthly", target, storage=temp_storage, kb=temp_kb)
        assert path is not None

        loaded = temp_kb.load_report("monthly", target)
        assert loaded is not None
        assert "# 月报" in loaded

    def test_quarterly_save_and_load(self, temp_storage: DataStorage, temp_kb: KnowledgeBase):
        """Quarterly report roundtrip."""
        _seed_calendar(temp_storage, TEST_DAYS)
        target = date(2026, 4, 10)  # Q2

        path = save_report("quarterly", target, storage=temp_storage, kb=temp_kb)
        assert path is not None

        loaded = temp_kb.load_report("quarterly", target)
        assert loaded is not None
        assert "# 季报" in loaded
        assert "Q2" in loaded


# ============================================================
# File naming rules
# ============================================================

class TestFileNaming:
    def test_weekly_filename(self, temp_storage: DataStorage, temp_kb: KnowledgeBase):
        """Weekly report filename follows week{WW}-{YYYY}.md rule."""
        _seed_calendar(temp_storage, TEST_DAYS)
        target = date(2026, 4, 10)  # ISO week 15 of 2026

        path = save_report("weekly", target, storage=temp_storage, kb=temp_kb)
        expected_week = target.isocalendar()[1]
        expected_name = f"week{expected_week:02d}-{target.year}.md"
        assert path.name == expected_name

    def test_monthly_filename(self, temp_storage: DataStorage, temp_kb: KnowledgeBase):
        """Monthly report filename follows {YYYY}-{MM}.md rule."""
        _seed_calendar(temp_storage, TEST_DAYS)
        target = date(2026, 4, 10)

        path = save_report("monthly", target, storage=temp_storage, kb=temp_kb)
        expected_name = f"{target.year}-{target.month:02d}.md"
        assert path.name == expected_name

    def test_quarterly_filename(self, temp_storage: DataStorage, temp_kb: KnowledgeBase):
        """Quarterly report filename follows Q{Q}-{YYYY}.md rule."""
        _seed_calendar(temp_storage, TEST_DAYS)
        target = date(2026, 4, 10)  # Q2

        path = save_report("quarterly", target, storage=temp_storage, kb=temp_kb)
        quarter = (target.month - 1) // 3 + 1
        expected_name = f"Q{quarter}-{target.year}.md"
        assert path.name == expected_name


# ============================================================
# list_reports non-empty after generation
# ============================================================

class TestListReports:
    def test_weekly_listed_after_generation(self, temp_storage: DataStorage, temp_kb: KnowledgeBase):
        """kb.list_reports('weekly') is non-empty after save_report."""
        _seed_calendar(temp_storage, TEST_DAYS)
        save_report("weekly", date(2026, 4, 10), storage=temp_storage, kb=temp_kb)

        reports = temp_kb.list_reports("weekly")
        assert len(reports) >= 1

    def test_all_three_types_listed(self, temp_storage: DataStorage, temp_kb: KnowledgeBase):
        """All three report types appear in their respective list_reports."""
        _seed_calendar(temp_storage, TEST_DAYS)
        target = date(2026, 4, 10)
        save_report("weekly", target, storage=temp_storage, kb=temp_kb)
        save_report("monthly", target, storage=temp_storage, kb=temp_kb)
        save_report("quarterly", target, storage=temp_storage, kb=temp_kb)

        assert len(temp_kb.list_reports("weekly")) >= 1
        assert len(temp_kb.list_reports("monthly")) >= 1
        assert len(temp_kb.list_reports("quarterly")) >= 1


# ============================================================
# Seeded data appears in report
# ============================================================

class TestSeededDataInReport:
    def test_factors_appear_in_weekly_report(self, temp_storage: DataStorage):
        """Seeded factor data shows up in weekly report table."""
        _seed_calendar(temp_storage, TEST_DAYS)
        cal = TradingCalendar(storage=temp_storage)

        # Seed factors for recent dates
        recent_days = TEST_DAYS[-5:]
        rows = []
        for d in recent_days:
            rows.append(("600519", d, "momentum", 0.85))
            rows.append(("600519", d, "reversal", -0.32))
        df = pd.DataFrame(rows, columns=["ticker", "date", "factor_name", "factor_value"])
        temp_storage.conn.execute("DELETE FROM factors")
        temp_storage.conn.execute("""
            INSERT INTO factors (ticker, date, factor_name, factor_value)
            SELECT ticker, date, factor_name, factor_value FROM df
        """)

        content = generate_weekly_report(recent_days[-1], temp_storage, cal)
        assert "momentum" in content
        assert "因子表现" in content

    def test_events_appear_in_weekly_report(self, temp_storage: DataStorage):
        """Seeded events show up in weekly report."""
        _seed_calendar(temp_storage, TEST_DAYS)
        cal = TradingCalendar(storage=temp_storage)

        recent_days = TEST_DAYS[-5:]
        rows = []
        for d in recent_days:
            rows.append((f"evt_{d.isoformat()}", d, "news", "earnings",
                         "600519", "Moutai", "beat estimates", "positive", 0.9))
        df = pd.DataFrame(rows, columns=[
            "event_id", "timestamp", "source", "event_type", "ticker",
            "company", "detail", "sentiment", "confidence",
        ])
        temp_storage.conn.execute("DELETE FROM events")
        temp_storage.conn.execute("""
            INSERT INTO events (event_id, timestamp, source, event_type, ticker,
                                company, detail, sentiment, confidence)
            SELECT event_id, timestamp, source, event_type, ticker,
                   company, detail, sentiment, confidence FROM df
        """)

        content = generate_weekly_report(recent_days[-1], temp_storage, cal)
        assert "市场事件" in content
        assert "earnings" in content or "positive" in content

    def test_index_appears_in_quarterly_report(self, temp_storage: DataStorage):
        """Seeded index data shows up in quarterly report market style section."""
        _seed_calendar(temp_storage, TEST_DAYS)
        cal = TradingCalendar(storage=temp_storage)

        # Seed index_daily for 000300
        idx_days = TEST_DAYS[-60:]
        closes = [3500.0 + i * 5 for i in range(len(idx_days))]
        df = pd.DataFrame({
            "index_code": ["000300"] * len(idx_days),
            "date": idx_days,
            "open": closes,
            "high": [c + 10 for c in closes],
            "low": [c - 10 for c in closes],
            "close": closes,
            "volume": [10_000_000] * len(idx_days),
        })
        temp_storage.conn.execute("DELETE FROM index_daily WHERE index_code = '000300'")
        temp_storage.conn.execute("""
            INSERT INTO index_daily (index_code, date, open, high, low, close, volume)
            SELECT index_code, date, open, high, low, close, volume FROM df
        """)

        content = generate_quarterly_report(idx_days[-1], temp_storage, cal)
        assert "沪深300" in content
        assert "季度收益" in content


# ============================================================
# Error handling
# ============================================================

class TestErrorHandling:
    def test_invalid_report_type_raises(self, temp_storage: DataStorage):
        """Invalid report type raises ValueError."""
        _seed_calendar(temp_storage, TEST_DAYS)
        with pytest.raises(ValueError, match="不支持的报告类型"):
            save_report("annual", date(2026, 4, 10), storage=temp_storage)

    def test_save_report_returns_none_on_failure(self, temp_storage: DataStorage,
                                                  temp_kb: KnowledgeBase, monkeypatch):
        """save_report returns None when generator raises."""
        _seed_calendar(temp_storage, TEST_DAYS)

        def boom(*args, **kwargs):
            raise RuntimeError("injected failure")

        monkeypatch.setattr("research.reporting.generate_weekly_report", boom)
        result = save_report("weekly", date(2026, 4, 10),
                             storage=temp_storage, kb=temp_kb)
        assert result is None


# ============================================================
# Helper functions
# ============================================================

class TestHelpers:
    def test_safe_pct_with_value(self):
        assert _safe_pct(0.1234) == "12.34%"

    def test_safe_pct_with_none(self):
        assert _safe_pct(None) == "N/A"

    def test_safe_pct_with_nan(self):
        assert _safe_pct(float("nan")) == "N/A"

    def test_safe_float_with_value(self):
        assert _safe_float(3.14159, 2) == "3.14"

    def test_safe_float_with_none(self):
        assert _safe_float(None) == "N/A"
