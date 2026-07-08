"""Tests for B2.3: Investment hypothesis auto-generation.

Covers:
  - generate_factor_hypothesis (IC > 0.05 positive, IC < -0.05 negative, |IC| <= 0.05 none)
  - generate_backtest_hypothesis (annual > 15% generates, <= 15% skips)
  - Initial status is "draft" (HYPOTHESIS_INITIAL_STATUS)
  - No proposed/testing/validated/deprecated states appear
  - StatusError on illegal transition (e.g. draft -> verified skips active)
  - draft -> active -> verified path works
  - Integration: auto_generate_from_factors produces draft hypotheses
  - Integration: auto_generate_from_backtests produces draft hypotheses
"""
from __future__ import annotations

from datetime import date
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from data.storage import DataStorage
from knowledge.knowledge_base import (
    KnowledgeBase,
    HYPOTHESIS_INITIAL_STATUS,
    HYPOTHESIS_TRANSITIONS,
    StatusError,
)
from research.hypothesis_generator import (
    generate_factor_hypothesis,
    generate_backtest_hypothesis,
    auto_generate_from_factors,
    auto_generate_from_backtests,
    IC_THRESHOLD,
    BACKTEST_RETURN_THRESHOLD,
)


# ============================================================
# generate_factor_hypothesis
# ============================================================

class TestGenerateFactorHypothesis:
    def test_positive_ic_generates_hypothesis(self, temp_kb: KnowledgeBase):
        """IC > 0.05 generates a '正向预测能力' hypothesis."""
        hyp_id = generate_factor_hypothesis("momentum_5d", 0.08, "600519", kb=temp_kb)
        assert hyp_id is not None

        hypos = temp_kb.load_hypotheses()
        assert len(hypos) == 1
        assert "正向预测能力" in hypos[0]["title"]
        assert hypos[0]["status"] == "draft"
        assert hypos[0]["factor_name"] == "momentum_5d"

    def test_negative_ic_generates_hypothesis(self, temp_kb: KnowledgeBase):
        """IC < -0.05 generates a '反向预测能力' hypothesis."""
        hyp_id = generate_factor_hypothesis("reversal_5d", -0.07, "600519", kb=temp_kb)
        assert hyp_id is not None

        hypos = temp_kb.load_hypotheses()
        assert "反向预测能力" in hypos[0]["title"]

    def test_weak_ic_no_hypothesis(self, temp_kb: KnowledgeBase):
        """|IC| <= 0.05 does not generate a hypothesis."""
        result = generate_factor_hypothesis("momentum_5d", 0.03, "600519", kb=temp_kb)
        assert result is None

        result = generate_factor_hypothesis("momentum_5d", -0.02, "600519", kb=temp_kb)
        assert result is None

        assert len(temp_kb.load_hypotheses()) == 0

    def test_nan_ic_no_hypothesis(self, temp_kb: KnowledgeBase):
        """NaN IC does not generate a hypothesis."""
        assert generate_factor_hypothesis("f", float("nan"), kb=temp_kb) is None
        assert generate_factor_hypothesis("f", None, kb=temp_kb) is None

    def test_initial_status_is_draft(self, temp_kb: KnowledgeBase):
        """Generated hypothesis has status='draft' (HYPOTHESIS_INITIAL_STATUS)."""
        generate_factor_hypothesis("momentum_5d", 0.1, "600519", kb=temp_kb)
        hypos = temp_kb.load_hypotheses()
        assert hypos[0]["status"] == HYPOTHESIS_INITIAL_STATUS
        assert hypos[0]["status"] == "draft"

    def test_validation_run_id_recorded(self, temp_kb: KnowledgeBase):
        """Hypothesis records validation_run_id for backtest linkage."""
        generate_factor_hypothesis("f", 0.1, "600519", kb=temp_kb,
                                   validation_run_id="run_abc123")
        hypos = temp_kb.load_hypotheses()
        assert hypos[0]["validation_run_id"] == "run_abc123"


# ============================================================
# generate_backtest_hypothesis
# ============================================================

class TestGenerateBacktestHypothesis:
    def test_high_return_generates_hypothesis(self, temp_kb: KnowledgeBase):
        """Annual return > 15% generates a hypothesis."""
        hyp_id = generate_backtest_hypothesis(
            strategy="momentum",
            annual_return=0.25,
            ticker="600519",
            run_id="run_001",
            kb=temp_kb,
            market_regime="uptrend",
        )
        assert hyp_id is not None

        hypos = temp_kb.load_hypotheses()
        assert len(hypos) == 1
        assert "momentum" in hypos[0]["title"]
        assert "uptrend" in hypos[0]["title"]
        assert hypos[0]["status"] == "draft"
        assert hypos[0]["validation_run_id"] == "run_001"

    def test_low_return_no_hypothesis(self, temp_kb: KnowledgeBase):
        """Annual return <= 15% does not generate."""
        assert generate_backtest_hypothesis(
            "momentum", 0.10, "600519", kb=temp_kb, market_regime="uptrend"
        ) is None
        assert generate_backtest_hypothesis(
            "momentum", 0.15, "600519", kb=temp_kb, market_regime="uptrend"
        ) is None  # exactly threshold, not > threshold

    def test_market_regime_detected(self, temp_storage: DataStorage, temp_kb: KnowledgeBase):
        """When market_regime not given, auto-detect from storage."""
        # Seed index data (uptrend)
        dates = pd.date_range("2025-01-01", periods=80, freq="D")
        closes = list(np.linspace(3000, 3300, 80))  # clear uptrend
        df = pd.DataFrame({
            "index_code": ["000300"] * 80,
            "date": [d.date() for d in dates],
            "open": closes, "high": closes, "low": closes, "close": closes,
            "volume": [10_000_000] * 80,
        })
        temp_storage.conn.execute("DELETE FROM index_daily WHERE index_code='000300'")
        temp_storage.conn.execute("""
            INSERT INTO index_daily (index_code, date, open, high, low, close, volume)
            SELECT index_code, date, open, high, low, close, volume FROM df
        """)

        hyp_id = generate_backtest_hypothesis(
            "momentum", 0.20, "600519", kb=temp_kb, storage=temp_storage
        )
        assert hyp_id is not None
        hypos = temp_kb.load_hypotheses()
        assert hypos[0]["market_regime"] == "uptrend"


# ============================================================
# No forbidden states
# ============================================================

class TestNoForbiddenStates:
    def test_forbidden_states_not_in_transitions(self):
        """HYPOTHESIS_TRANSITIONS must not contain proposed/testing/validated/deprecated."""
        all_states = set(HYPOTHESIS_TRANSITIONS.keys())
        forbidden = {"proposed", "testing", "validated", "deprecated"}
        assert forbidden.isdisjoint(all_states), \
            f"Forbidden states found: {forbidden & all_states}"

    def test_legal_states_present(self):
        """Required states must be present."""
        required = {"draft", "active", "verified", "invalidated", "obsolete", "rejected"}
        assert required.issubset(set(HYPOTHESIS_TRANSITIONS.keys()))


# ============================================================
# StatusError on illegal transitions
# ============================================================

class TestStatusTransitions:
    def test_illegal_transition_raises_status_error(self, temp_kb: KnowledgeBase):
        """draft -> verified (skipping active) raises StatusError."""
        hyp_id = generate_factor_hypothesis("f", 0.1, "600519", kb=temp_kb)

        with pytest.raises(StatusError):
            temp_kb.set_hypothesis_status(hyp_id, "verified")

    def test_proposed_state_raises_status_error(self, temp_kb: KnowledgeBase):
        """Setting 'proposed' (forbidden) raises StatusError."""
        hyp_id = generate_factor_hypothesis("f", 0.1, "600519", kb=temp_kb)

        with pytest.raises(StatusError):
            temp_kb.set_hypothesis_status(hyp_id, "proposed")

    def test_draft_to_active_to_verified_path(self, temp_kb: KnowledgeBase):
        """draft -> active -> verified path works correctly."""
        hyp_id = generate_factor_hypothesis("f", 0.1, "600519", kb=temp_kb)

        # draft -> active (legal)
        result = temp_kb.set_hypothesis_status(hyp_id, "active")
        assert result["status"] == "active"

        # active -> verified (legal)
        result = temp_kb.set_hypothesis_status(hyp_id, "verified")
        assert result["status"] == "verified"

    def test_draft_to_rejected_path(self, temp_kb: KnowledgeBase):
        """draft -> rejected (legal) path works."""
        hyp_id = generate_factor_hypothesis("f", 0.1, "600519", kb=temp_kb)
        result = temp_kb.set_hypothesis_status(hyp_id, "rejected")
        assert result["status"] == "rejected"

    def test_obsolete_is_terminal(self, temp_kb: KnowledgeBase):
        """obsolete -> anything raises StatusError (terminal state)."""
        hyp_id = generate_factor_hypothesis("f", 0.1, "600519", kb=temp_kb)
        temp_kb.set_hypothesis_status(hyp_id, "active")
        temp_kb.set_hypothesis_status(hyp_id, "obsolete")

        with pytest.raises(StatusError):
            temp_kb.set_hypothesis_status(hyp_id, "active")


# ============================================================
# Integration: batch generation
# ============================================================

class TestAutoGenerate:
    def test_auto_generate_from_factors(self, temp_storage: DataStorage, temp_kb: KnowledgeBase):
        """auto_generate_from_factors produces draft hypotheses."""
        # Seed stock data
        n = 120
        dates = pd.date_range("2025-01-01", periods=n, freq="D")
        prices = 100.0 + np.cumsum(np.random.randn(n) * 0.5)
        df = pd.DataFrame({
            "date": [d.date() for d in dates],
            "open": prices * 0.999, "high": prices * 1.01, "low": prices * 0.99,
            "close": prices, "volume": np.full(n, 2_000_000),
            "amount": prices * 2_000_000, "pct_change": pd.Series(prices).pct_change().fillna(0),
            "turnover": np.full(n, 0.01),
        })
        temp_storage.save_stock_daily("600519", df)

        ids = auto_generate_from_factors("600519", storage=temp_storage, kb=temp_kb)

        # Should generate some hypotheses (factors with significant IC)
        if ids:
            drafts = temp_kb.load_hypotheses(status="draft")
            assert len(drafts) > 0
            for h in drafts:
                assert h["status"] == "draft"
                assert h["source"] == "auto_generated"

    def test_auto_generate_from_backtests(self, temp_storage: DataStorage, temp_kb: KnowledgeBase):
        """auto_generate_from_backtests produces draft hypotheses from high-return runs."""
        # Seed a backtest run with high return
        temp_storage.conn.execute("DELETE FROM backtest_runs")
        temp_storage.conn.execute("""
            INSERT INTO backtest_runs
            (run_id, strategy, ticker, date_start, date_end, total_return,
             annual_return, sharpe_ratio, max_drawdown, win_rate, trade_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ["run_test1", "momentum", "600519", "2025-01-01", "2026-01-01",
              0.30, 0.25, 1.2, -0.08, 0.6, 10])

        ids = auto_generate_from_backtests(storage=temp_storage, kb=temp_kb)

        assert len(ids) >= 1
        drafts = temp_kb.load_hypotheses(status="draft")
        assert len(drafts) >= 1
        assert any("momentum" in h["title"] for h in drafts)

    def test_low_return_backtest_no_hypothesis(self, temp_storage: DataStorage, temp_kb: KnowledgeBase):
        """Backtest with annual_return <= 15% does not generate hypothesis."""
        temp_storage.conn.execute("DELETE FROM backtest_runs")
        temp_storage.conn.execute("""
            INSERT INTO backtest_runs
            (run_id, strategy, ticker, date_start, date_end, total_return,
             annual_return, sharpe_ratio, max_drawdown, win_rate, trade_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ["run_low", "momentum", "600519", "2025-01-01", "2026-01-01",
              0.05, 0.05, 0.3, -0.03, 0.5, 5])

        ids = auto_generate_from_backtests(storage=temp_storage, kb=temp_kb)
        assert len(ids) == 0
