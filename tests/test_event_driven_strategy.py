"""EventDrivenStrategy tests — event-to-signal mapping, decay, stacking."""
from __future__ import annotations

import pandas as pd
import pytest

from strategies.base import WeightVector, Direction
from strategies.event_driven.strategy import EventDrivenStrategy


class TestEventSignalMapping:
    def test_earnings_surprise_produces_buy(self):
        strat = EventDrivenStrategy()
        signals = strat.generate_signal(pd.DataFrame(), {
            "ticker": "600519",
            "events": [
                {"event_type": "earnings_surprise", "confidence": 0.9,
                 "date": "2026-07-01", "ticker": "600519"},
            ],
        })
        assert len(signals) >= 1
        for s in signals:
            assert s.direction == Direction.LONG
            assert 0 < s.score <= 1.0

    def test_earnings_miss_produces_sell(self):
        strat = EventDrivenStrategy()
        signals = strat.generate_signal(pd.DataFrame(), {
            "ticker": "600519",
            "events": [
                {"event_type": "earnings_miss", "confidence": 0.9,
                 "date": "2026-07-01", "ticker": "600519"},
            ],
        })
        assert len(signals) >= 1
        for s in signals:
            assert s.direction == Direction.SHORT

    def test_empty_events_returns_empty_signals(self):
        strat = EventDrivenStrategy()
        signals = strat.generate_signal(pd.DataFrame(), {
            "ticker": "600519",
            "events": [],
        })
        assert signals == []

    def test_no_events_key_returns_empty(self):
        strat = EventDrivenStrategy()
        signals = strat.generate_signal(pd.DataFrame(), {"ticker": "600519"})
        assert signals == []

    def test_low_confidence_event_is_filtered(self):
        """Events below min_confidence (default 0.3) should be ignored."""
        strat = EventDrivenStrategy()
        signals = strat.generate_signal(pd.DataFrame(), {
            "ticker": "600519",
            "events": [
                {"event_type": "earnings_surprise", "confidence": 0.1,
                 "date": "2026-07-01", "ticker": "600519"},
            ],
        })
        assert signals == []


class TestWeightVector:
    def test_weight_vector_from_events(self):
        strat = EventDrivenStrategy()
        wv = strat.generate_weight_vector(pd.DataFrame(), {
            "ticker": "600519",
            "events": [
                {"event_type": "earnings_surprise", "confidence": 0.8,
                 "date": "2026-07-01", "ticker": "600519"},
            ],
        })
        assert isinstance(wv, WeightVector)
        assert "600519" in wv.weights
        assert 0 < wv.confidence <= 1.0
        assert wv.source == "event_driven"

    def test_weight_vector_empty_events_zero_confidence(self):
        strat = EventDrivenStrategy()
        wv = strat.generate_weight_vector(pd.DataFrame(), {
            "ticker": "600519",
            "events": [],
        })
        assert wv.confidence == 0.0

    def test_multiple_events_averaged(self):
        strat = EventDrivenStrategy()
        wv = strat.generate_weight_vector(pd.DataFrame(), {
            "ticker": "600519",
            "events": [
                {"event_type": "earnings_surprise", "confidence": 0.9,
                 "date": "2026-07-01", "ticker": "600519"},
                {"event_type": "analyst_upgrade", "confidence": 0.7,
                 "date": "2026-07-01", "ticker": "600519"},
            ],
        })
        assert "600519" in wv.weights


class TestDecay:
    def test_old_event_has_less_impact(self):
        """Event from 2 days ago should have less impact than today's.
        Both must be within event_window_days (default 3)."""
        import datetime
        strat = EventDrivenStrategy()
        today = datetime.date.today()
        wv_recent = strat.generate_weight_vector(pd.DataFrame(), {
            "ticker": "600519",
            "events": [
                {"event_type": "earnings_surprise", "confidence": 1.0,
                 "date": today.isoformat(), "ticker": "600519"},
            ],
        })
        wv_older = strat.generate_weight_vector(pd.DataFrame(), {
            "ticker": "600519",
            "events": [
                {"event_type": "earnings_surprise", "confidence": 1.0,
                 "date": (today - datetime.timedelta(days=2)).isoformat(),
                 "ticker": "600519"},
            ],
        })
        assert abs(wv_older.weights["600519"]) <= abs(wv_recent.weights["600519"])


class TestHoldingPeriod:
    def test_returns_dict(self):
        strat = EventDrivenStrategy()
        hp = strat.expected_holding_period()
        assert "min_days" in hp
        assert "max_days" in hp


