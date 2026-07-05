"""
新闻聚合器

职责：
  - 调用各个采集器收集新闻
  - 按 title 去重
  - 按时间倒序排序
  - 提供给 daily_research.py Step 3

用法：
    from news.aggregator import collect_market_news, collect_ticker_news

    market_news = collect_market_news(max_items=20)
    ticker_news = collect_ticker_news(["603005", "600519"], max_per_ticker=5)
"""
from datetime import datetime
from typing import Optional

from loguru import logger

from .collector import AKShareCollector
from .schema import NewsSource


def _deduplicate(sources: list[NewsSource]) -> list[NewsSource]:
    """按 title 去重（简单前缀匹配）"""
    seen_titles = set()
    result = []
    for s in sources:
        key = s.title.strip()[:40]
        if key and key not in seen_titles:
            seen_titles.add(key)
            result.append(s)
    return result


def collect_market_news(max_items: int = 20) -> list[NewsSource]:
    """
    收集市场级新闻（不使用 proxy）

    Returns:
        按发布时间倒序排列的新闻列表
    """
    collector = AKShareCollector()
    news = collector.collect(symbol=None, limit=max_items)
    news = _deduplicate(news)
    news.sort(key=lambda x: x.published_at, reverse=True)
    logger.info(f"市场新闻: {len(news)} 条")
    return news[:max_items]


def collect_ticker_news(
    tickers: list[str],
    max_per_ticker: int = 5,
    total_limit: int = 30,
) -> list[NewsSource]:
    """
    收集指定股票的新闻

    Args:
        tickers: 股票代码列表
        max_per_ticker: 每只股票最多采集条数
        total_limit: 返回总数上限

    Returns:
        按发布时间倒序排列的新闻列表
    """
    collector = AKShareCollector()
    all_news = []
    for ticker in tickers:
        try:
            news = collector.collect(symbol=ticker, limit=max_per_ticker)
            all_news.extend(news)
        except Exception as e:
            logger.debug(f"  {ticker} 新闻采集失败: {e}")

    all_news = _deduplicate(all_news)
    all_news.sort(key=lambda x: x.published_at, reverse=True)
    logger.info(f"个股新闻: {len(all_news)} 条 (来自 {len(tickers)} 只股票)")
    return all_news[:total_limit]


def collect_all_news(
    tickers: Optional[list[str]] = None,
    max_market: int = 10,
    max_per_ticker: int = 3,
    total_limit: int = 30,
) -> list[NewsSource]:
    """
    一站式采集：市场要闻 + 个股新闻

    Args:
        tickers: 股票代码列表（可选）
        max_market: 市场新闻条数
        max_per_ticker: 每只股票条数
        total_limit: 返回总数上限

    Returns:
        合并去重后的新闻列表
    """
    all_sources = collect_market_news(max_items=max_market)
    if tickers:
        ticker_news = collect_ticker_news(tickers, max_per_ticker, total_limit)
        all_sources.extend(ticker_news)

    all_sources = _deduplicate(all_sources)
    all_sources.sort(key=lambda x: x.published_at, reverse=True)
    return all_sources[:total_limit]
