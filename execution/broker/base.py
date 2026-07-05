"""
Paper Broker — abstract execution interface.

Defines the broker contract that all execution backends must implement.
Supports both paper simulation and future live trading.

Key interfaces:
    place_order(order) -> OrderResult
    cancel_order(order_id) -> bool
    get_positions() -> list[Position]
    get_open_orders() -> list[Order]
"""
from __future__ import annotations

from abc import ABC, ABCMeta, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(Enum):
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    FILLED = "filled"
    PARTIAL_FILLED = "partial_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass
class Order:
    """订单"""
    order_id: str
    ticker: str
    side: OrderSide
    quantity: int  # 股数 (A 股为 100 的整数倍)
    order_type: str = "limit"  # limit / market
    price: Optional[float] = None
    status: OrderStatus = OrderStatus.SUBMITTED
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    filled_quantity: int = 0
    filled_avg_price: Optional[float] = None
    reason: str = ""


@dataclass
class OrderResult:
    """下单结果"""
    order: Order
    success: bool
    message: str = ""


@dataclass
class Position:
    """持仓"""
    ticker: str
    quantity: int
    avg_cost: float
    current_price: Optional[float] = None
    market_value: Optional[float] = None
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None


@dataclass
class PortfolioSummary:
    """组合摘要"""
    total_value: float
    cash: float
    positions: list[Position] = field(default_factory=list)
    open_orders: list[Order] = field(default_factory=list)
    pnl: float = 0.0
    pnl_pct: float = 0.0


class BrokerBase(ABC):
    """
    交易商抽象基类

    所有执行后端必须实现此接口。
    """

    @abstractmethod
    def place_order(self, order: Order) -> OrderResult:
        ...

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        ...

    @abstractmethod
    def get_positions(self) -> list[Position]:
        ...

    @abstractmethod
    def get_open_orders(self) -> list[Order]:
        ...

    @abstractmethod
    def get_portfolio_summary(self) -> PortfolioSummary:
        ...

    @abstractmethod
    def get_current_price(self, ticker: str) -> Optional[float]:
        ...
