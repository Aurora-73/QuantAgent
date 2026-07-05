"""
Strategy Decay Detector — monitor rolling performance metrics.

Detection rules:
  - Rolling 20-day win rate < 40% AND Sharpe < 0 → CRITICAL
  - IC < 0.02 for 20 consecutive periods → WARNING
  - IC direction reverses (positive→negative) → CRITICAL
  - Decay > 50% within 5 days → WARNING
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import numpy as np
import pandas as pd


class AlertLevel(Enum):
    OK = "ok"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class DecayAlert:
    """衰退告警"""
    level: AlertLevel
    metric: str
    message: str
    current_value: float = 0.0
    threshold: float = 0.0


@dataclass
class DecayReport:
    """衰退检测报告"""
    alerts: list[DecayAlert] = field(default_factory=list)
    is_decaying: bool = False

    @property
    def max_level(self) -> AlertLevel:
        if not self.alerts:
            return AlertLevel.OK
        levels = {a.level for a in self.alerts}
        if AlertLevel.CRITICAL in levels:
            return AlertLevel.CRITICAL
        if AlertLevel.WARNING in levels:
            return AlertLevel.WARNING
        return AlertLevel.OK


class DecayDetector:
    """
    策略衰退检测器

    用法:
        detector = DecayDetector()
        report = detector.check(win_rate_series, sharpe_series)
    """

    def __init__(self, win_rate_threshold: float = 0.40,
                 sharpe_threshold: float = 0.0,
                 ic_threshold: float = 0.02,
                 ic_consecutive_days: int = 20,
                 decay_speed_threshold: float = 0.50,
                 decay_speed_window: int = 5):
        self.win_rate_threshold = win_rate_threshold
        self.sharpe_threshold = sharpe_threshold
        self.ic_threshold = ic_threshold
        self.ic_consecutive_days = ic_consecutive_days
        self.decay_speed_threshold = decay_speed_threshold
        self.decay_speed_window = decay_speed_window

    def check(self, win_rate: pd.Series = None,
              sharpe: pd.Series = None,
              ic: pd.Series = None,
              returns: pd.Series = None) -> DecayReport:
        """
        运行衰退检测

        Args:
            win_rate: 滚动胜率序列
            sharpe: 滚动夏普序列
            ic: IC 序列
            returns: 收益序列（用于衰减速度检测）

        Returns:
            DecayReport
        """
        alerts = []

        # Rule 1: 胜率 + 夏普组合检测
        if win_rate is not None and sharpe is not None:
            latest_win = win_rate.iloc[-1] if len(win_rate) > 0 else 1.0
            latest_sharpe = sharpe.iloc[-1] if len(sharpe) > 0 else 1.0
            if latest_win < self.win_rate_threshold and latest_sharpe < self.sharpe_threshold:
                alerts.append(DecayAlert(
                    level=AlertLevel.CRITICAL,
                    metric="组合衰退",
                    message=f"滚动胜率 {latest_win:.1%} < {self.win_rate_threshold:.0%} 且 "
                            f"夏普 {latest_sharpe:.2f} < {self.sharpe_threshold:.0f}",
                    current_value=latest_win,
                    threshold=self.win_rate_threshold,
                ))

        # Rule 2: IC 持续偏低
        if ic is not None and len(ic) >= self.ic_consecutive_days:
            recent_ic = ic.iloc[-self.ic_consecutive_days:]
            low_ic_count = (recent_ic.abs() < self.ic_threshold).sum()
            if low_ic_count >= self.ic_consecutive_days:
                alerts.append(DecayAlert(
                    level=AlertLevel.WARNING,
                    metric="IC衰减",
                    message=f"IC 连续 {self.ic_consecutive_days} 期低于 {self.ic_threshold}",
                    current_value=float(recent_ic.iloc[-1]),
                    threshold=self.ic_threshold,
                ))

        # Rule 3: IC 方向反转
        if ic is not None and len(ic) >= 20:
            recent = ic.iloc[-20:]
            if recent.iloc[0] > 0 and recent.iloc[-1] < 0:
                alerts.append(DecayAlert(
                    level=AlertLevel.CRITICAL,
                    metric="IC反转",
                    message=f"IC 从 {recent.iloc[0]:.4f} 转为 {recent.iloc[-1]:.4f}",
                    current_value=float(recent.iloc[-1]),
                    threshold=0.0,
                ))

        # Rule 4: 收益衰减速度
        if returns is not None and len(returns) >= self.decay_speed_window * 2:
            recent = returns.iloc[-self.decay_speed_window:]
            prior = returns.iloc[-self.decay_speed_window * 2:-self.decay_speed_window]
            recent_mean = recent.mean()
            prior_mean = prior.mean()
            if prior_mean > 0 and recent_mean < prior_mean * (1 - self.decay_speed_threshold):
                decay_pct = (prior_mean - recent_mean) / abs(prior_mean)
                alerts.append(DecayAlert(
                    level=AlertLevel.WARNING,
                    metric="收益衰减",
                    message=f"收益在 {self.decay_speed_window} 日内衰减 {decay_pct:.0%}",
                    current_value=float(recent_mean),
                    threshold=float(prior_mean * (1 - self.decay_speed_threshold)),
                ))

        return DecayReport(
            alerts=alerts,
            is_decaying=any(a.level in (AlertLevel.WARNING, AlertLevel.CRITICAL) for a in alerts),
        )
