"""
vnpy 适配器 — 执行层

职责：
  - 将 vnpy 的对象转换为系统内部数据契约
  - 只暴露系统需要的方法
  - 处理 vnpy 未安装时的降级

设计原则：
  - 业务代码不直接依赖 vnpy 的类型
  - 所有输入输出都是 data/schema.py 中定义的类型
  - vnpy 的 BarData, OrderData 等在适配器内部转换
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from data.schema import (
    Bar, Order, Fill, Position, PortfolioSnapshot,
    Direction, OrderSide, OrderType, OrderStatus,
)

# 将 vnpy 源码加入 path
_VNPY_ROOT = Path(__file__).parent.parent.parent / "_reference" / "vnpy"
if str(_VNPY_ROOT) not in sys.path:
    sys.path.insert(0, str(_VNPY_ROOT))

try:
    from vnpy.event import EventEngine
    from vnpy.trader.engine import MainEngine
    from vnpy.trader.constant import (
        Direction as VnDirection,
        Offset as VnOffset,
        Status as VnStatus,
        OrderType as VnOrderType,
        Exchange as VnExchange,
        Interval as VnInterval,
    )
    from vnpy.trader.utility import BarGenerator, ArrayManager
    _HAS_VNPY = True
except ImportError:
    _HAS_VNPY = False


def is_available() -> bool:
    """vnpy 是否可用"""
    return _HAS_VNPY


# ============================================================
# 类型转换
# ============================================================

def _to_internal_direction(vn_dir) -> Direction:
    if vn_dir == VnDirection.LONG:
        return Direction.LONG
    return Direction.SHORT


def _to_internal_status(vn_status) -> OrderStatus:
    mapping = {
        VnStatus.SUBMITTING: OrderStatus.SUBMITTED,
        VnStatus.NOTTRADED: OrderStatus.PENDING,
        VnStatus.PARTTRADED: OrderStatus.PARTIAL,
        VnStatus.ALLTRADED: OrderStatus.FILLED,
        VnStatus.CANCELLED: OrderStatus.CANCELLED,
        VnStatus.REJECTED: OrderStatus.REJECTED,
    }
    return mapping.get(vn_status, OrderStatus.PENDING)


_EXCHANGE_MAP = {
    "SSE": VnExchange.SSE,
    "SZSE": VnExchange.SZSE,
    "CFFEX": VnExchange.CFFEX,
    "SHFE": VnExchange.SHFE,
    "CZCE": VnExchange.CZCE,
    "DCE": VnExchange.DCE,
    "INE": VnExchange.INE,
    "GFEX": VnExchange.GFEX,
}


def _to_vn_exchange(exchange_str: str):
    return _EXCHANGE_MAP.get(exchange_str, VnExchange.SSE)


def convert_bar(vn_bar) -> Bar:
    """vnpy BarData -> 内部 Bar"""
    return Bar(
        symbol=vn_bar.symbol,
        timestamp=vn_bar.datetime,
        open=vn_bar.open_price,
        high=vn_bar.high_price,
        low=vn_bar.low_price,
        close=vn_bar.close_price,
        volume=vn_bar.volume,
        source="vnpy",
    )


def convert_position(vn_pos) -> Position:
    """vnpy PositionData -> 内部 Position"""
    return Position(
        symbol=vn_pos.symbol,
        direction=_to_internal_direction(vn_pos.direction),
        volume=vn_pos.volume,
        avg_cost=vn_pos.price,
        market_value=vn_pos.volume * vn_pos.price,
    )


def convert_order(vn_order) -> Order:
    """vnpy OrderData -> 内部 Order"""
    side = OrderSide.BUY if vn_order.direction == VnDirection.LONG else OrderSide.SELL
    otype = OrderType.LIMIT if vn_order.type == VnOrderType.LIMIT else OrderType.MARKET
    return Order(
        order_id=vn_order.orderid,
        symbol=vn_order.symbol,
        side=side,
        order_type=otype,
        price=vn_order.price,
        volume=vn_order.volume,
        filled_volume=vn_order.traded,
        status=_to_internal_status(vn_order.status),
        timestamp=vn_order.datetime if hasattr(vn_order, 'datetime') else datetime.now(),
    )


# ============================================================
# 适配器
# ============================================================

class VnpyAdapter:
    """
    vnpy 执行引擎适配器

    所有方法的输入输出都是 data/schema.py 中的类型。
    vnpy 的内部对象在适配器边界处转换。
    """

    def __init__(self):
        if not _HAS_VNPY:
            raise ImportError("vnpy 未正确安装。请先运行: sudo bash install_sudo.sh && bash install_venv.sh")
        self._event_engine: Optional[EventEngine] = None
        self._main_engine: Optional[MainEngine] = None
        self._connected = False

    def start(self):
        """启动引擎"""
        self._event_engine = EventEngine()
        self._main_engine = MainEngine(self._event_engine)

    def stop(self):
        """停止引擎"""
        if self._main_engine:
            self._main_engine.close()
            self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ----------------------------------------------------------
    # 连接
    # ----------------------------------------------------------

    def connect_ctp(self, setting: dict):
        """连接 CTP (国内期货)"""
        from vnpy_ctp import CtpGateway
        self._main_engine.add_gateway(CtpGateway)
        self._main_engine.connect(setting, "CTP")
        self._connected = True

    def connect_ib(self, setting: dict):
        """连接 Interactive Brokers"""
        from vnpy_ib import IbGateway
        self._main_engine.add_gateway(IbGateway)
        self._main_engine.connect(setting, "IB")
        self._connected = True

    def connect_xtp(self, setting: dict):
        """连接 XTP (国内股票)"""
        from vnpy_xtp import XtpGateway
        self._main_engine.add_gateway(XtpGateway)
        self._main_engine.connect(setting, "XTP")
        self._connected = True

    # ----------------------------------------------------------
    # 订单
    # ----------------------------------------------------------

    def send_order(self, symbol: str, exchange: str,
                   side: OrderSide, price: float, volume: float,
                   order_type: OrderType = OrderType.LIMIT,
                   gateway: str = "CTP") -> str:
        """
        发送订单

        Args:
            symbol: 合约代码
            exchange: 交易所 ("SSE", "SZSE", "SHFE", ...)
            side: 买卖方向
            price: 价格
            volume: 数量
            order_type: 订单类型
            gateway: 网关名称

        Returns:
            订单 ID
        """
        if not self._connected:
            raise RuntimeError("未连接到券商")

        from vnpy.trader.object import OrderRequest as VnOrderRequest

        vn_dir = VnDirection.LONG if side == OrderSide.BUY else VnDirection.SHORT
        vn_type = VnOrderType.LIMIT if order_type == OrderType.LIMIT else VnOrderType.MARKET

        req = VnOrderRequest(
            symbol=symbol,
            exchange=_to_vn_exchange(exchange),
            direction=vn_dir,
            type=vn_type,
            price=price,
            volume=volume,
            offset=VnOffset.OPEN,
        )
        return self._main_engine.send_order(req, gateway)

    def cancel_order(self, order_id: str, symbol: str,
                     exchange: str, gateway: str = "CTP"):
        """撤单"""
        if not self._connected:
            return
        from vnpy.trader.object import CancelRequest as VnCancelRequest
        req = VnCancelRequest(
            orderid=order_id,
            symbol=symbol,
            exchange=_to_vn_exchange(exchange),
        )
        self._main_engine.cancel_order(req, gateway)

    # ----------------------------------------------------------
    # 查询 — 返回内部类型
    # ----------------------------------------------------------

    def get_positions(self) -> list[Position]:
        """获取所有持仓（内部类型）"""
        if not self._main_engine:
            return []
        return [convert_position(p) for p in self._main_engine.get_all_positions()]

    def get_account_snapshot(self) -> Optional[PortfolioSnapshot]:
        """获取账户快照（内部类型）"""
        if not self._main_engine:
            return None
        accounts = self._main_engine.get_all_accounts()
        if not accounts:
            return None
        a = accounts[0]
        positions = self.get_positions()
        return PortfolioSnapshot(
            timestamp=datetime.now(),
            positions=positions,
            cash=a.balance - a.frozen,
            total_value=a.balance,
        )

    def get_active_orders(self) -> list[Order]:
        """获取活跃订单（内部类型）"""
        if not self._main_engine:
            return []
        return [convert_order(o) for o in self._main_engine.get_all_active_orders()]

    # ----------------------------------------------------------
    # 历史数据 — 返回内部类型
    # ----------------------------------------------------------

    def query_bars(self, symbol: str, exchange: str,
                   start: str, end: str,
                   interval: str = "d") -> list[Bar]:
        """
        查询历史 K 线

        Args:
            symbol: 合约代码
            exchange: 交易所
            start: 开始日期 "YYYY-MM-DD"
            end: 结束日期 "YYYY-MM-DD"
            interval: 周期 ("d", "1m", "1h")

        Returns:
            内部 Bar 列表
        """
        if not self._main_engine:
            return []

        interval_map = {
            "d": VnInterval.DAILY,
            "1m": VnInterval.MINUTE,
            "1h": VnInterval.HOUR,
        }
        from vnpy.trader.object import HistoryRequest as VnHistoryRequest
        import pandas as pd

        req = VnHistoryRequest(
            symbol=symbol,
            exchange=_to_vn_exchange(exchange),
            start=pd.Timestamp(start),
            end=pd.Timestamp(end),
            interval=interval_map.get(interval, VnInterval.DAILY),
        )
        vn_bars = self._main_engine.query_history(req, "CTP")
        return [convert_bar(b) for b in vn_bars]
