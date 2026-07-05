"""
新闻采集器

信源分级：
  Tier 1: SEC EDGAR、巨潮资讯、公司IR
  Tier 2: Reuters、Bloomberg、FT
  Tier 3: OpenBB、Yahoo Finance、Benzinga
  Tier 4: Reddit、Twitter/X、Hacker News

设计原则：
  - 可靠性 > 时效性 > 结构化程度 > 数量
  - 不追求新闻越多越好
  - 每个采集器返回标准化的 NewsSource
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from .schema import NewsSource, SourceTier

logger = logging.getLogger(__name__)


class NewsCollector:
    """
    新闻采集器基类

    所有采集器继承此类，实现 collect() 方法。
    返回标准化的 NewsSource 列表。
    """

    def __init__(self, name: str, tier: SourceTier):
        self.name = name
        self.tier = tier

    def collect(self, symbol: str = None,
                start_date: datetime = None,
                end_date: datetime = None,
                limit: int = 50) -> list[NewsSource]:
        """
        采集新闻

        Args:
            symbol: 股票代码（可选）
            start_date: 开始时间
            end_date: 结束时间
            limit: 最大条数

        Returns:
            NewsSource 列表
        """
        raise NotImplementedError


class OpenBBCollector(NewsCollector):
    """
    OpenBB 新闻采集器（Tier 3）

    通过 OpenBB SDK 获取新闻，适合个人开发者。
    """

    def __init__(self):
        super().__init__("OpenBB", SourceTier.TIER_3)
        self._obb = None

    def _get_obb(self):
        if self._obb is None:
            try:
                from openbb import obb
                self._obb = obb
            except ImportError:
                logger.warning("OpenBB 未安装")
                return None
        return self._obb

    def collect(self, symbol: str = None,
                start_date: datetime = None,
                end_date: datetime = None,
                limit: int = 50) -> list[NewsSource]:
        obb = self._get_obb()
        if obb is None:
            return []

        sources = []
        try:
            if symbol:
                result = obb.news.company(symbol=symbol, limit=limit)
            else:
                result = obb.news.world(limit=limit)

            for item in (result.to_df().to_dict("records") if hasattr(result, 'to_df') else []):
                sources.append(NewsSource(
                    url=item.get("url", ""),
                    source_name=item.get("source", "OpenBB"),
                    tier=self.tier,
                    title=item.get("title", ""),
                    published_at=datetime.now(),  # OpenBB 格式各异
                    content_snippet=item.get("text", "")[:200],
                    raw_id=item.get("id", item.get("url", "")),
                ))
        except Exception as e:
            logger.warning(f"OpenBB 采集失败: {e}")

        return sources[:limit]


class YFinanceCollector(NewsCollector):
    """
    Yahoo Finance 新闻采集器（Tier 3）

    通过 yfinance 获取新闻。
    """

    def __init__(self):
        super().__init__("Yahoo Finance", SourceTier.TIER_3)

    def collect(self, symbol: str = None,
                start_date: datetime = None,
                end_date: datetime = None,
                limit: int = 50) -> list[NewsSource]:
        if not symbol:
            return []

        sources = []
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            news = ticker.news or []

            for item in news[:limit]:
                content = item.get("content", {})
                sources.append(NewsSource(
                    url=content.get("canonicalUrl", {}).get("url", ""),
                    source_name=content.get("provider", {}).get("displayName", "Yahoo"),
                    tier=self.tier,
                    title=content.get("title", ""),
                    published_at=datetime.fromtimestamp(
                        content.get("pubDate", 0)
                    ) if content.get("pubDate") else datetime.now(),
                    content_snippet=content.get("summary", "")[:200],
                    raw_id=content.get("id", ""),
                ))
        except Exception as e:
            logger.warning(f"Yahoo Finance 采集失败: {e}")

        return sources[:limit]


class AKShareCollector(NewsCollector):
    """
    AKShare 新闻采集器（Tier 3）

    通过 AKShare 获取 A 股新闻。
    - 个股新闻: ak.stock_news_em(symbol=ticker)
    - 市场要闻: ak.stock_info_global_em() (财联社快讯)
    """

    def __init__(self):
        super().__init__("AKShare", SourceTier.TIER_3)

    def collect(self, symbol: str = None,
                start_date: datetime = None,
                end_date: datetime = None,
                limit: int = 50) -> list[NewsSource]:
        sources = []
        try:
            import akshare as ak

            if symbol:
                # 个股新闻 — stock_news_em 使用东方财富个股新闻
                df = ak.stock_news_em(symbol=symbol)
                if df is not None and not df.empty:
                    for _, row in df.head(limit).iterrows():
                        pub_date = row.get("发布时间", row.get("date", ""))
                        if isinstance(pub_date, str) and pub_date:
                            try:
                                pub_date = datetime.fromisoformat(pub_date)
                            except ValueError:
                                pub_date = datetime.now()
                        else:
                            pub_date = datetime.now()

                        sources.append(NewsSource(
                            url=str(row.get("文章链接", row.get("url", ""))),
                            source_name="东方财富",
                            tier=self.tier,
                            title=str(row.get("新闻标题", row.get("title", ""))),
                            published_at=pub_date,
                            content_snippet=str(row.get("新闻内容", row.get("content", "")))[:200],
                            raw_id=str(row.get("seq", row.get("seq", ""))),
                        ))
            else:
                # 市场要闻 — 财联社快讯
                df = ak.stock_info_global_em()
                if df is not None and not df.empty:
                    for _, row in df.head(limit).iterrows():
                        sources.append(NewsSource(
                            url="",
                            source_name="财联社",
                            tier=self.tier,
                            title=str(row.get("标题", row.get("content", ""))),
                            published_at=datetime.now(),
                            content_snippet=str(row.get("内容", ""))[:200],
                            raw_id=str(row.get("序号", "")),
                        ))
        except Exception as e:
            logger.warning(f"AKShare 采集失败: {e}")

        return sources[:limit]


class CNInfoCollector(NewsCollector):
    """
    巨潮资讯采集器（Tier 1）

    A 股公告数据，一级信源。
    """

    def __init__(self):
        super().__init__("巨潮资讯", SourceTier.TIER_1)

    def collect(self, symbol: str = None,
                start_date: datetime = None,
                end_date: datetime = None,
                limit: int = 50) -> list[NewsSource]:
        # TODO: 接入巨潮资讯 API
        # http://www.cninfo.com.cn
        logger.info("巨潮资讯采集器待实现")
        return []


class SECEdgarCollector(NewsCollector):
    """
    SEC EDGAR 采集器（Tier 1）

    美股 SEC 文件，一级信源。
    """

    def __init__(self):
        super().__init__("SEC EDGAR", SourceTier.TIER_1)

    def collect(self, symbol: str = None,
                start_date: datetime = None,
                end_date: datetime = None,
                limit: int = 50) -> list[NewsSource]:
        # TODO: 接入 SEC EDGAR API
        # https://www.sec.gov/edgar
        logger.info("SEC EDGAR 采集器待实现")
        return []


# ============================================================
# 采集器注册表
# ============================================================

COLLECTORS = {
    "openbb": OpenBBCollector,
    "yahoo": YFinanceCollector,
    "akshare": AKShareCollector,
    "cninfo": CNInfoCollector,
    "sec_edgar": SECEdgarCollector,
}


def get_collector(name: str) -> NewsCollector:
    """获取采集器"""
    cls = COLLECTORS.get(name)
    if cls is None:
        raise ValueError(f"未知采集器: {name}，可用: {list(COLLECTORS.keys())}")
    return cls()


def get_all_collectors() -> dict[str, NewsCollector]:
    """获取所有采集器"""
    return {name: cls() for name, cls in COLLECTORS.items()}
