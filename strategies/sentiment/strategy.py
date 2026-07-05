"""
情绪策略

策略逻辑:
  1. 从 SocialAnalyzer (llm/social_analyzer.py) 获取社交情绪
  2. 从新闻事件情绪 (extractor.py) 获取新闻情绪
  3. 反指规则: 散户高度一致时反向
  4. 情绪信号是辅助信号，max_signal_strength 限制在 0.6
  5. 输出连续权重向量

设计原则:
  - 情绪不覆盖量化信号，只做方向调制
  - 极端情绪 (一致看多/看空 > 80%) 启用反指
  - 情绪策略权重上限低于主策略
"""
import yaml
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from strategies.base import (StrategyBase, Signal, Position, TradeOrder, RiskCheckResult,
                              WeightVector, Direction, SignalStrength)
from strategies.registry import register_strategy


@register_strategy("sentiment", description="情绪策略 — 社交/新闻情绪→信号映射",
                   category="event")
class SentimentStrategy(StrategyBase):
    """情绪策略"""

    def __init__(self, config_path: str = None):
        config = {}
        if config_path is None:
            config_path = Path(__file__).parent / "config.yaml"
        if Path(config_path).exists():
            with open(config_path, encoding="utf-8") as f:
                config = yaml.safe_load(f)

        super().__init__(name="sentiment", config=config)

        self.sentiment_sources = config.get("sentiment_sources", {})
        self.bullish_threshold = config.get("bullish_threshold", 0.6)
        self.bearish_threshold = config.get("bearish_threshold", 0.6)
        self.min_confidence = config.get("min_confidence", 0.3)
        self.max_signal_strength = config.get("max_signal_strength", 0.6)
        self.contrarian_mode = config.get("contrarian_mode", True)
        self.contrarian_bull_threshold = config.get("contrarian_bull_threshold", 0.8)
        self.contrarian_bear_threshold = config.get("contrarian_bear_threshold", 0.8)
        self.decay_hours = config.get("decay_hours", 24)
        self.min_decay = config.get("min_decay", 0.2)
        self.max_position_pct = config.get("max_position_pct", 0.03)

    def prepare_features(self, data: pd.DataFrame) -> pd.DataFrame:
        return data.copy()

    def generate_signal(self, features: pd.DataFrame,
                        context: dict = None) -> list[Signal]:
        """
        从 context 中的情绪数据生成信号。

        context 格式:
        {
            "sentiment": {
                "social": {"sentiment": "bullish", "bull_ratio": 0.7, ...},
                "news": {"sentiment": "bearish", "confidence": 0.6, "tickers": [...]},
            },
        }
        """
        signals = []
        sentiment_data = (context or {}).get("sentiment", {})
        if not sentiment_data:
            return signals

        # Aggregate per ticker sentiment
        ticker_scores: dict[str, list[float]] = {}
        ticker_confidences: dict[str, list[float]] = {}

        for source, weight in self.sentiment_sources.items():
            source_data = sentiment_data.get(source)
            if not source_data:
                continue

            sentiment = source_data.get("sentiment", "neutral")
            confidence = source_data.get("confidence", 0.0)
            bull_ratio = source_data.get("bull_ratio", 0.0)
            bear_ratio = source_data.get("bear_ratio", 0.0)
            tickers = source_data.get("tickers", [])

            if confidence < self.min_confidence:
                continue

            # Calculate base score
            score = 0.0
            if sentiment == "bullish":
                score = bull_ratio * weight
                # Contrarian: extreme bullish retail → bearish signal
                if self.contrarian_mode and bull_ratio > self.contrarian_bull_threshold:
                    score = -abs(score) * 0.5  # Flip and halve
                    confidence *= 0.7  # Lower confidence in contrarian mode
            elif sentiment == "bearish":
                score = -bear_ratio * weight
                # Contrarian: extreme bearish retail → bullish signal
                if self.contrarian_mode and bear_ratio > self.contrarian_bear_threshold:
                    score = abs(score) * 0.5
                    confidence *= 0.7

            score = np.clip(score, -self.max_signal_strength, self.max_signal_strength)

            # Apply to mentioned tickers
            for ticker in (tickers if tickers else ["000300"]):
                ticker_scores.setdefault(ticker, []).append(score)
                ticker_confidences.setdefault(ticker, []).append(confidence)

        for ticker, scores in ticker_scores.items():
            avg_score = float(np.mean(scores))
            avg_conf = float(np.mean(ticker_confidences.get(ticker, [0.5])))

            direction = Direction.LONG if avg_score > 0.05 else \
                Direction.SHORT if avg_score < -0.05 else Direction.FLAT
            strength = SignalStrength.MODERATE if abs(avg_score) > 0.2 else SignalStrength.WEAK

            signals.append(Signal(
                ticker=ticker, direction=direction, strength=strength,
                score=avg_score, confidence=avg_conf,
                source="sentiment",
                reason=f"情绪: {avg_score:+.2f} (反指={'是' if self.contrarian_mode and abs(avg_score) < self.max_signal_strength * 0.5 else '否'})",
            ))

        return signals

    def position_sizing(self, signals: list[Signal],
                        portfolio: list[Position],
                        total_capital: float) -> list[TradeOrder]:
        """情绪策略仓位计算 (辅助策略，仓位上限低)"""
        orders = []
        for sig in signals[:self.target_positions]:
            target_value = total_capital * self.max_position_pct * abs(sig.score)
            orders.append(TradeOrder(
                ticker=sig.ticker,
                direction=sig.direction,
                target_shares=abs(int(target_value / 10000)) * 100,
                order_type="market",
                reason=f"sentiment: {sig.reason}",
            ))
        return orders

    def risk_check(self, orders: list[TradeOrder],
                   portfolio: list[Position]) -> RiskCheckResult:
        return RiskCheckResult(passed=True)

    def expected_holding_period(self) -> dict:
        return {
            "min_days": 1,
            "max_days": 3,
            "typical_days": 1,
            "rebalance_freq": "daily",
        }

    def kill_switch_condition(self) -> dict:
        return {
            "max_drawdown": self.config.get("max_drawdown", -0.03),
            "daily_loss_limit": self.config.get("daily_loss_limit", -0.01),
            "consecutive_losses": 3,
            "volatility_spike": 2.0,
        }
