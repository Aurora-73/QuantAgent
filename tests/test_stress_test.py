"""StressTestEngine tests — scenario execution, result structure."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from risk.stress_test import StressTestEngine, StressTestReport


def _make_return_series(periods=500, annual_vol=0.25) -> pd.Series:
    """Synthetic daily return series with DatetimeIndex."""
    dates = pd.date_range("2022-01-01", periods=periods, freq="D")
    daily_vol = annual_vol / np.sqrt(252)
    returns = np.random.randn(periods) * daily_vol
    return pd.Series(returns, index=dates)


class TestScenarioDefinitions:
    def test_default_scenarios_are_loaded(self):
        engine = StressTestEngine()
        assert len(engine.scenarios) >= 3
        assert "2015_crash" in engine.scenarios or all(
            s in engine.scenarios for s in ["2015_crash", "2018_bear", "2020_covid"]
        )

    def test_scenario_filtering(self):
        engine = StressTestEngine(scenarios=["2015_crash", "2018_bear"])
        assert len(engine.scenarios) == 2
        assert "2015_crash" in engine.scenarios
        assert "2018_bear" in engine.scenarios

    def test_invalid_scenario_excluded(self):
        engine = StressTestEngine(scenarios=["nonexistent"])
        assert len(engine.scenarios) == 0


class TestRunStressTest:
    def test_run_returns_stress_test_report(self):
        engine = StressTestEngine(scenarios=["2015_crash"])
        returns = _make_return_series(periods=600)
        report = engine.run(returns)
        assert isinstance(report, StressTestReport)

    def test_result_has_scenario_results(self):
        engine = StressTestEngine(scenarios=["2015_crash"])
        returns = _make_return_series(periods=600)
        report = engine.run(returns)
        assert len(report.results) == 1
        result = report.results[0]
        assert result.scenario == "2015_crash"
        assert isinstance(result.max_drawdown, float)
        assert isinstance(result.portfolio_return, float)

    def test_each_scenario_result_has_required_fields(self):
        engine = StressTestEngine(scenarios=["2015_crash", "2018_bear"])
        returns = _make_return_series(periods=600)
        report = engine.run(returns)
        for r in report.results:
            assert r.scenario in ("2015_crash", "2018_bear")
            assert hasattr(r, "portfolio_return")
            assert hasattr(r, "max_drawdown")
            assert hasattr(r, "survived")

    def test_report_has_summary_fields(self):
        engine = StressTestEngine(scenarios=["2015_crash"])
        returns = _make_return_series(periods=600)
        report = engine.run(returns)
        assert isinstance(report.max_portfolio_drawdown, float)
        assert isinstance(report.worst_scenario, str)
        assert isinstance(report.all_survived, bool)

    def test_worst_scenario_is_one_of_results(self):
        engine = StressTestEngine(scenarios=["2015_crash", "2018_bear"])
        returns = _make_return_series(periods=600)
        report = engine.run(returns)
        names = [r.scenario_name for r in report.results]
        assert report.worst_scenario in names

    def test_no_overlap_still_returns_report(self):
        """If return series does not cover scenario period, defaults apply."""
        engine = StressTestEngine(scenarios=["2015_crash"])
        # Returns from 2024 won't overlap with 2015 crash scenario
        dates = pd.date_range("2024-01-01", periods=100, freq="D")
        returns = pd.Series(np.zeros(100), index=dates)
        report = engine.run(returns)
        assert len(report.results) == 1
        assert report.results[0].survived is True
        assert report.results[0].max_drawdown == 0.0


class TestMultipleScenarios:
    def test_multiple_scenarios_all_processed(self):
        engine = StressTestEngine(
            scenarios=["2015_crash", "2018_bear", "2020_covid"]
        )
        returns = _make_return_series(periods=600)
        report = engine.run(returns)
        assert len(report.results) == 3

    def test_empty_return_series(self):
        engine = StressTestEngine(scenarios=["2015_crash"])
        returns = pd.Series([], dtype=float)
        report = engine.run(returns)
        assert len(report.results) == 1
