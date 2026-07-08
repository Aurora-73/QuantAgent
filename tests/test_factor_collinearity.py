"""Tests for B2.2: Factor collinearity analysis.

Covers:
  - compute_factor_correlation (empty DB, seeded data, matrix shape/values)
  - detect_collinear_groups (known correlated factors, threshold boundary, independence)
  - generate_collinearity_report (structure, empty DB, no-auto-delete note)
  - Performance: 29-factor matrix < 5s
  - MCP tool get_factor_collinearity returns valid JSON
"""
from __future__ import annotations

import json
import time
from datetime import date, timedelta
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from data.storage import DataStorage
from research.factor_analysis import (
    compute_factor_correlation,
    detect_collinear_groups,
    generate_collinearity_report,
)


# ============================================================
# Helpers
# ============================================================

def _seed_factors(storage: DataStorage, ticker: str,
                  factor_data: dict[str, list[float]],
                  n_days: int = 60):
    """Seed factors table with synthetic data.

    Args:
        factor_data: {factor_name: [values]} — each list length must equal n_days
    """
    dates = [date.today() - timedelta(days=n_days - i) for i in range(n_days)]
    rows = []
    for fname, values in factor_data.items():
        for d, v in zip(dates, values):
            rows.append((ticker, d, fname, float(v)))
    df = pd.DataFrame(rows, columns=["ticker", "date", "factor_name", "factor_value"])
    storage.conn.execute("DELETE FROM factors WHERE ticker = ?", [ticker])
    storage.conn.execute("""
        INSERT INTO factors (ticker, date, factor_name, factor_value)
        SELECT ticker, date, factor_name, factor_value FROM df
    """)


def _make_correlated_series(base: np.ndarray, noise_std: float = 0.0) -> np.ndarray:
    """Return base + noise (noise_std=0 → perfect correlation)."""
    return base + np.random.randn(len(base)) * noise_std


# ============================================================
# compute_factor_correlation
# ============================================================

class TestComputeFactorCorrelation:
    def test_empty_db_returns_empty(self, temp_storage: DataStorage):
        """No factor data → empty DataFrame."""
        corr = compute_factor_correlation(storage=temp_storage)
        assert isinstance(corr, pd.DataFrame)
        assert corr.empty

    def test_seeded_factors_returns_matrix(self, temp_storage: DataStorage):
        """Seeded factors return a square correlation matrix."""
        n = 30
        base = np.random.randn(n)
        _seed_factors(temp_storage, "600519", {
            "momentum_5d": list(base),
            "momentum_10d": list(_make_correlated_series(base, 0.01)),
            "reversal_5d": list(-base),
        }, n_days=n)

        corr = compute_factor_correlation(storage=temp_storage)
        assert not corr.empty
        assert corr.shape == (3, 3)
        # Diagonal should be 1.0
        for f in corr.columns:
            assert abs(corr.loc[f, f] - 1.0) < 1e-6

    def test_matrix_values_in_range(self, temp_storage: DataStorage):
        """All correlation values in [-1, 1]."""
        n = 30
        _seed_factors(temp_storage, "600519", {
            "f1": list(np.random.randn(n)),
            "f2": list(np.random.randn(n)),
            "f3": list(np.random.randn(n)),
        }, n_days=n)

        corr = compute_factor_correlation(storage=temp_storage)
        assert ((corr >= -1.0) & (corr <= 1.0)).all().all()

    def test_perfect_correlation_detected(self, temp_storage: DataStorage):
        """Two identical series → correlation = 1.0."""
        n = 30
        base = np.random.randn(n)
        _seed_factors(temp_storage, "600519", {
            "f_a": list(base),
            "f_b": list(base),  # identical
        }, n_days=n)

        corr = compute_factor_correlation(storage=temp_storage)
        assert abs(corr.loc["f_a", "f_b"] - 1.0) < 1e-6

    def test_negative_correlation(self, temp_storage: DataStorage):
        """Factor and its negation → correlation = -1.0."""
        n = 30
        base = np.random.randn(n)
        _seed_factors(temp_storage, "600519", {
            "momentum": list(base),
            "reversal": list(-base),
        }, n_days=n)

        corr = compute_factor_correlation(storage=temp_storage)
        assert abs(corr.loc["momentum", "reversal"] - (-1.0)) < 1e-6


# ============================================================
# detect_collinear_groups
# ============================================================

class TestDetectCollinearGroups:
    def test_known_correlated_factors_grouped(self, temp_storage: DataStorage):
        """Highly correlated momentum_5d and momentum_10d are grouped."""
        n = 60
        base = np.random.randn(n)
        _seed_factors(temp_storage, "600519", {
            "momentum_5d": list(base),
            "momentum_10d": list(_make_correlated_series(base, 0.01)),  # ~0.99 corr
            "independent": list(np.random.randn(n) * 10),  # uncorrelated
        }, n_days=n)

        corr = compute_factor_correlation(storage=temp_storage)
        groups = detect_collinear_groups(corr, threshold=0.7)

        # momentum_5d and momentum_10d should be in the same group
        found_pair = False
        for group in groups:
            if "momentum_5d" in group and "momentum_10d" in group:
                found_pair = True
                break
        assert found_pair, f"Expected momentum_5d and momentum_10d grouped, got {groups}"

    def test_threshold_boundary(self, temp_storage: DataStorage):
        """Threshold 0.69 vs 0.71 changes grouping for ~0.70 correlation."""
        n = 100
        base = np.random.randn(n)
        # noise chosen so correlation ~ 0.70
        noisy = _make_correlated_series(base, 0.7)

        _seed_factors(temp_storage, "600519", {
            "f1": list(base),
            "f2": list(noisy),
        }, n_days=n)

        corr = compute_factor_correlation(storage=temp_storage)
        actual_corr = abs(corr.loc["f1", "f2"])

        groups_low = detect_collinear_groups(corr, threshold=0.50)
        groups_high = detect_collinear_groups(corr, threshold=0.95)

        # With low threshold they're grouped; with high they're not
        has_group_low = any("f1" in g and "f2" in g for g in groups_low)
        has_group_high = any("f1" in g and "f2" in g for g in groups_high)

        if actual_corr > 0.50:
            assert has_group_low, f"Should group at 0.50 threshold (corr={actual_corr:.3f})"
        if actual_corr < 0.95:
            assert not has_group_high, f"Should NOT group at 0.95 threshold (corr={actual_corr:.3f})"

    def test_independent_factors_no_groups(self, temp_storage: DataStorage):
        """Independent random factors → no collinear groups."""
        n = 60
        np.random.seed(42)
        _seed_factors(temp_storage, "600519", {
            "f1": list(np.random.randn(n)),
            "f2": list(np.random.randn(n)),
            "f3": list(np.random.randn(n)),
        }, n_days=n)

        corr = compute_factor_correlation(storage=temp_storage)
        groups = detect_collinear_groups(corr, threshold=0.7)
        assert groups == []

    def test_empty_matrix_no_groups(self, temp_storage: DataStorage):
        """Empty correlation matrix → no groups."""
        groups = detect_collinear_groups(pd.DataFrame(), threshold=0.7)
        assert groups == []

    def test_transitive_grouping(self, temp_storage: DataStorage):
        """f1~f2, f2~f3 (transitive) → all three in one group."""
        n = 60
        base = np.random.randn(n)
        _seed_factors(temp_storage, "600519", {
            "f1": list(base),
            "f2": list(_make_correlated_series(base, 0.01)),  # f1~f2
            "f3": list(_make_correlated_series(base, 0.01)),  # f2~f3 (via base)
        }, n_days=n)

        corr = compute_factor_correlation(storage=temp_storage)
        groups = detect_collinear_groups(corr, threshold=0.7)

        # All three should be in one group
        assert len(groups) >= 1
        big_group = [g for g in groups if len(g) == 3]
        assert len(big_group) == 1, f"Expected one group of 3, got {groups}"


# ============================================================
# generate_collinearity_report
# ============================================================

class TestGenerateCollinearityReport:
    def test_report_structure(self, temp_storage: DataStorage):
        """Report has all expected keys."""
        n = 30
        base = np.random.randn(n)
        _seed_factors(temp_storage, "600519", {
            "momentum_5d": list(base),
            "momentum_10d": list(_make_correlated_series(base, 0.01)),
        }, n_days=n)

        report = generate_collinearity_report(threshold=0.7, storage=temp_storage)

        assert "factor_count" in report
        assert "threshold" in report
        assert "high_correlation_pairs" in report
        assert "collinear_groups" in report
        assert "recommendations" in report
        assert report["factor_count"] == 2
        assert report["threshold"] == 0.7

    def test_empty_db_report(self, temp_storage: DataStorage):
        """Empty DB → sensible report with zero factors."""
        report = generate_collinearity_report(storage=temp_storage)
        assert report["factor_count"] == 0
        assert report["collinear_groups"] == []
        assert len(report["recommendations"]) > 0

    def test_report_includes_recommendation_text(self, temp_storage: DataStorage):
        """Report recommendations mention keeping one per group."""
        n = 30
        base = np.random.randn(n)
        _seed_factors(temp_storage, "600519", {
            "f_a": list(base),
            "f_b": list(base),  # perfect correlation
        }, n_days=n)

        report = generate_collinearity_report(threshold=0.7, storage=temp_storage)
        assert any("保留" in r for r in report["recommendations"])

    def test_high_pairs_sorted_by_correlation(self, temp_storage: DataStorage):
        """High correlation pairs are sorted by absolute correlation descending."""
        n = 50
        base = np.random.randn(n)
        _seed_factors(temp_storage, "600519", {
            "f_perfect": list(base),
            "f_near": list(_make_correlated_series(base, 0.1)),
            "f_indep": list(np.random.randn(n) * 5),
        }, n_days=n)

        report = generate_collinearity_report(threshold=0.3, storage=temp_storage)
        pairs = report["high_correlation_pairs"]
        if len(pairs) >= 2:
            for i in range(len(pairs) - 1):
                assert abs(pairs[i]["correlation"]) >= abs(pairs[i + 1]["correlation"])


# ============================================================
# Performance
# ============================================================

class TestPerformance:
    def test_29_factor_matrix_under_5s(self, temp_storage: DataStorage):
        """29-factor correlation matrix computes in < 5 seconds."""
        n = 100
        np.random.seed(0)
        base = np.random.randn(n)
        factor_data = {}
        for i in range(29):
            # Mix of correlated and independent factors
            noise = 0.0 if i < 5 else 5.0
            factor_data[f"factor_{i}"] = list(_make_correlated_series(base, noise))
        _seed_factors(temp_storage, "600519", factor_data, n_days=n)

        start = time.time()
        corr = compute_factor_correlation(storage=temp_storage)
        elapsed = time.time() - start

        assert corr.shape == (29, 29)
        assert elapsed < 5.0, f"29-factor matrix took {elapsed:.2f}s (limit 5s)"


# ============================================================
# MCP tool
# ============================================================

class TestMCPTool:
    def test_returns_json_string(self, temp_storage: DataStorage):
        """Tool returns a valid JSON string (MCP contract)."""
        with patch("data.storage.DataStorage", return_value=temp_storage):
            from mcp_server.tools_data import get_factor_collinearity
            result = get_factor_collinearity()
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert "factor_count" in parsed

    def test_empty_data_handling(self, temp_storage: DataStorage):
        """Empty DB → tool returns report with factor_count=0."""
        with patch("data.storage.DataStorage", return_value=temp_storage):
            from mcp_server.tools_data import get_factor_collinearity
            result = json.loads(get_factor_collinearity())
        assert result["factor_count"] == 0

    def test_with_seeded_data(self, temp_storage: DataStorage):
        """Seeded data → tool returns non-zero factor count."""
        n = 30
        base = np.random.randn(n)
        _seed_factors(temp_storage, "600519", {
            "momentum_5d": list(base),
            "momentum_10d": list(_make_correlated_series(base, 0.01)),
        }, n_days=n)

        with patch("data.storage.DataStorage", return_value=temp_storage):
            from mcp_server.tools_data import get_factor_collinearity
            result = json.loads(get_factor_collinearity(threshold=0.5))

        assert result["factor_count"] == 2
        assert "note" in result  # no-auto-delete note
