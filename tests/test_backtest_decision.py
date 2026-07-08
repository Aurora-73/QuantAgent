"""Tests for B2.1: Backtest -> decision_memory auto-write.

Covers:
  - _record_backtest_decision writes a record with correct fields
  - record_decision failure does not raise (does not affect backtest persistence)
  - Handles missing/None fields gracefully
  - Integration: run_backtest writes both backtest_run and decision_memory
  - Integration: save_backtest_run completes even when record_decision fails
"""
from __future__ import annotations

from datetime import date
from unittest.mock import patch, MagicMock

import numpy as np
import pandas as pd
import pytest

from data.storage import DataStorage
from scripts.backtest import _record_backtest_decision, run_backtest


# ============================================================
# Helper unit tests
# ============================================================

class TestRecordBacktestDecision:
    def test_writes_decision_with_correct_fields(self, temp_storage: DataStorage):
        """Helper writes a decision_memory record with signal_type='backtest'."""
        result = {
            "annual_return": 0.15,
            "sharpe_ratio": 1.2,
            "total_return": 0.30,
            "max_drawdown": -0.10,
        }
        _record_backtest_decision(temp_storage, result, "momentum", "600519")

        df = temp_storage.load_decisions(signal_type="backtest")
        assert len(df) == 1
        row = df.iloc[0]
        assert row["ticker"] == "600519"
        assert row["direction"] == "backtest"
        assert row["signal_type"] == "backtest"
        assert row["strategy"] == "momentum"
        assert float(row["weight"]) == 0.15
        assert "年化 15.00%" in row["reason"]
        assert "夏普 1.20" in row["reason"]

    def test_failure_does_not_raise(self, temp_storage: DataStorage):
        """If record_decision raises, helper logs warning but does not raise."""
        result = {"annual_return": 0.1, "sharpe_ratio": 0.5}
        with patch("scripts.backtest.DecisionMemory") as mock_dm_cls:
            mock_dm = MagicMock()
            mock_dm.record_decision.side_effect = RuntimeError("DB locked")
            mock_dm_cls.return_value = mock_dm

            # Should NOT raise
            _record_backtest_decision(temp_storage, result, "momentum", "600519")

        # No decision written
        df = temp_storage.load_decisions(signal_type="backtest")
        assert len(df) == 0

    def test_handles_missing_fields(self, temp_storage: DataStorage):
        """Result dict with missing keys defaults to 0, does not crash."""
        result = {}  # no annual_return, no sharpe_ratio
        _record_backtest_decision(temp_storage, result, "test_strat", "000001")

        df = temp_storage.load_decisions(signal_type="backtest")
        assert len(df) == 1
        row = df.iloc[0]
        assert float(row["weight"]) == 0.0
        assert "年化 0.00%" in row["reason"]

    def test_handles_none_values(self, temp_storage: DataStorage):
        """Result dict with None values does not crash."""
        result = {"annual_return": None, "sharpe_ratio": None}
        _record_backtest_decision(temp_storage, result, "test_strat", "000001")

        df = temp_storage.load_decisions(signal_type="backtest")
        assert len(df) == 1

    def test_decision_date_is_today(self, temp_storage: DataStorage):
        """Decision record uses today's date."""
        result = {"annual_return": 0.05, "sharpe_ratio": 0.8}
        _record_backtest_decision(temp_storage, result, "momentum", "600519")

        df = temp_storage.load_decisions(signal_type="backtest")
        row = df.iloc[0]
        dec_date = row["decision_date"]
        # DuckDB may return pd.Timestamp or date; normalize to date
        if hasattr(dec_date, "date"):
            dec_date = dec_date.date()
        elif isinstance(dec_date, str):
            dec_date = date.fromisoformat(dec_date[:10])
        assert dec_date == date.today()


# ============================================================
# Integration: run_backtest writes decision_memory
# ============================================================

def _seed_stock_data(storage: DataStorage, ticker: str, n: int = 100):
    """Seed temp_storage with OHLCV data for integration tests."""
    dates = pd.date_range("2025-01-01", periods=n, freq="D")
    prices = 100.0 + np.cumsum(np.random.randn(n) * 0.5)
    df = pd.DataFrame({
        "date": [d.date() for d in dates],
        "open": prices * 0.999,
        "high": prices * 1.01,
        "low": prices * 0.99,
        "close": prices,
        "volume": np.full(n, 2_000_000),
        "amount": prices * 2_000_000,
        "pct_change": pd.Series(prices).pct_change().fillna(0),
        "turnover": np.full(n, 0.01),
    })
    storage.save_stock_daily(ticker, df)


class TestRunBacktestIntegration:
    def test_run_backtest_writes_decision(self, temp_storage: DataStorage):
        """run_backtest writes both backtest_run and decision_memory."""
        _seed_stock_data(temp_storage, "600519", n=100)

        fake_result = {
            "total_return": 0.20,
            "annual_return": 0.12,
            "sharpe_ratio": 1.0,
            "max_drawdown": -0.08,
            "trade_count": 5,
        }

        with patch("scripts.backtest.DataStorage", return_value=temp_storage), \
             patch("scripts.backtest.BacktestEngine.signal_backtest",
                   return_value=fake_result), \
             patch("scripts.backtest.settings") as mock_settings:
            mock_settings.momentum_entry_threshold = 0.05
            mock_settings.momentum_exit_threshold = -0.02
            mock_settings.momentum_rsi_overbought = 70
            mock_settings.backtest_init_cash = 100000
            mock_settings.backtest_fees = 0.001
            mock_settings.backtest_slippage = 0.001

            run_backtest("momentum", "600519", "2025-01-01", "2025-04-01")

        # backtest_run persisted
        runs = temp_storage.load_backtest_runs()
        assert len(runs) >= 1

        # decision_memory persisted
        decisions = temp_storage.load_decisions(signal_type="backtest")
        assert len(decisions) >= 1
        row = decisions.iloc[0]
        assert row["ticker"] == "600519"
        assert row["signal_type"] == "backtest"

    def test_save_persists_even_if_decision_fails(self, temp_storage: DataStorage):
        """backtest_run is saved even when record_decision raises."""
        _seed_stock_data(temp_storage, "600519", n=100)

        fake_result = {
            "total_return": 0.15,
            "annual_return": 0.10,
            "sharpe_ratio": 0.9,
            "max_drawdown": -0.05,
            "trade_count": 3,
        }

        with patch("scripts.backtest.DataStorage", return_value=temp_storage), \
             patch("scripts.backtest.BacktestEngine.signal_backtest",
                   return_value=fake_result), \
             patch("scripts.backtest.DecisionMemory") as mock_dm_cls, \
             patch("scripts.backtest.settings") as mock_settings:
            mock_settings.momentum_entry_threshold = 0.05
            mock_settings.momentum_exit_threshold = -0.02
            mock_settings.momentum_rsi_overbought = 70
            mock_settings.backtest_init_cash = 100000
            mock_settings.backtest_fees = 0.001
            mock_settings.backtest_slippage = 0.001

            mock_dm = MagicMock()
            mock_dm.record_decision.side_effect = RuntimeError("injected failure")
            mock_dm_cls.return_value = mock_dm

            # Should not raise
            run_backtest("momentum", "600519", "2025-01-01", "2025-04-01")

        # backtest_run WAS persisted despite decision failure
        runs = temp_storage.load_backtest_runs()
        assert len(runs) >= 1

        # decision_memory was NOT written (the failure was caught)
        decisions = temp_storage.load_decisions(signal_type="backtest")
        assert len(decisions) == 0
