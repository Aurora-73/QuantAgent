"""
事件驱动策略

策略逻辑:
  1. 从知识库加载结构化事件 (earnings, analyst, regulatory, etc.)
  2. 按事件类型映射到信号方向和强度
  3. 时间衰减: 越旧的事件信号越弱
  4. 多事件叠加: 同一标的多个事件加权平均
  5. 输出连续权重向量

事件类型权重配置在 config.yaml event_weights 中。

数据来源:
  - EventExtractor (llm/extractor.py) — LLM 从新闻抽取的事件
  - knowledge/events/ — 结构化事件数据库
"""
import yaml
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from strategies.base import (StrategyBase, Signal, Position, TradeOrder, RiskCheckResult,
                              WeightVector, Direction, SignalStrength)
from strategies.registry import register_strategy


@register_strategy("event_driven", description="事件驱动策略 — Event→Signal 映射",
                   category="event")
class EventDrivenStrategy(StrategyBase):
    """事件驱动策略"""

    def __init__(self, config_path: str = None):
        config = {}
        if config_path is None:
            config_path = Path(__file__).parent / "config.yaml"
        if Path(config_path).exists():
            with open(config_path, encoding="utf-8") as f:
                config = yaml.safe_load(f)

        super().__init__(name="event_driven", config=config)

        self.event_weights = config.get("event_weights", {})
        self.min_confidence = config.get("min_confidence", 0.3)
        self.confidence_multiplier = config.get("confidence_multiplier", 1.0)
        self.max_signal_strength = config.get("max_signal_strength", 0.8)
        self.decay_days = config.get("decay_days", 5)
        self.min_decay = config.get("min_decay", 0.1)
        self.event_window_days = config.get("event_window_days", 3)
        self.max_position_pct = config.get("max_position_pct", 0.05)
        self.target_positions = config.get("target_positions", 10)
        self.rebalance_freq = config.get("rebalance_freq", "daily")

    def prepare_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """事件策略不依赖传统技术特征，直接返回原数据"""
        return data.copy()

    def generate_signal(self, features: pd.DataFrame,
                        context: dict = None) -> list[Signal]:
        """
        从 context 中的事件列表生成信号。

        context 格式:
        {
            "events": [
                {
                    "ticker": "600519",
                    "event_type": "earnings_surprise",
                    "confidence": 0.85,
                    "timestamp": "2026-07-01T10:00:00",
                    "detail": "Q2 净利润超预期 20%",
                    "sentiment": "positive",
                },
                ...
            ],
        }
        """
        signals = []
        events = (context or {}).get("events", [])
        if not events:
            return signals

        # Group events by ticker
        ticker_events: dict[str, list[dict]] = {}
        for ev in events:
            t = ev.get("ticker", "")
            if t:
                ticker_events.setdefault(t, []).append(ev)

        for ticker, ev_list in ticker_events.items():
            weighted_scores = []
            confidences = []

            for ev in ev_list:
                event_type = ev.get("event_type", "")
                confidence = ev.get("confidence", self.min_confidence)
                timestamp = ev.get("timestamp")

                if confidence < self.min_confidence:
                    continue

                # Base weight from event type
                base_weight = self.event_weights.get(event_type, 0.0)
                if base_weight == 0.0:
                    continue

                # Time decay
                decay = 1.0
                if timestamp:
                    try:
                        if isinstance(timestamp, str):
                            ev_time = datetime.fromisoformat(timestamp)
                        else:
                            ev_time = timestamp
                        hours_ago = (datetime.now() - ev_time).total_seconds() / 3600
                        days_ago = hours_ago / 24
                        if days_ago > self.event_window_days:
                            continue
                        decay = max(1.0 - days_ago / self.decay_days, self.min_decay)
                    except (ValueError, TypeError):
                        pass

                score = base_weight * confidence * decay * self.confidence_multiplier
                score = np.clip(score, -self.max_signal_strength, self.max_signal_strength)
                weighted_scores.append(score)
                confidences.append(confidence)

            if not weighted_scores:
                continue

            # Multiple events: weighted average
            avg_score = np.average(weighted_scores, weights=confidences)
            avg_conf = float(np.mean(confidences))

            direction = Direction.LONG if avg_score > 0.05 else \
                Direction.SHORT if avg_score < -0.05 else Direction.FLAT

            strength = SignalStrength.STRONG if abs(avg_score) > 0.5 else \
                SignalStrength.MODERATE if abs(avg_score) > 0.2 else SignalStrength.WEAK

            signals.append(Signal(
                ticker=ticker,
                direction=direction,
                strength=strength,
                score=float(avg_score),
                confidence=float(avg_conf),
                source="event_driven",
                reason=f"{len(ev_list)} events: "
                       f"{', '.join(e.get('event_type', '') for e in ev_list[:3])}",
            ))

        return signals

    def position_sizing(self, signals: list[Signal],
                        portfolio: list[Position],
                        total_capital: float) -> list[TradeOrder]:
        """基于信号强度和置信度的仓位计算"""
        orders = []
        if not signals:
            return orders

        # Sort by abs(score) descending
        sorted_sigs = sorted(signals, key=lambda s: abs(s.score), reverse=True)
        target_count = min(self.target_positions, len(sorted_sigs))
        top_signals = sorted_sigs[:target_count]

        for sig in top_signals:
            target_value = total_capital * self.max_position_pct * abs(sig.score)
            price = None  # Will be filled by caller

            existing = [p for p in portfolio if p.ticker == sig.ticker]
            current_qty = existing[0].shares if existing else 0

            orders.append(TradeOrder(
                ticker=sig.ticker,
                direction=sig.direction,
                target_shares=abs(int(target_value / 10000)) * 100,  # rough lot estimate
                order_type="market",
                reason=f"event_driven: {sig.reason}",
            ))

        return orders

    def risk_check(self, orders: list[TradeOrder],
                   portfolio: list[Position]) -> RiskCheckResult:
        """事件策略风控: 事件衰减过快时降低仓位"""
        violations = []
        for o in orders:
            if o.target_shares > 0:
                violations.append(f"事件驱动开仓: {o.ticker}")
        return RiskCheckResult(
            passed=len(violations) == 0,
            violations=violations,
        )

    def expected_holding_period(self) -> dict:
        return {
            "min_days": 1,
            "max_days": self.decay_days,
            "typical_days": 3,
            "rebalance_freq": self.rebalance_freq,
        }

    def kill_switch_condition(self) -> dict:
        return {
            "max_drawdown": self.config.get("max_drawdown", -0.05),
            "daily_loss_limit": self.config.get("daily_loss_limit", -0.02),
            "consecutive_losses": 3,
            "volatility_spike": 2.0,
        }
