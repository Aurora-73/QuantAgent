"""Tests for B1.2: Data freshness MCP tools.

Covers:
  - check_data_freshness (empty DB, with data, error handling)
  - update_data_incremental (dry_run, actual update with mocked function)
"""
from __future__ import annotations

import json
from datetime import date
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

from data.storage import DataStorage


# ============================================================
# check_data_freshness
# ============================================================

class TestCheckDataFreshness:
    def test_empty_db_all_outdated(self, temp_storage: DataStorage):
        """Empty database should report all tables as outdated."""
        with patch("mcp_server.tools_data.DataStorage", return_value=temp_storage):
            from mcp_server.tools_data import check_data_freshness
            result = json.loads(check_data_freshness())

        for table in ["stock_daily", "index_daily", "factors", "events", "financials"]:
            assert result[table]["status"] == "outdated"
            assert result[table]["last_date"] is None
        assert result["overall"] == "outdated"

    def test_fresh_data(self, temp_storage: DataStorage):
        """Database with today's data should report fresh status."""
        today = date.today()
        # Seed trading calendar
        temp_storage.conn.execute("""
            CREATE TABLE IF NOT EXISTS trading_calendar (trade_date DATE PRIMARY KEY)
        """)
        temp_storage.conn.execute(
            "INSERT INTO trading_calendar VALUES (?)", [today]
        )
        # Seed stock data
        df = pd.DataFrame({
            "date": [today.isoformat()],
            "open": [10.0], "high": [11.0], "low": [9.5], "close": [10.5],
            "volume": [10000], "amount": [1e5], "pct_change": [0.05],
            "turnover": [0.01],
        })
        temp_storage.save_stock_daily("TEST", df)

        with patch("mcp_server.tools_data.DataStorage", return_value=temp_storage):
            from mcp_server.tools_data import check_data_freshness
            result = json.loads(check_data_freshness())

        assert result["stock_daily"]["status"] == "fresh"
        assert result["stock_daily"]["last_date"] == str(today)

    def test_returns_json_string(self):
        """Tool must return a JSON string (MCP contract)."""
        with patch("mcp_server.tools_data.DataStorage") as mock_ds:
            mock_instance = MagicMock()
            mock_instance.get_freshness.side_effect = Exception("mock error")
            mock_ds.return_value = mock_instance

            from mcp_server.tools_data import check_data_freshness
            result = check_data_freshness()

        assert isinstance(result, str)
        parsed = json.loads(result)
        assert "overall" in parsed


# ============================================================
# update_data_incremental
# ============================================================

class TestUpdateDataIncremental:
    def test_dry_run_returns_preview(self):
        """dry_run=True should return preview without executing."""
        from mcp_server.tools_data import update_data_incremental
        result = json.loads(update_data_incremental(dry_run=True))

        assert result["success"] is True
        assert result["dry_run"] is True
        assert "incremental" in result["details"]["mode"]

    def test_actual_update_with_mock(self):
        """Non-dry-run should call update_market_data and return results."""
        mock_result = {
            "tickers_updated": 5,
            "rows_added": 30,
            "skipped": ["000001"],
            "index_updated": True,
        }

        with patch("scripts.update_data.update_market_data", return_value=mock_result):
            from mcp_server.tools_data import update_data_incremental
            result = json.loads(update_data_incremental(tickers="600519,000001"))

        assert result["success"] is True
        assert result["tickers_updated"] == 5
        assert result["rows_added"] == 30
        assert result["skipped"] == 1
        assert result["index_updated"] is True

    def test_error_handling(self):
        """Errors should be caught and returned as JSON."""
        with patch("scripts.update_data.update_market_data",
                   side_effect=Exception("network error")):
            from mcp_server.tools_data import update_data_incremental
            result = json.loads(update_data_incremental())

        assert result["success"] is False
        assert "network error" in result["message"]

    def test_returns_json_string(self):
        """Tool must return a JSON string (MCP contract)."""
        from mcp_server.tools_data import update_data_incremental
        result = update_data_incremental(dry_run=True)
        assert isinstance(result, str)
        json.loads(result)  # must be valid JSON
