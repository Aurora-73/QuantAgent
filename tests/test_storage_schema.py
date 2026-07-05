"""DataStorage schema-aware operations tests — dual-write, schema queries."""
from __future__ import annotations

import pandas as pd
import pytest

from data.storage import DataStorage


class TestRawDualWrite:
    def test_save_stock_daily_writes_to_raw(self, temp_storage: DataStorage):
        df = pd.DataFrame({
            "date": ["2026-07-01"],
            "open": [10.0], "high": [11.0], "low": [9.5], "close": [10.5],
            "volume": [10000], "amount": [105000.0], "pct_change": [0.05],
            "turnover": [0.01],
        })
        temp_storage.save_stock_daily("RAW_TEST", df)
        result = temp_storage.load_raw_stock_daily("RAW_TEST")
        assert len(result) == 1
        assert result.iloc[0]["ticker"] == "RAW_TEST"

    def test_save_index_daily_writes_to_raw(self, temp_storage: DataStorage):
        df = pd.DataFrame({
            "date": ["2026-07-01"],
            "open": [4000.0], "high": [4050.0], "low": [3980.0],
            "close": [4030.0], "volume": [500_000_000],
        })
        temp_storage.save_index_daily("TEST_IDX", df)
        result = temp_storage.conn.execute(
            "SELECT * FROM raw.index_daily WHERE index_code = 'TEST_IDX'"
        ).fetchdf()
        assert len(result) == 1

    def test_raw_data_has_ingested_at(self, temp_storage: DataStorage):
        df = pd.DataFrame({
            "date": ["2026-07-01"],
            "open": [10.0], "high": [11.0], "low": [9.5], "close": [10.5],
            "volume": [10000], "amount": [105000.0], "pct_change": [0.05],
            "turnover": [0.01],
        })
        temp_storage.save_stock_daily("RAW_TS", df)
        row = temp_storage.conn.execute(
            "SELECT ingested_at FROM raw.stock_daily WHERE ticker = 'RAW_TS'"
        ).fetchone()
        assert row is not None
        assert row[0] is not None  # ingested_at timestamp populated


class TestResearchDualWrite:
    def test_save_factors_writes_to_research(self, temp_storage: DataStorage):
        series = pd.Series(
            [0.05, 0.03, 0.04],
            index=pd.to_datetime(["2026-07-01", "2026-07-02", "2026-07-03"]),
            name="value",
        )
        temp_storage.save_factors("FACTOR_TEST", "mom_20d", series)
        result = temp_storage.load_research_factors(
            ticker="FACTOR_TEST", factor_name="mom_20d"
        )
        assert len(result) == 3
        assert "neutralized_value" in result.columns

    def test_save_decision_writes_to_research(self, temp_storage: DataStorage):
        from datetime import date
        did = temp_storage.save_decision(
            ticker="DEC_TEST", direction="buy", weight=0.5,
            reason="test", signal_type="momentum", strategy="momentum",
            decision_date=date(2026, 7, 1), price=100.0,
        )
        result = temp_storage.load_research_decisions(ticker="DEC_TEST")
        assert len(result) == 1
        assert result.iloc[0]["decision_id"] == did

    def test_save_event_writes_to_research(self, temp_storage: DataStorage):
        from datetime import datetime
        temp_storage.save_event({
            "event_id": "evt_schema_test",
            "timestamp": datetime.now(),
            "source": "test",
            "event_type": "earnings",
            "ticker": "EVT_TEST",
            "company": "Test Corp",
            "detail": "Q2 beat",
            "sentiment": "positive",
            "impact_objects": ["price_target"],
            "time_window": "1d",
            "confidence": 0.8,
            "tradability": "high",
            "tags": ["earnings"],
        })
        row = temp_storage.conn.execute(
            "SELECT * FROM research.events WHERE event_id = 'evt_schema_test'"
        ).fetchone()
        assert row is not None

    def test_save_prediction_writes_to_research(self, temp_storage: DataStorage):
        from datetime import date
        temp_storage.save_prediction({
            "prediction_id": "pred_schema_test",
            "date": date(2026, 7, 1),
            "agent": "test",
            "category": "price",
            "prediction": "up",
            "confidence": 0.6,
            "time_horizon": "1d",
            "verify_date": date(2026, 7, 2),
        })
        row = temp_storage.conn.execute(
            "SELECT * FROM research.predictions WHERE prediction_id = 'pred_schema_test'"
        ).fetchone()
        assert row is not None


class TestPublishedDualWrite:
    def test_save_lesson_writes_to_published(self, temp_storage: DataStorage):
        temp_storage.save_lesson({
            "lesson_id": "lesson_schema_test",
            "date": pd.Timestamp("2026-07-01"),
            "category": "risk",
            "lesson": "check sector exposure",
            "evidence": ["case1"],
            "confidence": 0.9,
            "applicable": "all",
        })
        row = temp_storage.conn.execute(
            "SELECT * FROM published.lessons WHERE lesson_id = 'lesson_schema_test'"
        ).fetchone()
        assert row is not None

    def test_backtest_run_writes_to_published(self, temp_storage: DataStorage):
        result = {
            "strategy": "momentum", "ticker": "BT_TEST",
            "date_start": "2026-01-01", "date_end": "2026-06-30",
            "total_return": 0.15, "sharpe_ratio": 1.2,
            "max_drawdown": -0.05, "win_rate": 0.6,
            "trade_count": 20, "init_cash": 1_000_000,
            "fees": 0.001, "slippage": 0.001,
        }
        run_id = temp_storage.save_backtest_run(result)
        row = temp_storage.conn.execute(
            "SELECT * FROM published.backtest_runs WHERE run_id = ?",
            [run_id],
        ).fetchone()
        assert row is not None


class TestSchemaStats:
    def test_get_schema_stats_returns_all_schemas(self, temp_storage: DataStorage):
        stats = temp_storage.get_schema_stats()
        assert "raw" in stats
        assert "research" in stats
        assert "published" in stats
        assert "cleaned" in stats

    def test_schema_stats_counts_rows(self, temp_storage: DataStorage):
        df = pd.DataFrame({
            "date": ["2026-07-01"],
            "open": [1.0], "high": [2.0], "low": [0.5], "close": [1.5],
            "volume": [1000], "amount": [1500.0], "pct_change": [0.01],
            "turnover": [0.001],
        })
        temp_storage.save_stock_daily("STAT_TEST", df)
        stats = temp_storage.get_schema_stats()
        assert stats["raw"]["stock_daily"] >= 1

    def test_empty_db_has_zero_counts(self, temp_storage: DataStorage):
        stats = temp_storage.get_schema_stats()
        for schema, tables in stats.items():
            if tables:
                for count in tables.values():
                    assert count == 0
