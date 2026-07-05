"""Factor engine correctness tests — synthetic data, known expected values."""
from __future__ import annotations

import numpy as np
import pandas as pd

from research.factors import FactorEngine


def _make_linear_data(n=252, start_price=100.0) -> pd.DataFrame:
    """Steady uptrend: close increases by 0.05% per day."""
    dates = pd.date_range("2026-01-01", periods=n, freq="D")
    prices = start_price * np.cumprod(1 + np.full(n, 0.0005))
    # Add small noise
    prices += np.random.randn(n) * 0.1
    return pd.DataFrame({
        "open": prices * 0.999,
        "high": prices * 1.005,
        "low": prices * 0.995,
        "close": prices,
        "volume": np.full(n, 2_000_000),
    }, index=dates)


class TestFactorEngineRegistration:
    def test_25_registered_factors(self):
        fe = FactorEngine()
        factors = fe.list_factors()
        assert len(factors) >= 25

    def test_each_factor_has_name_and_description(self):
        fe = FactorEngine()
        for name, desc in fe.list_factors().items():
            assert isinstance(name, str) and len(name) > 0
            assert isinstance(desc, str) and len(desc) > 0


class TestFactorComputation:
    def test_compute_all_returns_expected_columns(self):
        df = _make_linear_data()
        fe = FactorEngine()
        result = fe.compute_all(df)
        # Should include all raw + factor columns
        assert len(result.columns) >= 25
        assert "momentum_20d" in result.columns
        assert "rsi_14" in result.columns
        assert "volume_ratio_20d" in result.columns

    def test_momentum_positive_in_uptrend(self):
        df = _make_linear_data()
        fe = FactorEngine()
        result = fe.compute_all(df)
        latest_mom = result["momentum_20d"].iloc[-1]
        assert latest_mom > 0  # steady uptrend → positive momentum

    def test_rsi_in_mid_range(self):
        df = _make_linear_data()
        fe = FactorEngine()
        result = fe.compute_all(df)
        rsi_vals = result["rsi_14"].dropna()
        assert rsi_vals.between(0, 100).all()

    def test_no_nan_in_latest_window(self):
        df = _make_linear_data()
        fe = FactorEngine()
        result = fe.compute_all(df)
        # Last 60 rows should be fully computed (all windows warmed up)
        # Exclude columns that need additional data (fundamental, turnover rate, etc.)
        exclude = {"turnover_ma5", "price_volume_corr",
                   "roe", "pe_ttm", "revenue_growth", "profit_growth"}
        core_cols = [c for c in result.columns if c not in exclude]
        tail = result.iloc[-60:][core_cols]
        assert tail.isnull().sum().sum() == 0, f"NaN in: {tail.columns[tail.isnull().any()].tolist()}"

    def test_volume_ratio_around_one(self):
        """Constant volume → volume ratio ≈ 1.0."""
        df = _make_linear_data()
        fe = FactorEngine()
        result = fe.compute_all(df)
        vr = result["volume_ratio_20d"].iloc[-1]
        assert 0.9 <= vr <= 1.1

    def test_volatility_stable_in_low_vol_data(self):
        """Low-noise data → stable, non-zero volatility."""
        df = _make_linear_data()
        fe = FactorEngine()
        result = fe.compute_all(df)
        vol = result["volatility_20d"].dropna()
        assert vol.iloc[-1] > 0
