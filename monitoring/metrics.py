"""
指标追踪器

追踪策略和系统的关键指标：
  - 收益指标：总收益、年化收益、超额收益
  - 风险指标：最大回撤、波动率、夏普比率、Calmar 比率
  - 交易指标：胜率、盈亏比、换手率、滑点
  - 偏差指标：回测 vs 实盘偏差
"""
import pandas as pd
import numpy as np
from dataclasses import dataclass, field


@dataclass
class PerformanceMetrics:
    """绩效指标"""
    total_return: float = 0.0
    annual_return: float = 0.0
    excess_return: float = 0.0
    sharpe_ratio: float = 0.0
    calmar_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_duration: int = 0
    volatility: float = 0.0
    downside_volatility: float = 0.0
    win_rate: float = 0.0
    profit_loss_ratio: float = 0.0
    turnover: float = 0.0
    trade_count: int = 0
    avg_slippage: float = 0.0


class MetricsTracker:
    """指标追踪器"""

    @staticmethod
    def calculate_returns(equity_curve: pd.Series) -> pd.Series:
        """计算收益率序列"""
        return equity_curve.pct_change().dropna()

    @staticmethod
    def calculate_drawdown(equity_curve: pd.Series) -> pd.Series:
        """计算回撤序列"""
        peak = equity_curve.expanding().max()
        return (equity_curve - peak) / peak

    @staticmethod
    def calculate_max_drawdown(equity_curve: pd.Series) -> float:
        """计算最大回撤"""
        dd = MetricsTracker.calculate_drawdown(equity_curve)
        return dd.min()

    @staticmethod
    def calculate_sharpe(returns: pd.Series,
                         risk_free_rate: float = 0.02,
                         periods_per_year: int = 252) -> float:
        """计算夏普比率"""
        excess = returns.mean() * periods_per_year - risk_free_rate
        vol = returns.std() * np.sqrt(periods_per_year)
        return excess / vol if vol > 0 else 0.0

    @staticmethod
    def calculate_calmar(annual_return: float, max_drawdown: float) -> float:
        """计算 Calmar 比率"""
        return annual_return / abs(max_drawdown) if max_drawdown != 0 else 0.0

    @staticmethod
    def calculate_sortino(returns: pd.Series,
                          risk_free_rate: float = 0.02,
                          periods_per_year: int = 252) -> float:
        """计算 Sortino 比率"""
        excess = returns.mean() * periods_per_year - risk_free_rate
        downside = returns[returns < 0].std() * np.sqrt(periods_per_year)
        return excess / downside if downside > 0 else 0.0

    @staticmethod
    def calculate_win_rate(trades: list[dict]) -> float:
        """计算胜率"""
        if not trades:
            return 0.0
        wins = sum(1 for t in trades if t.get("pnl", 0) > 0)
        return wins / len(trades)

    @staticmethod
    def calculate_profit_loss_ratio(trades: list[dict]) -> float:
        """计算盈亏比"""
        gains = [t["pnl"] for t in trades if t.get("pnl", 0) > 0]
        losses = [abs(t["pnl"]) for t in trades if t.get("pnl", 0) < 0]
        avg_gain = np.mean(gains) if gains else 0
        avg_loss = np.mean(losses) if losses else 0
        return avg_gain / avg_loss if avg_loss > 0 else float("inf")

    @staticmethod
    def full_report(equity_curve: pd.Series,
                    trades: list[dict] = None,
                    benchmark: pd.Series = None,
                    risk_free_rate: float = 0.02) -> PerformanceMetrics:
        """
        生成完整绩效报告

        Args:
            equity_curve: 权益曲线
            trades: 交易记录
            benchmark: 基准曲线
            risk_free_rate: 无风险利率

        Returns:
            PerformanceMetrics
        """
        returns = MetricsTracker.calculate_returns(equity_curve)

        # 计算时间跨度
        try:
            total_days = (equity_curve.index[-1] - equity_curve.index[0]).days
        except AttributeError:
            total_days = len(equity_curve)

        total_return = (equity_curve.iloc[-1] / equity_curve.iloc[0]) - 1
        annual_return = (1 + total_return) ** (365 / max(total_days, 1)) - 1
        max_dd = MetricsTracker.calculate_max_drawdown(equity_curve)

        metrics = PerformanceMetrics(
            total_return=total_return,
            annual_return=annual_return,
            sharpe_ratio=MetricsTracker.calculate_sharpe(returns, risk_free_rate),
            calmar_ratio=MetricsTracker.calculate_calmar(annual_return, max_dd),
            sortino_ratio=MetricsTracker.calculate_sortino(returns, risk_free_rate),
            max_drawdown=max_dd,
            volatility=returns.std() * np.sqrt(252),
            trade_count=len(trades) if trades else 0,
            win_rate=MetricsTracker.calculate_win_rate(trades) if trades else 0,
            profit_loss_ratio=MetricsTracker.calculate_profit_loss_ratio(trades) if trades else 0,
        )

        if benchmark is not None:
            bench_returns = benchmark.pct_change().dropna()
            excess = returns - bench_returns.reindex(returns.index, method="ffill").fillna(0)
            metrics.excess_return = excess.sum()

        return metrics
