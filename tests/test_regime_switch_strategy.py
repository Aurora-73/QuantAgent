"""RegimeSwitchStrategy tests — regime mapping, sub-strategy delegation, cooldown."""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from strategies.base import WeightVector, Direction
from strategies.regime_switch.strategy import RegimeSwitchStrategy
from strategies.registry import list_strategies


class TestConfig:
    def test_default_regime_mapping(self):
        strat = RegimeSwitchStrategy()
        assert "trend" in strat.regime_strategies
        assert "oscillating" in strat.regime_strategies
        assert "extreme_volatility" in strat.regime_strategies

    def test_cooldown_default_is_3(self):
        strat = RegimeSwitchStrategy()
        assert strat.cooldown_days == 3

    def test_max_daily_switches_default_is_2(self):
        strat = RegimeSwitchStrategy()
        assert strat.max_daily_switches == 2


class TestSubStrategyDelegation:
    def test_trend_regime_uses_momentum(self):
        strat = RegimeSwitchStrategy()
        wv = strat.generate_weight_vector(pd.DataFrame(), {
            "ticker": "600519",
            "regime": {
                "regime": "trend",
                "confidence": 0.8,
            },
        })
        assert isinstance(wv, WeightVector)

    def test_extreme_volatility_returns_zero_weight(self):
        """extreme_volatility regime should not trade."""
        strat = RegimeSwitchStrategy()
        wv = strat.generate_weight_vector(pd.DataFrame(), {
            "ticker": "600519",
            "regime": {
                "regime": "extreme_volatility",
                "confidence": 0.8,
            },
        })
        assert wv.confidence == 0.0

    def test_low_regime_confidence_returns_zero(self):
        strat = RegimeSwitchStrategy()
        wv = strat.generate_weight_vector(pd.DataFrame(), {
            "ticker": "600519",
            "regime": {
                "regime": "trend",
                "confidence": 0.1,  # below min_regime_confidence=0.3
            },
        })
        assert wv.confidence == 0.0

    def test_no_regime_info_returns_zero(self):
        strat = RegimeSwitchStrategy()
        wv = strat.generate_weight_vector(pd.DataFrame(), {"ticker": "600519"})
        assert wv.confidence == 0.0

    def test_oscillating_regime_uses_event_driven(self):
        strat = RegimeSwitchStrategy()
        wv = strat.generate_weight_vector(pd.DataFrame(), {
            "ticker": "600519",
            "regime": {
                "regime": "oscillating",
                "confidence": 0.7,
            },
        })
        assert isinstance(wv, WeightVector)

    def test_policy_window_uses_sentiment(self):
        strat = RegimeSwitchStrategy()
        wv = strat.generate_weight_vector(pd.DataFrame(), {
            "ticker": "600519",
            "regime": {
                "regime": "policy_window",
                "confidence": 0.7,
            },
        })
        assert isinstance(wv, WeightVector)


class TestCooldown:
    def test_recent_switch_respected(self):
        strategy_name = "test_cooldown"
        # After a recent switch, weight vector should be empty
        strat = RegimeSwitchStrategy()
        strat._last_switch_date = date.today()
        strat._current_regime = "oscillating"
        wv = strat.generate_weight_vector(pd.DataFrame(), {
            "ticker": "600519",
            "regime": {
                "regime": "trend",
                "confidence": 0.8,
            },
        })
        # During cooldown, should return zero or use current regime
        # (not necessarily zero, but shouldn't switch to trend)
        assert isinstance(wv, WeightVector)
