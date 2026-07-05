"""
市场状态切换策略

策略逻辑:
  1. 从 MarketRegimeDetector 获取当前市场状态
  2. 根据 config.yaml regime_strategies 选择对应子策略
  3. 子策略可以是已有策略 (momentum / event_driven / sentiment)
  4. 输出子策略的加权权重向量
  5. 状态切换有冷却期，防止频繁切换

设计原则:
  - 不是每个 regime 都需要交易 (extreme_volatility → null)
  - 子策略通过 registry 动态加载
  - 切换有 cooldown，避免震荡市频繁切换
"""
import yaml
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from strategies.base import (StrategyBase, Signal, Position, TradeOrder, RiskCheckResult,
                              WeightVector, Direction, SignalStrength)
from strategies.registry import register_strategy, create_strategy, list_strategies


@register_strategy("regime_switch", description="市场状态切换策略 — Regime→子策略选择",
                   category="meta")
class RegimeSwitchStrategy(StrategyBase):
    """市场状态切换策略"""

    def __init__(self, config_path: str = None):
        config = {}
        if config_path is None:
            config_path = Path(__file__).parent / "config.yaml"
        if Path(config_path).exists():
            with open(config_path, encoding="utf-8") as f:
                config = yaml.safe_load(f)

        super().__init__(name="regime_switch", config=config)

        self.regime_strategies = config.get("regime_strategies", {})
        self.min_regime_confidence = config.get("min_regime_confidence", 0.3)
        self.cooldown_days = config.get("cooldown_days", 3)
        self.max_daily_switches = config.get("max_daily_switches", 2)
        self.max_position_pct = config.get("max_position_pct", 0.05)

        self._current_regime = None
        self._last_switch_date = None
        self._current_sub_strategy = None
        self._switch_count_today = 0

    def _get_sub_strategy(self, regime: str):
        """Get the sub-strategy for the current regime"""
        regime_config = self.regime_strategies.get(regime, {})
        strategy_name = regime_config.get("primary")
        if not strategy_name:
            return None
        params = regime_config.get("params", {})
        try:
            return create_strategy(strategy_name, **params)
        except ValueError:
            return None

    def prepare_features(self, data: pd.DataFrame) -> pd.DataFrame:
        return data.copy()

    def generate_signal(self, features: pd.DataFrame,
                        context: dict = None) -> list[Signal]:
        """
        根据市场状态选择子策略生成信号。

        context 格式:
        {
            "regime": "trend",           # 当前市场状态
            "regime_confidence": 0.78,   # 置信度
            "regime_detector": MarketRegimeDetector instance,  # 可选
        }
        """
        ctx = context or {}
        regime = ctx.get("regime", "unknown")
        regime_confidence = ctx.get("regime_confidence", 0.0)

        if regime_confidence < self.min_regime_confidence:
            return []  # 置信度不足，不开仓

        today = date.today()

        # 切换冷却期检查
        if self._current_regime and self._current_regime != regime:
            if self._last_switch_date:
                days_since_switch = (today - self._last_switch_date).days
                if days_since_switch < self.cooldown_days:
                    # 冷却期内保持原策略
                    regime = self._current_regime

        # 更新状态
        self._current_regime = regime
        self._last_switch_date = today

        # 获取子策略
        sub = self._get_sub_strategy(regime)
        if sub is None:
            return []  # 当前状态不开仓

        self._current_sub_strategy = sub

        # 委托子策略生成信号
        sub_signals = sub.generate_signal(features, context)
        regime_weight = self.regime_strategies.get(regime, {}).get("weight", 0.0)

        # 按 regime 权重调整信号强度
        for sig in sub_signals:
            sig.score *= regime_weight
            sig.source = f"regime_switch/{sub.name}"
            sig.reason = f"regime={regime}, sub={sub.name}: {sig.reason}"

        return sub_signals

    def position_sizing(self, signals: list[Signal],
                        portfolio: list[Position],
                        total_capital: float) -> list[TradeOrder]:
        if self._current_sub_strategy:
            return self._current_sub_strategy.position_sizing(signals, portfolio, total_capital)
        return []

    def risk_check(self, orders: list[TradeOrder],
                   portfolio: list[Position]) -> RiskCheckResult:
        return RiskCheckResult(passed=True)

    def expected_holding_period(self) -> dict:
        if self._current_sub_strategy:
            return self._current_sub_strategy.expected_holding_period()
        return {"min_days": 1, "max_days": 5, "typical_days": 3, "rebalance_freq": "daily"}

    def kill_switch_condition(self) -> dict:
        return {
            "max_drawdown": self.config.get("max_drawdown", -0.05),
            "daily_loss_limit": self.config.get("daily_loss_limit", -0.02),
            "consecutive_losses": 5,
            "volatility_spike": 3.0,
        }

    def get_current_regime(self) -> str:
        """获取当前市场状态"""
        return self._current_regime or "unknown"

    def get_current_sub_strategy(self) -> str:
        """获取当前子策略名称"""
        if self._current_sub_strategy:
            return self._current_sub_strategy.name
        return "none"
