"""
Simulation Engine — local paper trading simulator.

Takes weight vectors from the strategy/risk pipeline and simulates
order execution with configurable slippage and lot-size constraints.

Usage:
    engine = SimulationEngine(initial_cash=1_000_000, slippage=0.001)
    orders = engine.weight_to_orders({"600519": 0.3, "000858": 0.2}, current_prices)
    results = engine.simulate(orders)

Features:
    - A-share lot constraint (100 shares per lot)
    - Configurable slippage model
    - Order lifecycle management (submitted→accepted→filled)
    - PnL tracking
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import pandas as pd
from loguru import logger

from execution.broker.base import (
    BrokerBase,
    Order,
    OrderResult,
    OrderSide,
    OrderStatus,
    PortfolioSummary,
    Position,
)


@dataclass
class SimulationResult:
    """仿真结果"""
    orders: list[Order] = field(default_factory=list)
    total_commission: float = 0.0
    total_slippage_cost: float = 0.0
    final_cash: float = 0.0
    positions: list[Position] = field(default_factory=list)
    filled_count: int = 0
    rejected_count: int = 0


class SimulationEngine(BrokerBase):
    """
    本地仿真引擎

    接受权重向量，模拟 A 股市场成交。
    """

    MIN_LOT = 100  # A 股最小交易单位

    def __init__(self,
                 initial_cash: float = 1_000_000,
                 commission_rate: float = 0.0003,  # 万3
                 min_commission: float = 5.0,       # 最低佣金 5 元
                 stamp_tax_rate: float = 0.001,     # 印花税 千1 (卖出)
                 slippage: float = 0.001,           # 滑点 0.1%
                 price_source: callable = None):
        """
        Args:
            initial_cash: 初始资金
            commission_rate: 佣金费率
            min_commission: 最低佣金
            stamp_tax_rate: 印花税率 (仅卖出)
            slippage: 滑点比例
            price_source: 价格获取函数 callable(ticker) -> float
        """
        self.cash = initial_cash
        self.initial_cash = initial_cash
        self.commission_rate = commission_rate
        self.min_commission = min_commission
        self.stamp_tax_rate = stamp_tax_rate
        self.slippage = slippage
        self.price_source = price_source or (lambda t: None)

        self._positions: dict[str, Position] = {}
        self._orders: list[Order] = []
        self._order_map: dict[str, Order] = {}

    # ============================================================
    # Broker 接口实现
    # ============================================================

    def place_order(self, order: Order) -> OrderResult:
        """提交订单"""
        order.order_id = f"sim_{uuid.uuid4().hex[:12]}"
        order.created_at = datetime.now()
        order.status = OrderStatus.SUBMITTED

        # 验证
        if order.quantity <= 0:
            order.status = OrderStatus.REJECTED
            return OrderResult(order=order, success=False, message="数量必须 > 0")

        if order.quantity % self.MIN_LOT != 0:
            order.status = OrderStatus.REJECTED
            return OrderResult(order=order, success=False,
                               message=f"数量必须是 {self.MIN_LOT} 的整数倍")

        if order.side == OrderSide.BUY:
            cost = order.quantity * (order.price or 0)
            if cost > self.cash:
                order.status = OrderStatus.REJECTED
                return OrderResult(order=order, success=False,
                                   message=f"资金不足: 需 {cost:.2f}, 有 {self.cash:.2f}")

        order.status = OrderStatus.ACCEPTED
        self._orders.append(order)
        self._order_map[order.order_id] = order
        return OrderResult(order=order, success=True, message="已接受")

    def cancel_order(self, order_id: str) -> bool:
        """撤销订单"""
        order = self._order_map.get(order_id)
        if order and order.status in (OrderStatus.SUBMITTED, OrderStatus.ACCEPTED):
            order.status = OrderStatus.CANCELLED
            return True
        return False

    def get_positions(self) -> list[Position]:
        """获取当前持仓"""
        return list(self._positions.values())

    def get_open_orders(self) -> list[Order]:
        """获取未完成订单"""
        return [o for o in self._orders
                if o.status in (OrderStatus.SUBMITTED, OrderStatus.ACCEPTED)]

    def get_portfolio_summary(self) -> PortfolioSummary:
        """获取组合摘要"""
        positions = self.get_positions()
        pos_value = sum(
            (p.current_price or p.avg_cost) * p.quantity
            for p in positions
        )
        total = self.cash + pos_value
        pnl = total - self.initial_cash
        return PortfolioSummary(
            total_value=round(total, 2),
            cash=round(self.cash, 2),
            positions=positions,
            open_orders=self.get_open_orders(),
            pnl=round(pnl, 2),
            pnl_pct=round(pnl / self.initial_cash, 4) if self.initial_cash > 0 else 0.0,
        )

    def get_current_price(self, ticker: str) -> Optional[float]:
        """获取当前价格"""
        return self.price_source(ticker)

    # ============================================================
    # 仿真特有方法
    # ============================================================

    def weight_to_orders(self,
                         target_weights: dict[str, float],
                         current_prices: dict[str, float]) -> list[Order]:
        """
        将目标权重向量转换为订单列表。

        Args:
            target_weights: {ticker: weight}, w ∈ [-1, +1]
            current_prices: {ticker: price}

        Returns:
            订单列表
        """
        total_capital = self.cash + sum(
            self._positions.get(t, Position(
                ticker=t, quantity=0, avg_cost=0
            )).quantity * current_prices.get(t, 0)
            for t in set(list(target_weights.keys()) + list(self._positions.keys()))
        )

        orders = []
        for ticker, weight in target_weights.items():
            price = current_prices.get(ticker)
            if not price or price <= 0:
                continue

            current_qty = self._positions.get(ticker, Position(
                ticker=ticker, quantity=0, avg_cost=0
            )).quantity
            target_value = abs(weight) * total_capital
            target_qty = int(target_value / price / self.MIN_LOT) * self.MIN_LOT

            if weight >= 0:
                # 买入
                qty_diff = target_qty - current_qty
                if qty_diff > 0:
                    orders.append(Order(
                        order_id="",
                        ticker=ticker,
                        side=OrderSide.BUY,
                        quantity=qty_diff,
                        order_type="market",
                        price=price,
                        reason=f"权重 {weight:.2f}",
                    ))
                elif qty_diff < 0:
                    # 减仓
                    orders.append(Order(
                        order_id="",
                        ticker=ticker,
                        side=OrderSide.SELL,
                        quantity=abs(qty_diff),
                        order_type="market",
                        price=price,
                        reason=f"权重 {weight:.2f} (减仓)",
                    ))
            else:
                # 做空权重 → 卖出现有持仓
                if current_qty > 0:
                    orders.append(Order(
                        order_id="",
                        ticker=ticker,
                        side=OrderSide.SELL,
                        quantity=current_qty,
                        order_type="market",
                        price=price,
                        reason=f"权重 {weight:.2f} (清仓)",
                    ))

        return orders

    def simulate(self, orders: list[Order]) -> SimulationResult:
        """
        批量执行订单模拟。

        Args:
            orders: 订单列表

        Returns:
            SimulationResult
        """
        result = SimulationResult()

        for order in orders:
            price = order.price or self.get_current_price(order.ticker)
            if not price:
                result.rejected_count += 1
                continue

            # 应用滑点
            exec_price = price * (1 + self.slippage) if order.side == OrderSide.BUY \
                else price * (1 - self.slippage)
            exec_price = round(exec_price, 3)

            # 计算佣金
            turnover = order.quantity * exec_price
            commission = max(turnover * self.commission_rate, self.min_commission)
            stamp_tax = turnover * self.stamp_tax_rate if order.side == OrderSide.SELL else 0.0
            total_cost = turnover + commission + stamp_tax

            if order.side == OrderSide.BUY:
                if total_cost > self.cash:
                    # 资金不足，按可用资金最大可买
                    max_qty = int(self.cash / (exec_price * (1 + self.commission_rate))
                                  / self.MIN_LOT) * self.MIN_LOT
                    if max_qty <= 0:
                        result.rejected_count += 1
                        continue
                    order.quantity = max_qty
                    turnover = order.quantity * exec_price
                    commission = max(turnover * self.commission_rate, self.min_commission)
                    total_cost = turnover + commission

                self.cash -= total_cost
                existing = self._positions.get(order.ticker)
                if existing:
                    total_qty = existing.quantity + order.quantity
                    total_cost_basis = existing.avg_cost * existing.quantity + turnover
                    existing.avg_cost = total_cost_basis / total_qty if total_qty > 0 else 0
                    existing.quantity = total_qty
                else:
                    self._positions[order.ticker] = Position(
                        ticker=order.ticker,
                        quantity=order.quantity,
                        avg_cost=exec_price,
                        current_price=exec_price,
                    )
            else:
                # 卖出
                existing = self._positions.get(order.ticker)
                if not existing or existing.quantity < order.quantity:
                    result.rejected_count += 1
                    continue
                self.cash += turnover - commission - stamp_tax
                existing.quantity -= order.quantity
                if existing.quantity <= 0:
                    del self._positions[order.ticker]

            order.status = OrderStatus.FILLED
            order.filled_quantity = order.quantity
            order.filled_avg_price = exec_price
            order.updated_at = datetime.now()
            result.orders.append(order)
            result.filled_count += 1
            result.total_commission += commission
            result.total_slippage_cost += turnover * self.slippage

        result.final_cash = self.cash
        result.positions = self.get_positions()
        return result

    def reset(self, initial_cash: float = None):
        """重置仿真引擎状态"""
        self.cash = initial_cash or self.initial_cash
        self._positions.clear()
        self._orders.clear()
        self._order_map.clear()
        logger.info("  仿真引擎已重置")
