"""
统一数据契约 — 所有模块共享的核心类型

设计原则：
  - 所有模块依赖这些类型，不直接依赖第三方对象
  - 第三方对象在适配器层转换为这些类型
  - 字段命名统一：symbol, timestamp, source, market
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


# ============================================================
# 枚举
# ============================================================

class Direction(Enum):
    LONG = "long"
    SHORT = "short"


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    LIMIT = "limit"
    MARKET = "market"


class OrderStatus(Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class SignalStrength(Enum):
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    NONE = "none"


class Sentiment(Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class RuntimeMode(Enum):
    RESEARCH = "research"
    PAPER = "paper"
    LIVE = "live"


# ============================================================
# 行情数据
# ============================================================

@dataclass
class Bar:
    """K线"""
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float = 0.0
    turnover: float = 0.0
    source: str = ""
    adjust: str = ""  # qfq / hfq / ""


@dataclass
class Quote:
    """实时报价"""
    symbol: str
    timestamp: datetime
    last: float
    bid: float = 0.0
    ask: float = 0.0
    volume: float = 0.0
    source: str = ""


# ============================================================
# 基本面
# ============================================================

@dataclass
class FundamentalRecord:
    """基本面数据"""
    symbol: str
    timestamp: datetime
    report_type: str = ""  # annual / quarterly
    revenue: Optional[float] = None
    net_profit: Optional[float] = None
    pe: Optional[float] = None
    pb: Optional[float] = None
    roe: Optional[float] = None
    source: str = ""


# ============================================================
# 新闻与事件
# ============================================================

@dataclass
class NewsItem:
    """新闻条目"""
    title: str
    timestamp: datetime
    source: str
    url: str = ""
    content: str = ""
    symbols: list[str] = field(default_factory=list)
    sentiment: Sentiment = Sentiment.NEUTRAL


@dataclass
class Event:
    """结构化事件 — 系统规范类型"""
    event_id: str
    event_type: str
    symbol: str
    timestamp: datetime
    detail: str
    sentiment: Sentiment = Sentiment.NEUTRAL
    confidence: float = 0.5
    source: str = ""
    tags: list[str] = field(default_factory=list)
    company: str = ""
    impact_horizon: str = ""  # short / medium / long


# ============================================================
# 特征与信号
# ============================================================

@dataclass
class FeatureVector:
    """因子/特征向量"""
    symbol: str
    timestamp: datetime
    features: dict[str, float] = field(default_factory=dict)
    source: str = ""


@dataclass
class Signal:
    """交易信号"""
    symbol: str
    timestamp: datetime
    direction: Direction
    strength: SignalStrength
    score: float  # -1.0 ~ +1.0
    source: str  # 因子名 / 策略名 / LLM
    reason: str = ""
    confidence: float = 0.5


# ============================================================
# 订单与成交
# ============================================================

@dataclass
class Order:
    """订单"""
    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    price: float
    volume: float
    filled_volume: float = 0.0
    status: OrderStatus = OrderStatus.PENDING
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = ""
    strategy_id: str = ""


@dataclass
class Fill:
    """成交"""
    fill_id: str
    order_id: str
    symbol: str
    side: OrderSide
    price: float
    volume: float
    timestamp: datetime = field(default_factory=datetime.now)
    commission: float = 0.0
    slippage: float = 0.0


# ============================================================
# 持仓与组合
# ============================================================

@dataclass
class Position:
    """持仓"""
    symbol: str
    direction: Direction
    volume: float
    avg_cost: float
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0


@dataclass
class PortfolioSnapshot:
    """组合快照"""
    timestamp: datetime
    positions: list[Position] = field(default_factory=list)
    cash: float = 0.0
    total_value: float = 0.0
    daily_pnl: float = 0.0
    drawdown: float = 0.0
    source: str = ""


# ============================================================
# 研究输出
# ============================================================

@dataclass
class ResearchReport:
    """研究报告"""
    report_id: str
    report_type: str  # daily / weekly / monthly / event
    timestamp: datetime
    title: str
    summary: str
    sentiment: Sentiment = Sentiment.NEUTRAL
    confidence: float = 0.5
    key_points: list[str] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)
    symbols: list[str] = field(default_factory=list)
    source: str = ""


@dataclass
class Hypothesis:
    """投资假设"""
    hypothesis_id: str
    description: str
    timestamp: datetime
    metrics: list[str] = field(default_factory=list)
    status: str = "pending"  # pending / verified / rejected
    result: str = ""
    source: str = ""


# ============================================================
# LLM 结构化输出
# ============================================================

@dataclass
class LLMEventExtraction:
    """LLM 事件抽取结果"""
    events: list[Event] = field(default_factory=list)
    raw_text: str = ""
    parse_success: bool = True
    error: str = ""


@dataclass
class LLMSummary:
    """LLM 摘要结果"""
    title: str = ""
    summary: str = ""
    key_points: list[str] = field(default_factory=list)
    sentiment: Sentiment = Sentiment.NEUTRAL
    confidence: float = 0.5
    risk_flags: list[str] = field(default_factory=list)
    industry_impact: list[str] = field(default_factory=list)
    parse_success: bool = True
    error: str = ""


@dataclass
class LLMResearchDecision:
    """LLM 研究决策输出"""
    signal: str = "Hold"  # Buy / Overweight / Hold / Underweight / Sell
    signal_score: float = 0.0
    reasoning: str = ""
    key_factors: list[str] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)
    confidence: float = 0.5
    parse_success: bool = True
    error: str = ""


# ============================================================
# 回测结果
# ============================================================

@dataclass
class BacktestResult:
    """回测结果"""
    strategy_id: str
    start_date: str
    end_date: str
    total_return: float = 0.0
    annual_return: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    total_trades: int = 0
    turnover: float = 0.0
    params: dict = field(default_factory=dict)


# ============================================================
# 风控
# ============================================================

@dataclass
class RiskDecision:
    """风控决策"""
    approved: bool
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    adjusted_orders: list[Order] = field(default_factory=list)


# ============================================================
# 告警
# ============================================================

@dataclass
class Alert:
    """告警"""
    alert_id: str
    timestamp: datetime
    level: str  # info / warning / critical
    alert_type: str
    title: str
    detail: str
    source: str = ""
    acknowledged: bool = False
