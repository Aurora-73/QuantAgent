"""
交易日历模块 — A 股交易日判断。

数据源优先级:
  1. AKShare tool_trade_date_hist_sina()（主源，官方交易日历）
  2. DuckDB 缓存表 trading_calendar（次源，refresh 后持久化）
  3. 硬编码节假日（最终回退，标注 approximate）

Usage:
    from data.trading_calendar import TradingCalendar

    cal = TradingCalendar()
    cal.is_trading_day(date(2026, 7, 9))      # True/False
    cal.last_trading_day(date(2026, 7, 9))     # 最近交易日
    cal.next_trading_day(date(2026, 7, 9))     # 下一交易日
    cal.trading_days_between(start, end)        # 区间内交易日列表
    cal.refresh()                               # 从 AKShare 刷新缓存
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

import pandas as pd
from loguru import logger


# 最终回退：硬编码节假日（从 scheduler.py 迁移，标注 approximate）
# 仅在 AKShare 不可用且 DuckDB 缓存为空时使用
_FALLBACK_HOLIDAYS = {
    # 2026 (approximate)
    "2026-01-01", "2026-01-02",   # New Year
    "2026-02-16", "2026-02-17", "2026-02-18", "2026-02-19", "2026-02-20",  # Spring Festival
    "2026-04-06",                 # Qingming
    "2026-05-01", "2026-05-04", "2026-05-05",  # Labor Day
    "2026-06-22",                 # Dragon Boat
    "2026-09-28",                 # Mid-Autumn
    "2026-10-01", "2026-10-02", "2026-10-05", "2026-10-06", "2026-10-07",  # National Day
}


class TradingCalendar:
    """A 股交易日历，带多级回退。"""

    def __init__(self, storage=None):
        """
        Args:
            storage: DataStorage 实例（共享 DuckDB 连接，避免独占锁冲突）。
                     None 时创建独立实例。
        """
        if storage is not None:
            self.storage = storage
            self._owns_storage = False
        else:
            from data.storage import DataStorage
            self.storage = DataStorage()
            self._owns_storage = True

        self._trading_days: Optional[set[date]] = None
        self._sorted_days: Optional[list[date]] = None
        self._ensure_table()

    def _ensure_table(self):
        """创建缓存表（幂等）"""
        self.storage.conn.execute("""
            CREATE TABLE IF NOT EXISTS trading_calendar (
                trade_date DATE PRIMARY KEY
            )
        """)

    def _load_trading_days(self) -> set[date]:
        """加载交易日集合，优先 DuckDB 缓存，失败时尝试 AKShare，最终回退硬编码"""
        if self._trading_days is not None:
            return self._trading_days

        # 1. 尝试从 DuckDB 缓存加载
        try:
            df = self.storage.conn.execute(
                "SELECT trade_date FROM trading_calendar ORDER BY trade_date"
            ).fetchdf()
            if not df.empty:
                days = set(df["trade_date"].dt.date)
                self._trading_days = days
                self._sorted_days = sorted(days)
                logger.debug(f"交易日历从缓存加载: {len(days)} 天")
                return days
        except Exception as e:
            logger.debug(f"从 DuckDB 加载交易日历失败: {e}")

        # 2. 尝试从 AKShare 刷新
        try:
            self.refresh()
            if self._trading_days is not None:
                return self._trading_days
        except Exception as e:
            logger.warning(f"AKShare 交易日历刷新失败: {e}")

        # 3. 最终回退：硬编码节假日
        logger.warning("交易日历使用硬编码回退（approximate），建议运行 refresh() 更新")
        today = date.today()
        days = set()
        d = today - timedelta(days=365)
        while d <= today + timedelta(days=365):
            if d.weekday() < 5 and d.isoformat() not in _FALLBACK_HOLIDAYS:
                days.add(d)
            d += timedelta(days=1)
        self._trading_days = days
        self._sorted_days = sorted(days)
        return days

    def refresh(self) -> int:
        """
        从 AKShare 拉取最新交易日历并缓存到 DuckDB。

        Returns:
            缓存的交易日数量
        """
        try:
            import akshare as ak
        except ImportError:
            logger.warning("akshare 未安装，无法刷新交易日历")
            return 0

        df = ak.tool_trade_date_hist_sina()
        if df.empty:
            logger.warning("AKShare 返回空交易日历")
            return 0

        # 写入 DuckDB 缓存（先删后插，trading_calendar 表无索引删除 bug 风险）
        df = df.copy()
        # 统一转为 date 对象（AKShare 可能返回 date 或 Timestamp，pd.to_datetime 统一处理）
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date

        self.storage.conn.execute("DELETE FROM trading_calendar")
        self.storage.conn.execute("""
            INSERT INTO trading_calendar (trade_date)
            SELECT trade_date FROM df
        """)

        days = set(df["trade_date"].tolist())
        self._trading_days = days
        self._sorted_days = sorted(days)
        logger.info(f"交易日历已刷新: {len(days)} 天 (范围 {self._sorted_days[0]} ~ {self._sorted_days[-1]})")
        return len(days)

    def is_trading_day(self, d: date = None) -> bool:
        """判断是否为交易日"""
        d = d or date.today()
        days = self._load_trading_days()
        return d in days

    def last_trading_day(self, d: date = None) -> Optional[date]:
        """获取 <= d 的最近交易日"""
        d = d or date.today()
        days = self._load_trading_days()
        if self._sorted_days is None:
            return None
        # 二分查找：找 <= d 的最大日期
        import bisect
        idx = bisect.bisect_right(self._sorted_days, d)
        if idx == 0:
            return None
        return self._sorted_days[idx - 1]

    def next_trading_day(self, d: date = None) -> Optional[date]:
        """获取 > d 的下一交易日"""
        d = d or date.today()
        days = self._load_trading_days()
        if self._sorted_days is None:
            return None
        import bisect
        idx = bisect.bisect_right(self._sorted_days, d)
        if idx >= len(self._sorted_days):
            return None
        return self._sorted_days[idx]

    def trading_days_between(self, start: date, end: date) -> list[date]:
        """获取 [start, end] 区间内的交易日列表"""
        days = self._load_trading_days()
        if self._sorted_days is None:
            return []
        import bisect
        lo = bisect.bisect_left(self._sorted_days, start)
        hi = bisect.bisect_right(self._sorted_days, end)
        return self._sorted_days[lo:hi]

    def close(self):
        """释放资源（仅当本实例拥有 storage 时关闭）"""
        if self._owns_storage and hasattr(self.storage, "close"):
            self.storage.close()


# 模块级单例（惰性初始化）
_singleton: Optional[TradingCalendar] = None


def get_trading_calendar() -> TradingCalendar:
    """获取模块级单例"""
    global _singleton
    if _singleton is None:
        _singleton = TradingCalendar()
    return _singleton


def is_trading_day(d: date = None) -> bool:
    """模块级便捷函数"""
    return get_trading_calendar().is_trading_day(d)
