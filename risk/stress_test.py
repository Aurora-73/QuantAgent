"""
Stress Test Engine — replay historical crisis scenarios.

Scenarios:
  1. 2015 Crash  — 2015-06-12 to 2016-01-28 (5178→2638, -49%)
  2. 2018 Bear   — 2018-01-24 to 2019-01-04 (3587→2440, -32%)
  3. 2020 COVID  — 2020-01-14 to 2020-03-19 (3127→2646, -15%)
  4. 2024 Jan    — 2024-01-02 to 2024-02-05 (2976→2635, -11%)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd

from loguru import logger


CRISIS_SCENARIOS = {
    "2015_crash": {
        "name": "2015 股灾",
        "start": "2015-06-12",
        "end": "2016-01-28",
        "index_drop": -0.49,
    },
    "2018_bear": {
        "name": "2018 熊市",
        "start": "2018-01-24",
        "end": "2019-01-04",
        "index_drop": -0.32,
    },
    "2020_covid": {
        "name": "2020 疫情",
        "start": "2020-01-14",
        "end": "2020-03-19",
        "index_drop": -0.15,
    },
    "2024_january": {
        "name": "2024 流动性危机",
        "start": "2024-01-02",
        "end": "2024-02-05",
        "index_drop": -0.11,
    },
}


@dataclass
class StressTestResult:
    """压力测试结果"""
    scenario: str
    scenario_name: str
    portfolio_return: float = 0.0
    benchmark_return: float = 0.0
    excess_return: float = 0.0
    max_drawdown: float = 0.0
    recovery_days: int = -1  # -1 = 未恢复
    survived: bool = True


@dataclass
class StressTestReport:
    """压力测试总报告"""
    results: list[StressTestResult] = field(default_factory=list)
    max_portfolio_drawdown: float = 0.0
    worst_scenario: str = ""
    all_survived: bool = True


class StressTestEngine:
    """
    压力测试引擎

    将组合置于历史危机场景中，模拟组合表现。
    """

    def __init__(self, scenarios: list[str] = None):
        """
        Args:
            scenarios: 场景列表，None=全部
        """
        if scenarios is None:
            self.scenarios = list(CRISIS_SCENARIOS.keys())
        else:
            self.scenarios = [s for s in scenarios if s in CRISIS_SCENARIOS]

    def run(self, portfolio_returns: pd.Series,
            benchmark_returns: pd.Series = None) -> StressTestReport:
        """
        运行压力测试

        Args:
            portfolio_returns: 组合日收益率序列 (DatetimeIndex)
            benchmark_returns: 基准日收益率序列 (可选)

        Returns:
            StressTestReport
        """
        report = StressTestReport()

        if portfolio_returns.empty:
            for key in self.scenarios:
                scenario = CRISIS_SCENARIOS[key]
                report.results.append(StressTestResult(
                    scenario=key,
                    scenario_name=scenario["name"],
                    survived=True,
                ))
            return report

        for key in self.scenarios:
            scenario = CRISIS_SCENARIOS[key]
            result = self._test_scenario(key, scenario, portfolio_returns, benchmark_returns)
            report.results.append(result)

        # 汇总
        if report.results:
            dds = [r.max_drawdown for r in report.results]
            report.max_portfolio_drawdown = min(dds)
            worst = report.results[int(np.argmin(dds))]
            report.worst_scenario = worst.scenario_name
            report.all_survived = all(r.survived for r in report.results)

        return report

    def _test_scenario(self, key: str, scenario: dict,
                       portfolio_returns: pd.Series,
                       benchmark_returns: pd.Series) -> StressTestResult:
        """测试单个场景"""
        start = pd.Timestamp(scenario["start"])
        end = pd.Timestamp(scenario["end"])
        mask = (portfolio_returns.index >= start) & (portfolio_returns.index <= end)

        if mask.sum() < 5:
            logger.warning(f"  无 {scenario['name']} 期间的数据（仅 {mask.sum()} 天，跳过）")
            return StressTestResult(
                scenario=key,
                scenario_name=scenario["name"],
                survived=True,
                recovery_days=-2,  # -2 = insufficient data
            )

        period_returns = portfolio_returns[mask]
        equity = (1 + period_returns).cumprod()
        peak = equity.expanding().max()
        drawdown = (equity - peak) / peak
        max_dd = float(drawdown.min())
        portfolio_return = float(equity.iloc[-1] - 1)

        # 恢复天数
        post_mask = portfolio_returns.index > end
        recovery_days = -1
        if post_mask.any():
            post_equity = (1 + portfolio_returns[post_mask]).cumprod()
            high_water_mark = equity.max()
            for i, v in enumerate(post_equity):
                if v >= high_water_mark:
                    recovery_days = i + 1
                    break

        result = StressTestResult(
            scenario=key,
            scenario_name=scenario["name"],
            portfolio_return=portfolio_return,
            max_drawdown=max_dd,
        )
        result.recovery_days = recovery_days
        result.survived = max_dd > -0.5  # 亏损 < 50% 算幸存

        if benchmark_returns is not None:
            bench_mask = (benchmark_returns.index >= start) & (benchmark_returns.index <= end)
            if bench_mask.sum() > 0:
                bench_ret = benchmark_returns[bench_mask]
                result.benchmark_return = float((1 + bench_ret).prod() - 1)
                result.excess_return = portfolio_return - result.benchmark_return

        logger.info(f"  {scenario['name']}: 组合 {portfolio_return:.2%}, "
                    f"回撤 {max_dd:.2%}, 恢复 {recovery_days if recovery_days>0 else '未'}天")
        return result
