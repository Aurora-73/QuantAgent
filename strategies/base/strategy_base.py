"""
策略基类 — 统一接口

所有策略必须实现以下方法：
  prepare_features()        准备特征
  generate_signal()         生成信号
  position_sizing()         仓位计算
  risk_check()              风控检查
  expected_holding_period() 预期持仓周期
  kill_switch_condition()   熔断条件

设计原则：
  1. 信号和执行分离
  2. 研究和实盘分离
  3. 预测和仓位分离
  4. AI 和规则分离
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Optional

import pandas as pd


# ============================================================
# 数据结构
# ============================================================

class Direction(Enum):
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


class SignalStrength(Enum):
    STRONG = "strong"      # 强信号
    MODERATE = "moderate"  # 中等信号
    WEAK = "weak"          # 弱信号
    NONE = "none"          # 无信号


@dataclass
class Signal:
    """一条交易信号"""
    ticker: str
    direction: Direction
    strength: SignalStrength
    score: float                  # 原始分数 (-1 ~ +1)
    confidence: float             # 置信度 (0 ~ 1)
    source: str                   # 来源 (factor / event / sentiment / regime)
    reason: str                   # 生成理由
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict = field(default_factory=dict)


@dataclass
class Position:
    """持仓"""
    ticker: str
    shares: int
    avg_cost: float
    market_value: float
    unrealized_pnl: float
    weight: float                 # 组合权重
    direction: Direction = Direction.LONG


@dataclass
class TradeOrder:
    """交易指令"""
    ticker: str
    direction: Direction          # BUY / SELL
    target_shares: int            # 目标股数
    order_type: str               # "limit" / "market"
    limit_price: Optional[float] = None
    reason: str = ""
    urgency: str = "normal"       # "low" / "normal" / "high"
    metadata: dict = field(default_factory=dict)


@dataclass
class RiskCheckResult:
    """风控检查结果"""
    passed: bool
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    adjusted_orders: list[TradeOrder] = field(default_factory=list)


@dataclass
class WeightVector:
    """
    连续权重向量 — 策略的统一输出接口。

    w ∈ [-1, +1] for each symbol:
      +1.0 = 满仓做多
       0.0 = 空仓
      -1.0 = 满仓做空

    多策略融合时直接加权平均，不需要离散信号转换。
    """
    weights: dict = field(default_factory=dict)   # {ticker: weight}
    confidence: float = 1.0
    source: str = ""
    reason: str = ""
    metadata: dict = field(default_factory=dict)

    def to_long_only(self) -> dict:
        """Convert to long-only weights (clip negatives to 0, re-normalize)."""
        pos = {k: max(v, 0.0) for k, v in self.weights.items()}
        total = sum(pos.values())
        if total > 0:
            pos = {k: v / total for k, v in pos.items()}
        return pos

    def to_signals(self, ticker: str = None) -> list:
        """Convert back to discrete signals for backward compatibility."""
        signals = []
        for sym, w in self.weights.items():
            if ticker and sym != ticker:
                continue
            if w > 0.2:
                direction = Direction.LONG
                strength = SignalStrength.STRONG if w > 0.6 else SignalStrength.MODERATE
            elif w < -0.2:
                direction = Direction.SHORT
                strength = SignalStrength.STRONG if w < -0.6 else SignalStrength.MODERATE
            else:
                direction = Direction.FLAT
                strength = SignalStrength.WEAK
            signals.append(Signal(
                ticker=sym, direction=direction, strength=strength,
                score=w, confidence=self.confidence, source=self.source,
                reason=self.reason,
            ))
        return signals

    def is_empty(self) -> bool:
        return not self.weights or all(abs(w) < 0.01 for w in self.weights.values())


@dataclass
class BacktestResult:
    """回测结果"""
    total_return: float
    annual_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    turnover: float
    trades: int
    details: dict = field(default_factory=dict)


# ============================================================
# 策略基类
# ============================================================

class StrategyBase(ABC):
    """
    策略插件基类

    每个策略是一个目录：
      strategies/
        momentum/
          __init__.py
          config.yaml
          features.py
          signals.py
        event_driven/
          __init__.py
          config.yaml
          features.py
          signals.py
    """

    def __init__(self, name: str, config: dict = None):
        self.name = name
        self.config = config or {}

    @abstractmethod
    def prepare_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        准备特征

        输入: 原始行情/基本面数据
        输出: 带特征的 DataFrame

        这一步只做数据变换，不做任何决策。
        特征列命名建议: {strategy}_{feature_name}
        例如: momentum_20d, momentum_60d, reversal_5d
        """
        pass

    @abstractmethod
    def generate_signal(self, features: pd.DataFrame,
                        context: dict = None) -> list[Signal]:
        """
        生成信号

        输入: prepare_features() 的输出 + 可选上下文 (LLM 摘要、事件标签等)
        输出: 信号列表

        注意:
        - 信号只表达方向和强度，不表达仓位大小
        - context 中可以包含 LLM 生成的情绪/事件信息，但只作为调制信号
        - 最终信号应落在结构化规则上，不能完全依赖 LLM 判断
        """
        pass

    # ============================================================
    # Weight Vector (new interface — Phase B)
    # ============================================================

    def generate_weight_vector(self, features: pd.DataFrame,
                               context: dict = None) -> WeightVector:
        """
        Generate continuous weight vector (new interface).

        Default: converts discrete signals to weights.
        Override this to directly produce continuous weights.
        """
        signals = self.generate_signal(features, context)
        weights = {}
        for s in signals:
            if s.direction == Direction.LONG:
                weights[s.ticker] = s.score
            elif s.direction == Direction.SHORT:
                weights[s.ticker] = -s.score
            else:
                weights[s.ticker] = 0.0
        return WeightVector(
            weights=weights,
            confidence=sum(s.confidence for s in signals) / max(len(signals), 1),
            source=self.name,
            reason="Converted from discrete signals",
        )

    def cash_deployment_signal(self, cash_ratio: float) -> dict:
        """
        Cash deployment fallback for idle funds (source: fengyezi).

        When strategy has no signal or position is not full,
        idle cash is deployed to reverse repo / money market fund.

        Args:
            cash_ratio: Fraction of portfolio in cash (0-1)

        Returns:
            {action: "repo"/"mmf"/"hold", ratio: float, reason: str}
        """
        if cash_ratio < 0.05:
            return {"action": "hold", "ratio": 0, "reason": "现金比例低于5%，无需操作"}
        if cash_ratio > 0.3:
            return {"action": "repo", "ratio": cash_ratio * 0.8,
                    "reason": f"现金比例{cash_ratio:.1%}较高，建议80%配置逆回购"}
        return {"action": "mmf", "ratio": cash_ratio * 0.5,
                "reason": f"现金比例{cash_ratio:.1%}，建议50%配置货币基金"}

    @abstractmethod
    def position_sizing(self, signals: list[Signal],
                        portfolio: list[Position],
                        total_capital: float) -> list[TradeOrder]:
        """
        仓位计算

        输入: 信号列表 + 当前持仓 + 总资金
        输出: 交易指令列表

        这一步做的是:
        - 信号到目标仓位的映射
        - 考虑现有持仓的调整
        - 输出具体的交易指令 (买多少/卖多少)
        """
        pass

    @abstractmethod
    def risk_check(self, orders: list[TradeOrder],
                   portfolio: list[Position]) -> RiskCheckResult:
        """
        风控检查

        输入: 交易指令 + 当前持仓
        输出: 检查结果 (通过/违规/调整后指令)

        策略级风控 (全局风控在 risk/ 模块):
        - 单票仓位上限
        - 行业集中度
        - 换手率限制
        - 流动性筛选
        """
        pass

    @abstractmethod
    def expected_holding_period(self) -> dict:
        """
        预期持仓周期

        返回:
        {
            "min_days": 1,
            "max_days": 20,
            "typical_days": 5,
            "rebalance_freq": "daily"  # daily / weekly / monthly
        }

        用于:
        - 交易成本估算
        - 换手率控制
        - 回测参数设置
        """
        pass

    @abstractmethod
    def kill_switch_condition(self) -> dict:
        """
        熔断条件

        返回:
        {
            "max_drawdown": -0.05,       # 最大回撤 -5%
            "daily_loss_limit": -0.02,   # 日亏损限额 -2%
            "consecutive_losses": 5,     # 连续亏损 5 次
            "volatility_spike": 3.0,     # 波动率突增 3 倍
        }

        触发后:
        - 停止开新仓
        - 可选: 强制平仓
        - 发送告警
        """
        pass

    # ============================================================
    # 辅助方法 (可选覆盖)
    # ============================================================

    def describe(self) -> str:
        """策略描述"""
        return f"Strategy: {self.name}"

    def get_params(self) -> dict:
        """获取策略参数"""
        return self.config

    def validate_data(self, data: pd.DataFrame) -> bool:
        """验证输入数据格式"""
        required_cols = {"open", "high", "low", "close", "volume"}
        return required_cols.issubset(set(data.columns))
