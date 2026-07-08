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

import json
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
from loguru import logger

try:
    import akshare as ak
    HAS_AKSHARE = True
except ImportError:
    HAS_AKSHARE = False

from data.provider import _no_proxy, _safe_float


# ============================================================
# 磁盘缓存 — 板块列表/成分股变化频率低（每日一次），适合 TTL 缓存
# ============================================================
_CACHE_DIR = Path("data/cache/sectors")
_CACHE_TTL = 86400  # 24 小


def _load_cache(key: str, ttl: int = _CACHE_TTL):
    """从磁盘加载缓存，过期返回 None。"""
    path = _CACHE_DIR / f"{key}.json"
    if not path.exists():
        return None
    age = time.time() - path.stat().st_mtime
    if age > ttl:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_cache(key: str, data):
    """保存数据到磁盘缓存。"""
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _CACHE_DIR / f"{key}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, default=str), encoding="utf-8")


class SectorData:
    """行业/概念板块数据获取与构建"""

    # 缓存：板块名 → [ticker, ...]
    _board_cache: dict[str, list[str]] = {}

    @staticmethod
    def get_industry_list() -> list[dict]:
        """
        获取申万行业列表（24h 磁盘缓存）

        Returns:
            [{"name": "半导体", "code": "BK1036", "stock_count": 120}, ...]
        """
        cached = _load_cache("industry_list")
        if cached is not None:
            logger.debug(f"行业列表缓存命中: {len(cached)} 个行业")
            return cached

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
            _save_cache("industry_list", results)
            return results
        except Exception as e:
            logger.error(f"获取行业列表失败: {e}")
            return []

    @staticmethod
    def get_concept_list() -> list[dict]:
        """
        获取东方财富概念板块列表（24h 磁盘缓存）

        Returns:
            [{"name": "半导体", "code": "BK1036", "stock_count": 280}, ...]
        """
        cached = _load_cache("concept_list")
        if cached is not None:
            logger.debug(f"概念板块列表缓存命中: {len(cached)} 个板块")
            return cached

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
            _save_cache("concept_list", results)
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
        获取板块成分股列表（24h 磁盘缓存 + 内存缓存）

        Args:
            board_name: 板块名称，如 "半导体"
            board_type: "industry" 或 "concept"

        Returns:
            [{"ticker": "688981", "name": "中芯国际", "code": "688981"}, ...]
        """
        cache_key_str = f"stocks_{board_type}_{board_name}"
        mem_key = f"{board_type}:{board_name}"

        # 1. 内存缓存
        if mem_key in SectorData._board_cache:
            tickers = SectorData._board_cache[mem_key]
            return [{"ticker": t, "name": ""} for t in tickers]

        # 2. 磁盘缓存
        cached = _load_cache(cache_key_str)
        if cached is not None:
            SectorData._board_cache[mem_key] = [r["ticker"] for r in cached]
            logger.debug(f"板块成分股缓存命中: {board_name} ({len(cached)} 只)")
            return cached

        if not HAS_AKSHARE:
            logger.warning("AKShare 未安装")
            return []

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

            # 双层缓存
            SectorData._board_cache[mem_key] = [r["ticker"] for r in results]
            _save_cache(cache_key_str, results)
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

        优先从 DuckDB 本地数据构建（毫秒级），仅在本地无数据时回退到 API。

        Args:
            board_name: 板块名称
            board_type: "industry" 或 "concept"
            start_date: 起始日期
            end_date: 结束日期 (默认今天)

        Returns:
            DataFrame with columns: date, open, high, low, close, volume, stock_count
        """
        if end_date is None:
            end_date = date.today().strftime("%Y-%m-%d")

        # 获取成分股
        stocks = SectorData.get_board_stocks(board_name, board_type)
        if not stocks:
            logger.warning(f"板块 {board_name} 无成分股数据")
            return pd.DataFrame()

        tickers = [s["ticker"] for s in stocks]
        logger.info(f"构建 {board_name} 板块指数: {len(tickers)} 只股票, {start_date} → {end_date}")

        # 优先从 DuckDB 批量查询（单次 SQL 替代 N 次 API 调用）
        all_closes, all_opens, all_highs, all_lows, all_volumes = \
            SectorData._load_board_data_from_db(tickers, start_date, end_date)

        # 如果 DuckDB 无数据，回退到 API
        if not all_closes:
            all_closes, all_opens, all_highs, all_lows, all_volumes = \
                SectorData._load_board_data_from_api(tickers, start_date, end_date)

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

    @staticmethod
    def _load_board_data_from_db(tickers: list[str], start_date: str, end_date: str):
        """从 DuckDB 批量查询所有成分股日线（单次 SQL，毫秒级）。"""
        all_closes, all_opens, all_highs, all_lows, all_volumes = {}, {}, {}, {}, {}
        try:
            from data.storage import DataStorage
            storage = DataStorage()
            # 单次查询所有 ticker 的数据
            placeholders = ",".join(["?"] * len(tickers))
            query = f"""
                SELECT ticker, date, open, high, low, close, volume
                FROM stock_daily
                WHERE ticker IN ({placeholders})
                  AND date >= ? AND date <= ?
                ORDER BY ticker, date
            """
            df = storage.conn.execute(
                query, [*tickers, start_date, end_date]
            ).fetchdf()
            storage.close()

            if df.empty:
                return all_closes, all_opens, all_highs, all_lows, all_volumes

            df["date"] = pd.to_datetime(df["date"])
            for ticker, group in df.groupby("ticker"):
                group = group.set_index("date")
                all_closes[ticker] = group["close"]
                all_opens[ticker] = group["open"]
                all_highs[ticker] = group["high"]
                all_lows[ticker] = group["low"]
                all_volumes[ticker] = group["volume"]

            logger.info(f"DuckDB 批量查询: {len(all_closes)}/{len(tickers)} 只股票有数据")
        except Exception as e:
            logger.debug(f"DuckDB 查询失败，将回退到 API: {e}")
        return all_closes, all_opens, all_highs, all_lows, all_volumes

    @staticmethod
    def _load_board_data_from_api(tickers: list[str], start_date: str, end_date: str):
        """从 API 逐只拉取日线（回退方案，有限流等待）。"""
        from data.provider import DataProvider

        all_closes, all_opens, all_highs, all_lows, all_volumes = {}, {}, {}, {}, {}
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
        return all_closes, all_opens, all_highs, all_lows, all_volumes


# ============================================================
# 快捷函数
# ============================================================

def get_semiconductor_stocks() -> list[dict]:
    """快捷获取半导体板块成分股"""
    return SectorData.get_board_stocks("半导体", board_type="concept")


def get_semiconductor_index(start_date: str = "2024-01-01") -> pd.DataFrame:
    """快捷获取半导体板块等权指数"""
    return SectorData.build_board_index("半导体", board_type="concept", start_date=start_date)
