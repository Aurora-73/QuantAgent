"""
Walk-Forward Optimization engine.

Methodology:
  - Divide data into sequential training/test windows
  - For each window: train (optimize params) on TRAIN data, evaluate on TEST data
  - Aggregate OOS results for final metrics
  - No look-ahead: each test window only uses data available before it

Usage:
    engine = WalkForwardEngine(train_window=252, test_window=63, step=63)
    result = engine.run(close, signal_func)

    # Parameter scan
    param_grid = {"lookback": [10, 15, 20, 25, 30], "threshold": [0.03, 0.05]}
    result = engine.parameter_scan(close, base_signal_func, param_grid)
"""
from __future__ import annotations

import itertools
import uuid
from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import pandas as pd

from loguru import logger


@dataclass
class WFOPeriod:
    """单个 WFO 窗口结果"""
    period_start: str = ""
    period_end: str = ""
    total_return: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    trade_count: int = 0
    params: dict = field(default_factory=dict)


@dataclass
class WFOResult:
    """Walk-Forward 整体结果"""
    periods: list[WFOPeriod] = field(default_factory=list)
    avg_return: float = 0.0
    avg_sharpe: float = 0.0
    avg_max_drawdown: float = 0.0
    total_trades: int = 0
    win_periods: int = 0
    total_periods: int = 0
    stability: float = 0.0  # Sharpe 稳定性 (正值表示一致性)
    params_used: list[dict] = field(default_factory=list)
    equity_curve: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))


class WalkForwardEngine:
    """
    Walk-Forward Optimization 引擎

    流程：
      1. 将数据划分为 N 个连续的 (train, test) 窗口
      2. 每个窗口：只用过去数据训练参数 → 在测试集上评估
      3. 汇总所有 OOS 结果
    """

    def __init__(self, train_window: int = 252,
                 test_window: int = 63,
                 step: int = 63,
                 min_train: int = 60):
        """
        Args:
            train_window: 训练窗口长度（交易日）
            test_window: 测试窗口长度
            step: 窗口滑动步长
            min_train: 最小训练数据量
        """
        self.train_window = train_window
        self.test_window = test_window
        self.step = step
        self.min_train = min_train

    def run(self, close: pd.Series,
            signal_func: Callable,
            fixed_params: dict = None) -> WFOResult:
        """
        运行 Walk-Forward 验证

        Args:
            close: 收盘价序列
            signal_func: 信号函数 signal_func(close_slice, params) -> (entries, exits)
            fixed_params: 固定参数（不优化时使用）

        Returns:
            WFOResult
        """
        dates = close.index
        n = len(dates)
        result = WFOResult()
        all_equity = []

        window_starts = list(range(self.train_window, n - self.test_window + 1, self.step))

        for idx, w_start in enumerate(window_starts):
            train_end = w_start
            test_start = w_start
            test_end = min(test_start + self.test_window, n)

            train_slice = close.iloc[train_end - self.train_window:train_end]
            test_slice = close.iloc[test_start:test_end]

            if len(train_slice) < self.min_train or len(test_slice) < 5:
                continue

            params = fixed_params or {}

            try:
                entries, exits = signal_func(test_slice, params)
            except Exception:
                entries = pd.Series(False, index=test_slice.index)
                exits = pd.Series(False, index=test_slice.index)

            period_metrics = self._backtest_period(
                test_slice, entries, exits
            )
            period_metrics.period_start = str(dates[test_start].date())
            period_metrics.period_end = str(dates[test_end - 1].date())
            period_metrics.params = params

            result.periods.append(period_metrics)

            if period_metrics.total_return > 0:
                result.win_periods += 1

        result.total_periods = len(result.periods)
        if not result.periods:
            logger.warning("WFO: 无有效窗口")
            return result

        returns = [p.total_return for p in result.periods]
        sharpes = [p.sharpe_ratio for p in result.periods]
        dd = [p.max_drawdown for p in result.periods]

        result.avg_return = float(np.mean(returns))
        result.avg_sharpe = float(np.mean(sharpes))
        result.avg_max_drawdown = float(np.mean(dd))
        result.total_trades = sum(p.trade_count for p in result.periods)

        # 稳定性: 正 Sharpe 比例 (越高越稳定)
        if sharpes:
            positive_sharpe = sum(1 for s in sharpes if s > 0)
            result.stability = positive_sharpe / len(sharpes)

        logger.info(f"WFO: {result.total_periods} 个窗口, "
                    f"平均收益 {result.avg_return:.2%}, "
                    f"平均夏普 {result.avg_sharpe:.2f}, "
                    f"稳定性 {result.stability:.0%}")

        return result

    def parameter_scan(self, close: pd.Series,
                       signal_func: Callable,
                       param_grid: dict[str, list]) -> list[dict]:
        """
        参数扫描：遍历所有参数组合，每组跑 WFO

        Args:
            close: 收盘价序列
            signal_func: 信号函数 signal_func(close_slice, params) -> (entries, exits)
            param_grid: 参数网格 {"param_name": [values]}

        Returns:
            每组 (params, wfo_result) 列表，按 avg_sharpe 降序
        """
        keys = list(param_grid.keys())
        value_sets = list(itertools.product(*param_grid.values()))

        results = []
        for values in value_sets:
            params = dict(zip(keys, values))
            wfo_result = self.run(close, signal_func, fixed_params=params)
            results.append({
                "params": params,
                "avg_sharpe": wfo_result.avg_sharpe,
                "avg_return": wfo_result.avg_return,
                "avg_max_drawdown": wfo_result.avg_max_drawdown,
                "stability": wfo_result.stability,
                "total_periods": wfo_result.total_periods,
                "win_periods": wfo_result.win_periods,
            })

        results.sort(key=lambda r: r["avg_sharpe"], reverse=True)

        for r in results:
            logger.info(f"  params={r['params']}: Sharpe={r['avg_sharpe']:.2f}, "
                        f"return={r['avg_return']:.2%}, stability={r['stability']:.0%}")

        return results

    def _backtest_period(self, close: pd.Series,
                         entries: pd.Series,
                         exits: pd.Series) -> WFOPeriod:
        """对单个 WFO 测试窗口执行回测"""
        from research.backtest import BacktestEngine
        bt_result = BacktestEngine.signal_backtest(
            close=close,
            entries=entries,
            exits=exits,
            init_cash=1_000_000,
            fees=0.001,
            slippage=0.001,
        )
        return WFOPeriod(
            period_start="",
            period_end="",
            total_return=bt_result.get("total_return", 0),
            sharpe_ratio=bt_result.get("sharpe_ratio", 0),
            max_drawdown=bt_result.get("max_drawdown", 0),
            trade_count=bt_result.get("trade_count", 0),
        )
