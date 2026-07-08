"""Tests for P0.1: independent incremental data update task.

Covers:
  - DataStorage.get_last_date (empty table, with data, ticker filter)
  - DataStorage.append_stock_daily / append_index_daily (append without delete)
  - update_market_data with mocked DataProvider (incremental skip, fetch missing)
"""
from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import patch

import pandas as pd
import pytest

from data.storage import DataStorage


# ============================================================
# get_last_date
# ============================================================

class TestGetLastDate:
    def test_empty_table_returns_none(self, temp_storage: DataStorage):
        assert temp_storage.get_last_date("stock_daily") is None

    def test_stock_daily_returns_latest(self, temp_storage: DataStorage):
        df = pd.DataFrame({
            "date": ["2026-07-01", "2026-07-02", "2026-07-03"],
            "open": [10.0, 10.5, 11.0], "high": [11.0, 11.5, 12.0],
            "low": [9.5, 10.0, 10.5], "close": [10.5, 11.0, 11.5],
            "volume": [10000, 11000, 12000], "amount": [1e5, 1.1e5, 1.2e5],
            "pct_change": [0.05, 0.05, 0.05], "turnover": [0.01, 0.01, 0.01],
        })
        temp_storage.save_stock_daily("TEST001", df)
        result = temp_storage.get_last_date("stock_daily")
        assert result == date(2026, 7, 3)

    def test_ticker_filter(self, temp_storage: DataStorage):
        df_a = pd.DataFrame({
            "date": ["2026-07-01", "2026-07-05"],
            "open": [10.0, 10.5], "high": [11.0, 11.5],
            "low": [9.5, 10.0], "close": [10.5, 11.0],
            "volume": [10000, 11000], "amount": [1e5, 1.1e5],
            "pct_change": [0.05, 0.05], "turnover": [0.01, 0.01],
        })
        df_b = pd.DataFrame({
            "date": ["2026-07-10"],
            "open": [20.0], "high": [21.0], "low": [19.0],
            "close": [20.5], "volume": [20000], "amount": [2e5],
            "pct_change": [0.05], "turnover": [0.01],
        })
        temp_storage.save_stock_daily("AAA", df_a)
        temp_storage.save_stock_daily("BBB", df_b)

        assert temp_storage.get_last_date("stock_daily", ticker="AAA") == date(2026, 7, 5)
        assert temp_storage.get_last_date("stock_daily", ticker="BBB") == date(2026, 7, 10)
        assert temp_storage.get_last_date("stock_daily") == date(2026, 7, 10)

    def test_index_daily(self, temp_storage: DataStorage):
        df = pd.DataFrame({
            "date": ["2026-07-01", "2026-07-02"],
            "open": [4000.0, 4010.0], "high": [4050.0, 4060.0],
            "low": [3980.0, 3990.0], "close": [4030.0, 4040.0],
            "volume": [5e8, 5.1e8],
        })
        temp_storage.save_index_daily("000300", df)
        assert temp_storage.get_last_date("index_daily", ticker="000300") == date(2026, 7, 2)

    def test_unsupported_table_raises(self, temp_storage: DataStorage):
        with pytest.raises(ValueError, match="不支持的表"):
            temp_storage.get_last_date("nonexistent_table")


# ============================================================
# append_stock_daily
# ============================================================

class TestAppendStockDaily:
    def test_append_preserves_existing(self, temp_storage: DataStorage):
        old_df = pd.DataFrame({
            "date": ["2026-07-01"],
            "open": [10.0], "high": [11.0], "low": [9.5], "close": [10.5],
            "volume": [10000], "amount": [1e5], "pct_change": [0.05],
            "turnover": [0.01],
        })
        temp_storage.save_stock_daily("APP001", old_df)

        new_df = pd.DataFrame({
            "date": ["2026-07-02"],
            "open": [10.5], "high": [11.5], "low": [10.0], "close": [11.0],
            "volume": [11000], "amount": [1.1e5], "pct_change": [0.05],
            "turnover": [0.01],
        })
        temp_storage.append_stock_daily("APP001", new_df)

        loaded = temp_storage.load_stock_daily("APP001")
        assert len(loaded) == 2
        assert loaded.index[0] == pd.Timestamp("2026-07-01")
        assert loaded.index[1] == pd.Timestamp("2026-07-02")

    def test_append_empty_df_noop(self, temp_storage: DataStorage):
        temp_storage.append_stock_daily("EMPTY", pd.DataFrame())
        assert temp_storage.get_last_date("stock_daily", ticker="EMPTY") is None

    def test_append_writes_to_raw_schema(self, temp_storage: DataStorage):
        df = pd.DataFrame({
            "date": ["2026-07-01"],
            "open": [10.0], "high": [11.0], "low": [9.5], "close": [10.5],
            "volume": [10000], "amount": [1e5], "pct_change": [0.05],
            "turnover": [0.01],
        })
        temp_storage.append_stock_daily("RAW_APP", df)
        result = temp_storage.conn.execute(
            "SELECT * FROM raw.stock_daily WHERE ticker = 'RAW_APP'"
        ).fetchdf()
        assert len(result) == 1


# ============================================================
# append_index_daily
# ============================================================

class TestAppendIndexDaily:
    def test_append_preserves_existing(self, temp_storage: DataStorage):
        old_df = pd.DataFrame({
            "date": ["2026-07-01"],
            "open": [4000.0], "high": [4050.0], "low": [3980.0],
            "close": [4030.0], "volume": [5e8],
        })
        temp_storage.save_index_daily("000300", old_df)

        new_df = pd.DataFrame({
            "date": ["2026-07-02"],
            "open": [4030.0], "high": [4060.0], "low": [4010.0],
            "close": [4040.0], "volume": [5.1e8],
        })
        temp_storage.append_index_daily("000300", new_df)

        loaded = temp_storage.load_index_daily("000300")
        assert len(loaded) == 2


# ============================================================
# update_market_data (with mocked DataProvider)
# ============================================================

def _make_stock_df(start: str, end: str) -> pd.DataFrame:
    dates = pd.date_range(start, end, freq="D")
    n = len(dates)
    df = pd.DataFrame({
        "open": range(n), "high": range(1, n + 1), "low": range(n),
        "close": range(1, n + 1), "volume": [10000] * n,
        "amount": [1e5] * n, "pct_change": [0.01] * n, "turnover": [0.01] * n,
    }, index=dates)
    df.index.name = "date"
    return df


class TestUpdateMarketData:
    def test_incremental_skips_up_to_date(self, temp_storage: DataStorage):
        """If storage already has data up to target_date, skip fetching."""
        from scripts.update_data import update_market_data

        today = date(2026, 7, 3)
        existing = pd.DataFrame({
            "date": ["2026-07-03"],
            "open": [10.0], "high": [11.0], "low": [9.5], "close": [10.5],
            "volume": [10000], "amount": [1e5], "pct_change": [0.05],
            "turnover": [0.01],
        })
        temp_storage.save_stock_daily("600519", existing)
        temp_storage.save_index_daily("000300", pd.DataFrame({
            "date": ["2026-07-03"], "open": [4000.0], "high": [4050.0],
            "low": [3980.0], "close": [4030.0], "volume": [5e8],
        }))

        with patch("scripts.update_data.DataProvider") as mock_dp, \
             patch("scripts.update_data.DataStorage", return_value=temp_storage):
            mock_dp.get_csi300_components.return_value = ["600519"]
            mock_dp.get_stock_daily.return_value = pd.DataFrame()
            mock_dp.get_index_daily.return_value = pd.DataFrame()

            result = update_market_data(
                target_date=today, tickers=["600519"], incremental=True
            )

        assert result["tickers_updated"] == 0
        assert "600519" in result["skipped"]
        mock_dp.get_stock_daily.assert_not_called()

    def test_incremental_fetches_missing(self, temp_storage: DataStorage):
        """If storage lags behind, fetch from last_date+1 to target."""
        from scripts.update_data import update_market_data

        today = date(2026, 7, 5)
        existing = pd.DataFrame({
            "date": ["2026-07-01"],
            "open": [10.0], "high": [11.0], "low": [9.5], "close": [10.5],
            "volume": [10000], "amount": [1e5], "pct_change": [0.05],
            "turnover": [0.01],
        })
        temp_storage.save_stock_daily("600519", existing)
        temp_storage.save_index_daily("000300", pd.DataFrame({
            "date": ["2026-07-05"], "open": [4000.0], "high": [4050.0],
            "low": [3980.0], "close": [4030.0], "volume": [5e8],
        }))

        new_data = _make_stock_df("2026-07-02", "2026-07-05")

        with patch("scripts.update_data.DataProvider") as mock_dp, \
             patch("scripts.update_data.DataStorage", return_value=temp_storage), \
             patch("scripts.update_data.DataCleaner") as mock_cleaner:
            mock_dp.get_csi300_components.return_value = ["600519"]
            mock_dp.get_stock_daily.return_value = new_data
            mock_cleaner.clean_ohlcv.side_effect = lambda x: x

            result = update_market_data(
                target_date=today, tickers=["600519"], incremental=True
            )

        assert result["tickers_updated"] == 1
        assert result["rows_added"] == 4
        mock_dp.get_stock_daily.assert_called_once_with(
            "600519", "2026-07-02", "2026-07-05"
        )

    def test_incremental_no_existing_data_full_fetch(self, temp_storage: DataStorage):
        """If no existing data, fetch from 2020-01-01 (full history)."""
        from scripts.update_data import update_market_data

        today = date(2026, 7, 3)
        new_data = _make_stock_df("2026-07-01", "2026-07-03")

        with patch("scripts.update_data.DataProvider") as mock_dp, \
             patch("scripts.update_data.DataStorage", return_value=temp_storage), \
             patch("scripts.update_data.DataCleaner") as mock_cleaner:
            mock_dp.get_csi300_components.return_value = ["000001"]
            mock_dp.get_stock_daily.return_value = new_data
            mock_dp.get_index_daily.return_value = pd.DataFrame()
            mock_cleaner.clean_ohlcv.side_effect = lambda x: x

            result = update_market_data(
                target_date=today, tickers=["000001"], incremental=True
            )

        assert result["tickers_updated"] == 1
        mock_dp.get_stock_daily.assert_called_once_with(
            "000001", "2020-01-01", "2026-07-03"
        )

    def test_non_incremental_uses_save(self, temp_storage: DataStorage):
        """Non-incremental mode uses save_stock_daily (delete + insert)."""
        from scripts.update_data import update_market_data

        today = date(2026, 7, 3)
        existing = pd.DataFrame({
            "date": ["2026-07-01"],
            "open": [10.0], "high": [11.0], "low": [9.5], "close": [10.5],
            "volume": [10000], "amount": [1e5], "pct_change": [0.05],
            "turnover": [0.01],
        })
        temp_storage.save_stock_daily("600519", existing)

        new_data = _make_stock_df("2026-07-01", "2026-07-03")

        with patch("scripts.update_data.DataProvider") as mock_dp, \
             patch("scripts.update_data.DataStorage", return_value=temp_storage), \
             patch("scripts.update_data.DataCleaner") as mock_cleaner:
            mock_dp.get_csi300_components.return_value = ["600519"]
            mock_dp.get_stock_daily.return_value = new_data
            mock_dp.get_index_daily.return_value = pd.DataFrame()
            mock_cleaner.clean_ohlcv.side_effect = lambda x: x

            result = update_market_data(
                target_date=today, tickers=["600519"], incremental=False
            )

        assert result["tickers_updated"] == 1
        loaded = temp_storage.load_stock_daily("600519")
        assert len(loaded) == 3
