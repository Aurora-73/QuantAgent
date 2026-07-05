"""
动量策略

策略逻辑：
  1. 计算 20 日动量因子 (20日收益率)
  2. 结合 RSI 和成交量过滤
  3. 选择动量最强的 N 只股票
  4. 等权或波动率加权
  5. 每周调仓

AI 辅助（可选）：
  - LLM 提供的情绪信号作为调制因子
  - 事件冲击评分作为过滤器
  - 但最终买卖决策由规则引擎决定
"""
import yaml
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from strategies.base import (StrategyBase, Signal, Position, TradeOrder, RiskCheckResult,
                              WeightVector, Direction, SignalStrength)
from strategies.registry import register_strategy
from research.factors import FactorEngine
from risk.risk_engine import RiskEngine, RiskConfig


@register_strategy("momentum", description="动量突破策略 — 20日动量 + RSI + 量比过滤",
                   category="trend")
class MomentumStrategy(StrategyBase):
    """动量策略"""

    def __init__(self, config_path: str = None):
        config = {}
        if config_path is None:
            config_path = Path(__file__).parent / "config.yaml"
        if Path(config_path).exists():
            with open(config_path, encoding="utf-8") as f:
                config = yaml.safe_load(f)

        super().__init__(name="momentum", config=config)

        self.lookback = config.get("lookback_period", 20)
        self.entry_threshold = config.get("entry_threshold", 0.05)
        self.exit_threshold = config.get("exit_threshold", -0.02)
        self.rsi_overbought = config.get("rsi_overbought", 70)
        self.rsi_oversold = config.get("rsi_oversold", 30)
        self.max_position_pct = config.get("max_position_pct", 0.05)
        self.target_positions = config.get("target_positions", 10)

        self.factor_engine = FactorEngine()

    def prepare_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        准备动量策略所需特征

        使用 FactorEngine 计算 25 个注册因子，再补充策略专用组合特征。

        输入: OHLCV DataFrame
        输出: 带特征列的 DataFrame
        """
        df = self.factor_engine.compute_all(data)

        # 映射列名（FactorEngine 的命名 → 策略期望的命名）
        df["momentum"] = df["momentum_20d"]
        df["rsi"] = df["rsi_14"]
        df["volume_ratio"] = df["volume_ratio_20d"]
        df["volatility"] = df["volatility_20d"]

        # 趋势强度: (MA20 - MA60) / MA60
        # 从 ma_deviation 反向计算 MA 值
        close = df["close"]
        ma20 = close / (1 + df["ma_deviation_20"])
        ma60 = close / (1 + df["ma_deviation_60"])
        df["trend_strength"] = (ma20 - ma60) / ma60

        return df

    def generate_signal(self, features: pd.DataFrame,
                        context: dict = None) -> list[Signal]:
        """
        生成动量信号

        信号逻辑：
          - 20日动量 > 阈值 → 做多
          - RSI < 超买线 → 确认不追高
          - 成交量放大 → 确认有效性
          - 趋势向上 → 确认方向
        """
        if features.empty:
            return []

        latest = features.iloc[-1]
        signals = []

        ticker = context.get("ticker", "unknown") if context else "unknown"

        momentum = latest.get("momentum", 0)
        rsi = latest.get("rsi", 50)
        volume_ratio = latest.get("volume_ratio", 1)
        trend = latest.get("trend_strength", 0)
        quality = latest.get("quality_momentum", 0)

        # 做多信号
        if (momentum > self.entry_threshold
                and rsi < self.rsi_overbought
                and volume_ratio > 0.8
                and trend > 0):

            # 信号强度
            if momentum > 0.15 and volume_ratio > 1.5:
                strength = SignalStrength.STRONG
                score = 0.8
            elif momentum > 0.10:
                strength = SignalStrength.MODERATE
                score = 0.6
            else:
                strength = SignalStrength.WEAK
                score = 0.4

            signals.append(Signal(
                ticker=ticker,
                direction=Direction.LONG,
                strength=strength,
                score=score,
                confidence=min(momentum * 5, 1.0),
                source="momentum",
                reason=f"动量{momentum:.1%}, RSI{rsi:.0f}, 量比{volume_ratio:.1f}, 趋势{trend:.1%}",
            ))

        # 出场信号
        elif momentum < self.exit_threshold or rsi > self.rsi_overbought:
            signals.append(Signal(
                ticker=ticker,
                direction=Direction.FLAT,
                strength=SignalStrength.MODERATE,
                score=-0.5,
                confidence=0.7,
                source="momentum",
                reason=f"动量衰减 {momentum:.1%} 或 RSI 超买 {rsi:.0f}",
            ))

        return signals

    def generate_weight_vector(self, features: pd.DataFrame,
                               context: dict = None) -> WeightVector:
        """
        Generate continuous weight vector directly.

        Converts momentum strength to weight w ∈ [-1, +1]:
          - Strong momentum + all filters pass → w > 0.5
          - Weak momentum → w ~ 0.3
          - Momentum breakdown → w < 0 (exit/flat)
        """
        if features.empty:
            return WeightVector(weights={}, confidence=0.0,
                               source=self.name, reason="无数据")

        latest = features.iloc[-1]
        ticker = context.get("ticker", "unknown") if context else "unknown"

        momentum = latest.get("momentum", 0)
        rsi = latest.get("rsi", 50)
        volume_ratio = latest.get("volume_ratio", 1)
        trend = latest.get("trend_strength", 0)
        quality = latest.get("quality_momentum", 0)

        # Continuous weight mapping
        if (momentum > self.entry_threshold
                and rsi < self.rsi_overbought
                and volume_ratio > 0.8
                and trend > 0):
            # Map momentum to [0.3, 1.0]
            weight = min(max(momentum * 5.0, 0.3), 1.0)
            confidence = min(momentum * 3.0 + 0.3, 0.95)
            reason = f"动量{momentum:.1%}, RSI{rsi:.0f}, 量比{volume_ratio:.1f}"
        elif momentum < self.exit_threshold or rsi > self.rsi_overbought:
            weight = -0.3  # Exit signal
            confidence = 0.7
            reason = f"退出: 动量{momentum:.1%} 或 RSI{rsi:.0f}超买"
        else:
            weight = 0.0
            confidence = 0.3
            reason = f"无信号: 动量{momentum:.1%}"

        return WeightVector(
            weights={ticker: weight},
            confidence=confidence,
            source=self.name,
            reason=reason,
        )

    def position_sizing(self, signals: list[Signal],
                        portfolio: list[Position],
                        total_capital: float) -> list[TradeOrder]:
        """
        仓位计算

        逻辑：
        - 等权分配到 target_positions 只股票
        - 单票不超过 max_position_pct
        - 信号越强，仓位越大
        """
        orders = []

        # 筛选做多信号
        long_signals = [s for s in signals if s.direction == Direction.LONG]
        flat_signals = [s for s in signals if s.direction == Direction.FLAT]

        # 按分数排序，取前 N
        long_signals.sort(key=lambda s: s.score, reverse=True)
        selected = long_signals[:self.target_positions]

        if not selected:
            return orders

        # 计算每只股票的目标仓位
        base_weight = min(1.0 / len(selected), self.max_position_pct)

        for signal in selected:
            # 根据信号强度调整权重
            weight = base_weight * (signal.score / 0.6)  # 以中等信号为基准
            weight = min(weight, self.max_position_pct)

            target_value = total_capital * weight
            # 简化：假设价格为1，实际需要当前价格
            target_shares = int(target_value)

            orders.append(TradeOrder(
                ticker=signal.ticker,
                direction=Direction.LONG,
                target_shares=target_shares,
                order_type="market",
                reason=signal.reason,
                metadata={"target_weight": weight},
            ))

        # 平仓信号
        for signal in flat_signals:
            orders.append(TradeOrder(
                ticker=signal.ticker,
                direction=Direction.FLAT,
                target_shares=0,
                order_type="market",
                reason=signal.reason,
            ))

        return orders

    def risk_check(self, orders: list[TradeOrder],
                   portfolio: list[Position]) -> RiskCheckResult:
        """
        策略级风控检查
        """
        violations = []
        warnings = []
        adjusted = []

        for order in orders:
            weight = order.metadata.get("target_weight", 0)

            # 单票仓位检查
            if weight > self.max_position_pct:
                warnings.append(
                    f"{order.ticker} 仓位 {weight:.2%} 超过上限 {self.max_position_pct:.2%}，已调整"
                )
                order.metadata["target_weight"] = self.max_position_pct
                order.target_shares = int(order.target_shares * self.max_position_pct / weight)

            adjusted.append(order)

        # 总仓位检查
        total_weight = sum(
            o.metadata.get("target_weight", 0)
            for o in adjusted if o.direction == Direction.LONG
        )
        if total_weight > 1.0:
            warnings.append(f"总仓位 {total_weight:.2%} 超过100%，需减仓")

        return RiskCheckResult(
            passed=len(violations) == 0,
            violations=violations,
            warnings=warnings,
            adjusted_orders=adjusted,
        )

    def expected_holding_period(self) -> dict:
        return {
            "min_days": 3,
            "max_days": 20,
            "typical_days": 10,
            "rebalance_freq": "weekly",
        }

    def kill_switch_condition(self) -> dict:
        return {
            "max_drawdown": -0.05,
            "daily_loss_limit": -0.02,
            "consecutive_losses": 5,
            "volatility_spike": 3.0,
        }

    # 因子计算已委托给 FactorEngine.compute_all()
    # 历史方法 _calc_rsi / _calc_atr 已移除
