"""Momentum strategy contract tests — synthetic data, interface verification."""
from __future__ import annotations

import numpy as np
import pandas as pd

from strategies.momentum.strategy import MomentumStrategy
from strategies.base import Direction, SignalStrength, WeightVector


def _make_test_data(n=260) -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=n, freq="D")
    prices = 100 * np.cumprod(1 + np.full(n, 0.0005))
    return pd.DataFrame({
        "open": prices * 0.999,
        "high": prices * 1.005,
        "low": prices * 0.995,
        "close": prices,
        "volume": np.full(n, 2_000_000),
    }, index=dates)


class TestPrepareFeatures:
    def test_uses_factorengine(self):
        strat = MomentumStrategy()
        df = _make_test_data()
        result = strat.prepare_features(df)
        # Should have FactorEngine columns (not hand-rolled ones)
        assert "momentum_20d" in result.columns
        assert "rsi_14" in result.columns
        # Strategy mapping columns
        assert "momentum" in result.columns
        assert "rsi" in result.columns
        assert "volume_ratio" in result.columns
        assert "trend_strength" in result.columns

    def test_no_private_calc_methods(self):
        # Acceptance: _calc_rsi and _calc_atr must be removed
        assert not hasattr(MomentumStrategy, "_calc_rsi")
        assert not hasattr(MomentumStrategy, "_calc_atr")

    def test_trend_strength_in_uptrend(self):
        strat = MomentumStrategy()
        df = _make_test_data()
        result = strat.prepare_features(df)
        ts = result["trend_strength"].iloc[-1]
        assert ts > 0  # uptrend → positive trend strength


class TestGenerateSignal:
    def test_returns_list_of_signals(self):
        strat = MomentumStrategy()
        df = _make_test_data()
        features = strat.prepare_features(df)
        signals = strat.generate_signal(features, {"ticker": "600519"})
        assert isinstance(signals, list)
        for s in signals:
            assert hasattr(s, "direction")
            assert hasattr(s, "score")
            assert -1.0 <= s.score <= 1.0

    def test_empty_features_returns_empty(self):
        strat = MomentumStrategy()
        signals = strat.generate_signal(pd.DataFrame(), {})
        assert signals == []


class TestGenerateWeightVector:
    def test_returns_weight_vector(self):
        strat = MomentumStrategy()
        df = _make_test_data()
        features = strat.prepare_features(df)
        wv = strat.generate_weight_vector(features, {"ticker": "600519"})
        assert isinstance(wv, WeightVector)
        assert isinstance(wv.weights, dict)
        assert 0.0 <= wv.confidence <= 1.0
        assert wv.source == "momentum"

    def test_empty_features_returns_zero_weight(self):
        strat = MomentumStrategy()
        wv = strat.generate_weight_vector(pd.DataFrame(), {})
        assert wv.confidence == 0.0


class TestHoldingPeriod:
    def test_expected_holding_period_has_days(self):
        strat = MomentumStrategy()
        hp = strat.expected_holding_period()
        assert "min_days" in hp
        assert "max_days" in hp
        assert hp["min_days"] <= hp["max_days"]
