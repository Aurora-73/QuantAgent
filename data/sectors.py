"""
行业/概念板块数据模块

提供申万行业分类和东方财富概念板块的完整数据能力：
  - 板块列表查询
  - 板块成分股获取
  - 板块等权指数构建

所有 AKShare 调用使用 _no_proxy 绕过代理。

Usage:
    from data.sectors import SectorData
    stocks = SectorData.get_board_stocks("半导体", board_type="concept")
    index_df = SectorData.build_board_index("半导体", board_type="concept")
"""
from __future__ import annotations

import time
from datetime import date, datetime, timedelta
from typing import Optional

import pandas as pd
from loguru import logger

try:
    import akshare as ak
    HAS_AKSHARE = True
except ImportError:
    HAS_AKSHARE = False

from data.provider import _no_proxy, _safe_float


class SectorData:
    """行业/概念板块数据获取与构建"""

    # 缓存：板块名 → [ticker, ...]
    _board_cache: dict[str, list[str]] = {}

    @staticmethod
    def get_industry_list() -> list[dict]:
        """
        获取申万行业列表

        Returns:
            [{"name": "半导体", "code": "BK1036", "stock_count": 120}, ...]
        """
        if not HAS_AKSHARE:
            logger.warning("AKShare 未安装")
            return []
        try:
            with _no_proxy():
                df = ak.stock_board_industry_name_em()
            if df.empty:
                return []
            # 标准化列名
            results = []
            for _, row in df.iterrows():
                results.append({
                    "name": str(row.get("板块名称", row.iloc[0] if len(df.columns) > 0 else "")),
                    "code": str(row.get("板块代码", row.iloc[1] if len(df.columns) > 1 else "")),
                    "stock_count": int(row.get("成分股数量", row.iloc[3] if len(df.columns) > 3 else 0)),
                    "pct_change": _safe_float(row.get("涨跌幅", row.iloc[4] if len(df.columns) > 4 else None)),
                })
            logger.info(f"获取申万行业列表: {len(results)} 个行业")
            return results
        except Exception as e:
            logger.error(f"获取行业列表失败: {e}")
            return []

    @staticmethod
    def get_concept_list() -> list[dict]:
        """
        获取东方财富概念板块列表

        Returns:
            [{"name": "半导体", "code": "BK1036", "stock_count": 280}, ...]
        """
        if not HAS_AKSHARE:
            logger.warning("AKShare 未安装")
            return []
        try:
            with _no_proxy():
                df = ak.stock_board_concept_name_em()
            if df.empty:
                return []
            results = []
            for _, row in df.iterrows():
                name = str(row.get("板块名称", row.iloc[0] if len(df.columns) > 0 else ""))
                results.append({
                    "name": name,
                    "code": str(row.get("板块代码", row.iloc[1] if len(df.columns) > 1 else "")),
                    "stock_count": int(row.get("成分股数量", row.iloc[3] if len(df.columns) > 3 else 0)),
                    "pct_change": _safe_float(row.get("涨跌幅", row.iloc[4] if len(df.columns) > 4 else None)),
                })
            logger.info(f"获取概念板块列表: {len(results)} 个板块")
            return results
        except Exception as e:
            logger.error(f"获取概念板块列表失败: {e}")
            return []

    @staticmethod
    def search_board(keyword: str, board_type: str = "concept") -> list[dict]:
        """
        按关键词搜索板块

        Args:
            keyword: 搜索关键词，如 "半导体"、"AI"
            board_type: "industry" (申万行业) 或 "concept" (概念板块)

        Returns:
            匹配的板块列表
        """
        if board_type == "industry":
            all_boards = SectorData.get_industry_list()
        else:
            all_boards = SectorData.get_concept_list()

        keyword_lower = keyword.lower()
        matches = [
            b for b in all_boards
            if keyword_lower in b["name"].lower()
        ]
        logger.info(f"搜索 '{keyword}' ({board_type}): 找到 {len(matches)} 个板块")
        return matches

    @staticmethod
    def get_board_stocks(board_name: str, board_type: str = "concept") -> list[dict]:
        """
        获取板块成分股列表

        Args:
            board_name: 板块名称，如 "半导体"
            board_type: "industry" 或 "concept"

        Returns:
            [{"ticker": "688981", "name": "中芯国际", "code": "688981"}, ...]
        """
        if not HAS_AKSHARE:
            logger.warning("AKShare 未安装")
            return []

        cache_key = f"{board_type}:{board_name}"
        try:
            with _no_proxy():
                if board_type == "industry":
                    df = ak.stock_board_industry_cons_em(symbol=board_name)
                else:
                    df = ak.stock_board_concept_cons_em(symbol=board_name)

            if df.empty:
                return []

            results = []
            for _, row in df.iterrows():
                # AKShare 返回列名可能因版本不同而异
                code = str(row.get("代码", row.iloc[0] if len(df.columns) > 0 else ""))
                name = str(row.get("名称", row.iloc[1] if len(df.columns) > 1 else ""))
                if code:
                    results.append({
                        "ticker": code,
                        "name": name,
                    })

            # 缓存
            SectorData._board_cache[cache_key] = [r["ticker"] for r in results]
            logger.info(f"获取板块 {board_name} ({board_type}): {len(results)} 只成分股")
            return results
        except Exception as e:
            logger.error(f"获取板块成分股失败 ({board_name}, {board_type}): {e}")
            return []

    @staticmethod
    def build_board_index(
        board_name: str,
        board_type: str = "concept",
        start_date: str = "2024-01-01",
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        从成分股日线数据构建板块等权指数

        使用简单等权平均：index_value = mean(all_stocks_close_for_that_day)

        Args:
            board_name: 板块名称
            board_type: "industry" 或 "concept"
            start_date: 起始日期
            end_date: 结束日期 (默认今天)

        Returns:
            DataFrame with columns: date, open, high, low, close, volume, stock_count
        """
        from data.provider import DataProvider

        if end_date is None:
            end_date = date.today().strftime("%Y-%m-%d")

        # 获取成分股
        stocks = SectorData.get_board_stocks(board_name, board_type)
        if not stocks:
            logger.warning(f"板块 {board_name} 无成分股数据")
            return pd.DataFrame()

        tickers = [s["ticker"] for s in stocks]
        logger.info(f"构建 {board_name} 板块指数: {len(tickers)} 只股票, {start_date} → {end_date}")

        # 批量拉取日线
        all_closes = {}
        all_opens = {}
        all_highs = {}
        all_lows = {}
        all_volumes = {}

        for i, ticker in enumerate(tickers):
            try:
                df = DataProvider.get_stock_daily(ticker, start_date, end_date)
                if not df.empty:
                    all_closes[ticker] = df["close"]
                    if "open" in df.columns:
                        all_opens[ticker] = df["open"]
                    if "high" in df.columns:
                        all_highs[ticker] = df["high"]
                    if "low" in df.columns:
                        all_lows[ticker] = df["low"]
                    if "volume" in df.columns:
                        all_volumes[ticker] = df["volume"]
            except Exception as e:
                logger.warning(f"获取 {ticker} 数据失败: {e}")
            if i > 0 and i % 10 == 0:
                time.sleep(0.5)  # 限流

        if not all_closes:
            return pd.DataFrame()

        # 构建等权指数
        close_df = pd.DataFrame(all_closes).sort_index()
        index_df = pd.DataFrame(index=close_df.index)
        index_df["close"] = close_df.mean(axis=1)
        index_df["stock_count"] = close_df.notna().sum(axis=1)

        if all_opens:
            open_df = pd.DataFrame(all_opens).sort_index()
            index_df["open"] = open_df.mean(axis=1)
        if all_highs:
            high_df = pd.DataFrame(all_highs).sort_index()
            index_df["high"] = high_df.mean(axis=1)
        if all_lows:
            low_df = pd.DataFrame(all_lows).sort_index()
            index_df["low"] = low_df.mean(axis=1)
        if all_volumes:
            vol_df = pd.DataFrame(all_volumes).sort_index()
            index_df["volume"] = vol_df.sum(axis=1)

        index_df["pct_change"] = index_df["close"].pct_change() * 100
        index_df.index.name = "date"

        logger.info(f"板块指数构建完成: {len(index_df)} 个交易日")
        return index_df


# ============================================================
# 快捷函数
# ============================================================

def get_semiconductor_stocks() -> list[dict]:
    """快捷获取半导体板块成分股"""
    return SectorData.get_board_stocks("半导体", board_type="concept")


def get_semiconductor_index(start_date: str = "2024-01-01") -> pd.DataFrame:
    """快捷获取半导体板块等权指数"""
    return SectorData.build_board_index("半导体", board_type="concept", start_date=start_date)
