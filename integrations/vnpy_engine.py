"""
vnpy 集成 — 执行层引擎

直接使用 vnpy 的：
  - MainEngine 交易引擎
  - Gateway 系统 (CTP, IB, XTP 等)
  - AlphaStrategy 多资产策略框架
  - BarGenerator / ArrayManager 工具
  - 事件驱动架构

不重复实现 vnpy 已有的功能。

适配器:
  VnpyExecutionAdapter — 实现 ExecutionEngine 接口
  VnpyEngine — 旧接口，保留向后兼容
"""
import warnings
import sys
from pathlib import Path
from typing import Optional

import pandas as pd

from loguru import logger

from integrations.base import ExecutionEngine

# 将 vnpy 源码加入 path
VNPY_ROOT = Path(__file__).parent.parent.parent / "_reference" / "vnpy"
if str(VNPY_ROOT) not in sys.path:
    sys.path.insert(0, str(VNPY_ROOT))

try:
    from vnpy.event import EventEngine, Event, EVENT_TIMER
    from vnpy.trader.engine import MainEngine
    from vnpy.trader.object import (
        TickData, BarData, OrderData, TradeData,
        PositionData, AccountData, ContractData,
        SubscribeRequest, OrderRequest, CancelRequest, HistoryRequest,
    )
    from vnpy.trader.constant import (
        Direction, Offset, Status, OrderType, Exchange, Interval,
    )
    from vnpy.trader.utility import BarGenerator, ArrayManager, round_to
    HAS_VNPY = True
except ImportError as e:
    HAS_VNPY = False
    logger.warning(f"vnpy 导入失败: {e}")


class VnpyExecutionAdapter(ExecutionEngine):
    """
    vnpy 执行适配器 — 实现统一的 ExecutionEngine 接口

    用法:
        adapter = VnpyExecutionAdapter()
        adapter.start()
        order_id = adapter.send_order("000300", "LONG", 4000, 100)
    """

    def __init__(self):
        if not HAS_VNPY:
            raise ImportError("vnpy 未正确安装")
        self._engine = VnpyEngine()

    def start(self):
        self._engine.start()

    def stop(self):
        self._engine.stop()

    def send_order(self, symbol: str, direction: str,
                   price: float, volume: float,
                   order_type: str = "LIMIT") -> str:
        return self._engine.send_order(symbol, "SSE", direction, price, volume, order_type)

    def cancel_order(self, order_id: str) -> bool:
        try:
            self._engine.cancel_order(order_id, "", "")
            return True
        except Exception:
            return False

    def get_positions(self) -> list[dict]:
        return self._engine.get_positions()

    def get_accounts(self) -> list[dict]:
        return self._engine.get_accounts()


class VnpyEngine:
    """
    vnpy 执行引擎

    提供：
    1. 券商连接 (Gateway)
    2. 订单管理
    3. 持仓查询
    4. Alpha 策略框架
    5. 数据订阅

    已弃用: 请使用 VnpyExecutionAdapter 替代。
    """

    def __init__(self):
        warnings.warn(
            "VnpyEngine 已弃用，请使用 VnpyExecutionAdapter（实现统一的 ExecutionEngine 接口）",
            DeprecationWarning, stacklevel=2,
        )
        if not HAS_VNPY:
            raise ImportError("vnpy 未正确安装")

        self.event_engine = None
        self.main_engine = None
        self._connected = False

    def start(self):
        """启动引擎"""
        self.event_engine = EventEngine()
        self.main_engine = MainEngine(self.event_engine)
        logger.success("vnpy 引擎启动")

    def stop(self):
        """停止引擎"""
        if self.main_engine:
            self.main_engine.close()
            self._connected = False
            logger.info("vnpy 引擎已停止")

    # ============================================================
    # Gateway 连接
    # ============================================================

    def connect_ctp(self, setting: dict):
        """
        连接 CTP (国内期货)

        Args:
            setting: CTP 连接参数
                {
                    "用户名": "...",
                    "密码": "...",
                    "经纪商代码": "...",
                    "交易服务器": "...",
                    "行情服务器": "...",
                    "产品名称": "...",
                    "授权编码": "...",
                    "产品信息": ""
                }
        """
        try:
            from vnpy_ctp import CtpGateway
            self.main_engine.add_gateway(CtpGateway)
            self.main_engine.connect(setting, "CTP")
            self._connected = True
            logger.success("CTP 连接成功")
        except ImportError:
            logger.error("vnpy_ctp 未安装。pip install vnpy_ctp")

    def connect_ib(self, setting: dict):
        """
        连接 Interactive Brokers

        Args:
            setting: IB 连接参数
                {
                    "TWS地址": "127.0.0.1",
                    "TWS端口": 7497,
                    "客户号": 1,
                }
        """
        try:
            from vnpy_ib import IbGateway
            self.main_engine.add_gateway(IbGateway)
            self.main_engine.connect(setting, "IB")
            self._connected = True
            logger.success("IB 连接成功")
        except ImportError:
            logger.error("vnpy_ib 未安装。pip install vnpy_ib")

    def connect_xtp(self, setting: dict):
        """
        连接 XTP (国内股票/期权)

        Args:
            setting: XTP 连接参数
        """
        try:
            from vnpy_xtp import XtpGateway
            self.main_engine.add_gateway(XtpGateway)
            self.main_engine.connect(setting, "XTP")
            self._connected = True
            logger.success("XTP 连接成功")
        except ImportError:
            logger.error("vnpy_xtp 未安装。pip install vnpy_xtp")

    # ============================================================
    # 订单管理
    # ============================================================

    def send_order(self, symbol: str, exchange: str,
                   direction: str, price: float, volume: float,
                   order_type: str = "LIMIT") -> str:
        """
        发送订单

        Args:
            symbol: 合约代码
            exchange: 交易所 ("SSE", "SZSE", "CFFEX", "SHFE", ...)
            direction: 方向 ("LONG", "SHORT")
            price: 价格
            volume: 数量
            order_type: 订单类型 ("LIMIT", "MARKET")

        Returns:
            订单 ID
        """
        if not self._connected:
            raise RuntimeError("未连接到券商")

        exchange_map = {
            "SSE": Exchange.SSE,
            "SZSE": Exchange.SZSE,
            "CFFEX": Exchange.CFFEX,
            "SHFE": Exchange.SHFE,
            "CZCE": Exchange.CZCE,
            "DCE": Exchange.DCE,
            "INE": Exchange.INE,
            "GFEX": Exchange.GFEX,
        }

        req = OrderRequest(
            symbol=symbol,
            exchange=exchange_map.get(exchange, Exchange.SSE),
            direction=Direction.LONG if direction == "LONG" else Direction.SHORT,
            type=OrderType.LIMIT if order_type == "LIMIT" else OrderType.MARKET,
            price=price,
            volume=volume,
            offset=Offset.OPEN,
        )

        return self.main_engine.send_order(req, "CTP")

    def cancel_order(self, orderid: str, symbol: str, exchange: str):
        """撤单"""
        if not self._connected:
            return

        exchange_map = {
            "SSE": Exchange.SSE,
            "SZSE": Exchange.SZSE,
        }

        req = CancelRequest(
            orderid=orderid,
            symbol=symbol,
            exchange=exchange_map.get(exchange, Exchange.SSE),
        )
        self.main_engine.cancel_order(req, "CTP")

    # ============================================================
    # 查询
    # ============================================================

    def get_positions(self) -> list[dict]:
        """获取所有持仓"""
        if not self.main_engine:
            return []
        positions = self.main_engine.get_all_positions()
        return [
            {
                "symbol": p.symbol,
                "exchange": p.exchange.value,
                "direction": p.direction.value,
                "volume": p.volume,
                "frozen": p.frozen,
            }
            for p in positions
        ]

    def get_accounts(self) -> list[dict]:
        """获取账户信息"""
        if not self.main_engine:
            return []
        accounts = self.main_engine.get_all_accounts()
        return [
            {
                "accountid": a.accountid,
                "balance": a.balance,
                "frozen": a.frozen,
                "available": a.balance - a.frozen,
            }
            for a in accounts
        ]

    def get_active_orders(self) -> list[dict]:
        """获取活跃订单"""
        if not self.main_engine:
            return []
        orders = self.main_engine.get_all_active_orders()
        return [
            {
                "orderid": o.orderid,
                "symbol": o.symbol,
                "direction": o.direction.value,
                "price": o.price,
                "volume": o.volume,
                "traded": o.traded,
                "status": o.status.value,
            }
            for o in orders
        ]

    # ============================================================
    # 历史数据
    # ============================================================

    def query_history(self, symbol: str, exchange: str,
                      start: str, end: str,
                      interval: str = "d") -> list:
        """
        查询历史数据

        Args:
            symbol: 合约代码
            exchange: 交易所
            start: 开始日期
            end: 结束日期
            interval: 周期 ("d", "1m", "1h")

        Returns:
            BarData 列表
        """
        if not self.main_engine:
            return []

        interval_map = {
            "d": Interval.DAILY,
            "1m": Interval.MINUTE,
            "1h": Interval.HOUR,
        }

        req = HistoryRequest(
            symbol=symbol,
            exchange=Exchange.SSE,
            start=pd.Timestamp(start),
            end=pd.Timestamp(end),
            interval=interval_map.get(interval, Interval.DAILY),
        )

        return self.main_engine.query_history(req, "CTP")

    # ============================================================
    # 工具方法
    # ============================================================

    @staticmethod
    def create_bar_generator(on_bar_callback, window: int = 0,
                             on_window_bar=None):
        """创建 BarGenerator"""
        if not HAS_VNPY:
            raise ImportError("vnpy 未安装")
        return BarGenerator(on_bar_callback, window, on_window_bar)

    @staticmethod
    def create_array_manager(size: int = 100):
        """创建 ArrayManager"""
        if not HAS_VNPY:
            raise ImportError("vnpy 未安装")
        return ArrayManager(size)
