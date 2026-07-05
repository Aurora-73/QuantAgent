"""Risk engine boundary condition tests."""
from __future__ import annotations

import pandas as pd

from risk.risk_engine import RiskEngine, RiskConfig, RiskViolation


class TestSectorExposure:
    def test_sector_within_limit_passes(self):
        engine = RiskEngine()
        portfolio = [
            {"ticker": "600519", "weight": 0.05, "sector": "baijiu"},
            {"ticker": "000858", "weight": 0.05, "sector": "baijiu"},
            {"ticker": "300750", "weight": 0.10, "sector": "battery"},
        ]
        violations = engine._check_sector_exposure([], portfolio)
        baijiu_violations = [v for v in violations if v.ticker == "baijiu"]
        assert len(baijiu_violations) == 0  # 10% < 20% limit

    def test_sector_over_limit_triggers_violation(self):
        engine = RiskEngine()
        portfolio = [
            {"ticker": "600519", "weight": 0.15, "sector": "baijiu"},
            {"ticker": "000858", "weight": 0.10, "sector": "baijiu"},
        ]
        violations = engine._check_sector_exposure([], portfolio)
        baijiu_violations = [v for v in violations if v.ticker == "baijiu"]
        assert len(baijiu_violations) == 1  # 25% > 20% limit
        assert baijiu_violations[0].severity == "warning"

    def test_empty_portfolio_no_violations(self):
        engine = RiskEngine()
        violations = engine._check_sector_exposure([], [])
        assert len(violations) == 0


class TestTurnoverCheck:
    def test_turnover_within_limit(self):
        engine = RiskEngine()
        orders = [type("O", (), {"target_weight": 0.03})()]
        violations = engine._check_turnover(orders, [{"ticker": "600519", "weight": 0.1}])
        assert len(violations) == 0  # 0.03/2 = 1.5% < 10%

    def test_turnover_exceeds_limit(self):
        engine = RiskEngine()
        orders = [type("O", (), {"target_weight": 0.30})()]
        violations = engine._check_turnover(orders, [{"ticker": "600519", "weight": 0.0}])
        assert len(violations) == 1  # 0.30/2 = 15% > 10%
        assert violations[0].rule == "daily_turnover"

    def test_empty_orders_no_violations(self):
        engine = RiskEngine()
        violations = engine._check_turnover([], [])
        assert len(violations) == 0


class TestDrawdownGuard:
    def test_moderate_drawdown_passes(self):
        engine = RiskEngine()
        equity = pd.Series([1.0, 1.02, 1.01, 0.98, 0.99, 1.0])
        report = engine.check_drawdown(equity)
        assert report.passed is True

    def test_severe_drawdown_blocks(self):
        engine = RiskEngine()
        equity = pd.Series([1.0, 1.02, 0.95, 0.90, 0.93, 0.91, 0.89])
        report = engine.check_drawdown(equity)
        assert report.passed is False
        assert any(v.rule == "max_drawdown" for v in report.violations)

    def test_daily_loss_exceeds_limit(self):
        engine = RiskEngine()
        report = engine.check_daily_loss(-0.03)  # -3% < -2% limit
        assert report.passed is False
        assert any(v.rule == "daily_loss" for v in report.violations)

    def test_daily_loss_within_limit(self):
        engine = RiskEngine()
        report = engine.check_daily_loss(-0.01)  # -1% > -2% limit
        assert report.passed is True


class TestBlacklist:
    def test_blacklisted_ticker_blocked(self):
        engine = RiskEngine(RiskConfig(blacklist=["600519"]))
        orders = [type("O", (), {"ticker": "600519"})()]
        violations = engine._check_blacklist(orders)
        assert len(violations) == 1
        assert violations[0].severity == "block"

    def test_non_blacklisted_ticker_allowed(self):
        engine = RiskEngine(RiskConfig(blacklist=["600519"]))
        orders = [type("O", (), {"ticker": "000001"})()]
        violations = engine._check_blacklist(orders)
        assert len(violations) == 0
