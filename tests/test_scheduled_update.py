"""Tests for B1.1: Scheduled update wrapper script.

Covers:
  - run_scheduled_update trading day check (skip on non-trading day)
  - --force flag (run regardless of trading day)
  - --dry-run flag (preview without execution)
  - failure notification (AlertManager called on error)
"""
from __future__ import annotations

from datetime import date
from unittest.mock import patch, MagicMock

import pytest


class TestRunScheduledUpdate:
    def test_non_trading_day_skips(self):
        """Non-trading day should return 0 without calling update_market_data."""
        from scripts.run_scheduled_update import run_scheduled_update

        mock_cal = MagicMock()
        mock_cal.is_trading_day.return_value = False

        with patch("scripts.run_scheduled_update.TradingCalendar",
                   return_value=mock_cal), \
             patch("scripts.run_scheduled_update.update_market_data") as mock_update:
            exit_code = run_scheduled_update()

        assert exit_code == 0
        mock_update.assert_not_called()
        mock_cal.close.assert_called_once()

    def test_trading_day_runs_update(self):
        """Trading day should call update_market_data."""
        from scripts.run_scheduled_update import run_scheduled_update

        mock_cal = MagicMock()
        mock_cal.is_trading_day.return_value = True
        mock_result = {"tickers_updated": 5, "rows_added": 30, "skipped": [], "index_updated": True}

        with patch("scripts.run_scheduled_update.TradingCalendar",
                   return_value=mock_cal), \
             patch("scripts.run_scheduled_update.update_market_data",
                   return_value=mock_result), \
             patch("scripts.run_scheduled_update._notify_success"):
            exit_code = run_scheduled_update()

        assert exit_code == 0

    def test_force_runs_on_non_trading_day(self):
        """--force should run even on non-trading day."""
        from scripts.run_scheduled_update import run_scheduled_update

        mock_cal = MagicMock()
        mock_cal.is_trading_day.return_value = False
        mock_result = {"tickers_updated": 3, "rows_added": 15, "skipped": [], "index_updated": True}

        with patch("scripts.run_scheduled_update.TradingCalendar",
                   return_value=mock_cal), \
             patch("scripts.run_scheduled_update.update_market_data",
                   return_value=mock_result), \
             patch("scripts.run_scheduled_update._notify_success"):
            exit_code = run_scheduled_update(force=True)

        assert exit_code == 0

    def test_dry_run_skips_execution(self):
        """--dry-run should not call update_market_data."""
        from scripts.run_scheduled_update import run_scheduled_update

        mock_cal = MagicMock()
        mock_cal.is_trading_day.return_value = True

        with patch("scripts.run_scheduled_update.TradingCalendar",
                   return_value=mock_cal), \
             patch("scripts.run_scheduled_update.update_market_data") as mock_update:
            exit_code = run_scheduled_update(dry_run=True)

        assert exit_code == 0
        mock_update.assert_not_called()

    def test_failure_triggers_notification(self):
        """On failure, _notify_failure should be called and return 1."""
        from scripts.run_scheduled_update import run_scheduled_update

        mock_cal = MagicMock()
        mock_cal.is_trading_day.return_value = True

        with patch("scripts.run_scheduled_update.TradingCalendar",
                   return_value=mock_cal), \
             patch("scripts.run_scheduled_update.update_market_data",
                   side_effect=Exception("network error")), \
             patch("scripts.run_scheduled_update._notify_failure") as mock_notify:
            exit_code = run_scheduled_update()

        assert exit_code == 1
        mock_notify.assert_called_once()

    def test_calendar_failure_falls_through(self):
        """If TradingCalendar fails, update should still proceed (treat as trading day)."""
        from scripts.run_scheduled_update import run_scheduled_update

        mock_result = {"tickers_updated": 2, "rows_added": 10, "skipped": [], "index_updated": False}

        with patch("scripts.run_scheduled_update.TradingCalendar",
                   side_effect=Exception("DB locked")), \
             patch("scripts.run_scheduled_update.update_market_data",
                   return_value=mock_result), \
             patch("scripts.run_scheduled_update._notify_success"):
            exit_code = run_scheduled_update()

        assert exit_code == 0
