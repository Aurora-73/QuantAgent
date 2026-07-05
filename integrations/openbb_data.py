"""
OpenBB 集成 — 数据入口

直接使用 OpenBB Platform SDK 的：
  - 行情数据 (equity.price.historical)
  - 新闻数据 (news.company, news.world)
  - 基本面数据 (equity.fundamental.*)
  - 宏观数据 (economy.*)

OpenBB 优势：
  - 统一接口访问 50+ 数据源
  - 内置数据标准化
  - 活跃的社区维护

适配器:
  OpenBBDataAdapter — 实现 DataProvider 接口
  OpenBBDataProvider — 旧接口，保留向后兼容
"""
import warnings
import sys
from pathlib import Path
from typing import Optional

import pandas as pd

from loguru import logger

from integrations.base import DataProvider

# 将 OpenBB 源码加入 path
OPENBB_ROOT = Path(__file__).parent.parent.parent / "_reference" / "OpenBB"
if str(OPENBB_ROOT) not in sys.path:
    sys.path.insert(0, str(OPENBB_ROOT))

try:
    from openbb import obb
    HAS_OPENBB = True
except ImportError as e:
    HAS_OPENBB = False
    logger.warning(f"OpenBB 导入失败: {e}")


class OpenBBDataAdapter(DataProvider):
    """
    OpenBB 数据适配器 — 实现统一的 DataProvider 接口

    用法:
        adapter = OpenBBDataAdapter()
        df = adapter.get_historical("AAPL", "2024-01-01", "2024-12-31")
    """

    def __init__(self, provider: str = "yfinance"):
        if not HAS_OPENBB:
            raise ImportError("OpenBB 未正确安装")
        self._provider = OpenBBDataProvider(provider)

    def get_historical(self, symbol: str,
                       start_date: str = None,
                       end_date: str = None,
                       interval: str = "1d") -> pd.DataFrame:
        return self._provider.get_historical(symbol, start_date, end_date, interval)

    def get_quote(self, symbol: str) -> dict:
        return self._provider.get_quote(symbol)

    def get_company_news(self, symbol: str, limit: int = 20) -> pd.DataFrame:
        return self._provider.get_company_news(symbol, limit)

    def search(self, query: str) -> pd.DataFrame:
        return self._provider.search(query)


class OpenBBDataProvider:
    """
    OpenBB 数据提供者

    提供：
    1. 行情数据 (A股、美股、港股)
    2. 新闻数据
    3. 基本面数据
    4. 宏观数据

    已弃用: 请使用 OpenBBDataAdapter 替代。
    """

    def __init__(self, provider: str = "yfinance"):
        warnings.warn(
            "OpenBBDataProvider 已弃用，请使用 OpenBBDataAdapter（实现统一的 DataProvider 接口）",
            DeprecationWarning, stacklevel=2,
        )
        """
        Args:
            provider: 默认数据源 ("yfinance", "fmp", "alpha_vantage")
        """
        if not HAS_OPENBB:
            raise ImportError("OpenBB 未正确安装")

        self.provider = provider

    # ============================================================
    # 行情数据
    # ============================================================

    def get_historical(self, symbol: str,
                       start_date: str = None,
                       end_date: str = None,
                       interval: str = "1d") -> pd.DataFrame:
        """
        获取历史行情

        Args:
            symbol: 股票代码 (如 "AAPL", "000001.SZ")
            start_date: 开始日期 "YYYY-MM-DD"
            end_date: 结束日期 "YYYY-MM-DD"
            interval: 周期 ("1d", "1h", "1m")

        Returns:
            DataFrame (date, open, high, low, close, volume)
        """
        result = obb.equity.price.historical(
            symbol=symbol,
            provider=self.provider,
            start_date=start_date,
            end_date=end_date,
            interval=interval,
        )
        return result.to_df() if hasattr(result, 'to_df') else pd.DataFrame()

    def get_quote(self, symbol: str) -> dict:
        """获取最新报价"""
        result = obb.equity.price.quote(
            symbol=symbol,
            provider=self.provider,
        )
        return result.to_dict() if hasattr(result, 'to_dict') else {}

    # ============================================================
    # 新闻数据
    # ============================================================

    def get_company_news(self, symbol: str,
                         limit: int = 20) -> pd.DataFrame:
        """
        获取公司新闻

        Args:
            symbol: 股票代码
            limit: 返回条数

        Returns:
            DataFrame 包含标题、内容、来源、日期
        """
        result = obb.news.company(
            symbol=symbol,
            provider=self.provider,
            limit=limit,
        )
        return result.to_df() if hasattr(result, 'to_df') else pd.DataFrame()

    def get_world_news(self, limit: int = 20,
                       topics: str = None) -> pd.DataFrame:
        """
        获取全球新闻

        Args:
            limit: 返回条数
            topics: 话题过滤

        Returns:
            DataFrame
        """
        result = obb.news.world(
            provider=self.provider,
            limit=limit,
        )
        return result.to_df() if hasattr(result, 'to_df') else pd.DataFrame()

    # ============================================================
    # 基本面数据
    # ============================================================

    def get_income(self, symbol: str,
                   period: str = "annual",
                   limit: int = 5) -> pd.DataFrame:
        """获取利润表"""
        result = obb.equity.fundamental.income(
            symbol=symbol,
            provider=self.provider,
            period=period,
            limit=limit,
        )
        return result.to_df() if hasattr(result, 'to_df') else pd.DataFrame()

    def get_balance(self, symbol: str,
                    period: str = "annual",
                    limit: int = 5) -> pd.DataFrame:
        """获取资产负债表"""
        result = obb.equity.fundamental.balance(
            symbol=symbol,
            provider=self.provider,
            period=period,
            limit=limit,
        )
        return result.to_df() if hasattr(result, 'to_df') else pd.DataFrame()

    def get_cashflow(self, symbol: str,
                     period: str = "annual",
                     limit: int = 5) -> pd.DataFrame:
        """获取现金流量表"""
        result = obb.equity.fundamental.cash(
            symbol=symbol,
            provider=self.provider,
            period=period,
            limit=limit,
        )
        return result.to_df() if hasattr(result, 'to_df') else pd.DataFrame()

    def get_metrics(self, symbol: str) -> dict:
        """获取关键指标"""
        result = obb.equity.fundamental.metrics(
            symbol=symbol,
            provider=self.provider,
        )
        return result.to_dict() if hasattr(result, 'to_dict') else {}

    def get_ratios(self, symbol: str) -> dict:
        """获取财务比率"""
        result = obb.equity.fundamental.ratios(
            symbol=symbol,
            provider=self.provider,
        )
        return result.to_dict() if hasattr(result, 'to_dict') else {}

    # ============================================================
    # 搜索
    # ============================================================

    def search(self, query: str) -> pd.DataFrame:
        """搜索股票"""
        result = obb.equity.search(query=query, provider=self.provider)
        return result.to_df() if hasattr(result, 'to_df') else pd.DataFrame()

    def get_profile(self, symbol: str) -> dict:
        """获取公司信息"""
        result = obb.equity.profile(symbol=symbol, provider=self.provider)
        return result.to_dict() if hasattr(result, 'to_dict') else {}
