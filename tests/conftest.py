"""Shared fixtures and data generators for all tests."""
from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


# ============================================================
# Synthetic data generators
# ============================================================

def make_uptrend_data(n=260, start_price=100.0) -> pd.DataFrame:
    """Steady uptrend: ~0.05% per day with small noise."""
    dates = pd.date_range("2026-01-01", periods=n, freq="D")
    prices = start_price * np.cumprod(1 + np.full(n, 0.0005))
    prices += np.random.randn(n) * 0.1
    return pd.DataFrame({
        "open": prices * 0.999,
        "high": prices * 1.005,
        "low": prices * 0.995,
        "close": prices,
        "volume": np.full(n, 2_000_000),
    }, index=dates)


def make_rangebound_data(n=260, center=100.0, amp=5.0) -> pd.DataFrame:
    """Oscillating market: prices cycle around center."""
    dates = pd.date_range("2026-01-01", periods=n, freq="D")
    t = np.arange(n)
    prices = center + amp * np.sin(t * 2 * np.pi / 60)
    prices += np.random.randn(n) * 0.2
    return pd.DataFrame({
        "open": prices * 0.999,
        "high": prices * 1.01,
        "low": prices * 0.99,
        "close": prices,
        "volume": np.full(n, 2_000_000),
    }, index=dates)


def make_downtrend_data(n=260, start_price=100.0) -> pd.DataFrame:
    """Steady downtrend: ~-0.05% per day."""
    dates = pd.date_range("2026-01-01", periods=n, freq="D")
    prices = start_price * np.cumprod(1 - np.full(n, 0.0005))
    prices += np.random.randn(n) * 0.1
    return pd.DataFrame({
        "open": prices * 0.999,
        "high": prices * 1.005,
        "low": prices * 0.995,
        "close": prices,
        "volume": np.full(n, 2_000_000),
    }, index=dates)


def make_day_data(close=100.0) -> pd.DataFrame:
    """Single day of OHLCV data."""
    return pd.DataFrame({
        "open": [close * 0.999],
        "high": [close * 1.005],
        "low": [close * 0.995],
        "close": [close],
        "volume": [2_000_000],
    })


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def temp_kb():
    """KnowledgeBase with temp directory — auto-cleaned."""
    from knowledge.knowledge_base import KnowledgeBase
    with tempfile.TemporaryDirectory() as tmp:
        kb = KnowledgeBase(base_dir=str(tmp))
        yield kb


@pytest.fixture
def temp_storage():
    """DataStorage with temp DuckDB — auto-cleaned."""
    from data.storage import DataStorage
    with tempfile.TemporaryDirectory() as tmp:
        db_path = str(Path(tmp) / "test.duckdb")
        ds = DataStorage(db_path=db_path)
        yield ds
        ds.close()


@pytest.fixture
def uptrend_df():
    """252 days of uptrend OHLCV data."""
    return make_uptrend_data()


@pytest.fixture
def rangebound_df():
    """260 days of oscillating OHLCV data."""
    return make_rangebound_data()
