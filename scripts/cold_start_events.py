"""
事件数据冷启动脚本

从 AKShare 采集市场新闻 + 个股新闻，直接写入 events 表（非 LLM 路径）。
不涉及因子计算、回测等耗 CPU 操作，可在 Windows 本机执行。

用法:
    python -m scripts.cold_start_events                          # 默认采集市场新闻
    python -m scripts.cold_start_events --tickers 600519,300750  # 指定个股
    python -m scripts.cold_start_events --days 3                 # 采集多天（模拟历史）
    python -m scripts.cold_start_events --max-market 20 --max-per-ticker 5
"""
import sys
import os
import argparse
import hashlib
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

# 采集新闻前清除代理（AKShare 为国内数据源，不需要代理）
for proxy_var in ["http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"]:
    os.environ.pop(proxy_var, None)

from data.provider import DataProvider
from data.storage import DataStorage
from news.aggregator import collect_all_news


def cold_start_events(
    tickers: list[str] = None,
    max_market: int = 20,
    max_per_ticker: int = 3,
    total_limit: int = 50,
    days: int = 1,
):
    """
    事件冷启动：采集新闻并写入 events 表

    Args:
        tickers: 个股代码列表（None 则只采集市场新闻）
        max_market: 市场新闻条数
        max_per_ticker: 每只股票条数
        total_limit: 返回总数上限
        days: 采集天数（模拟历史，每天采集一次）
    """
    logger.info(f"{'='*60}")
    logger.info(f"  事件冷启动")
    logger.info(f"  股票: {tickers or '仅市场新闻'}")
    logger.info(f"  天数: {days}")
    logger.info(f"{'='*60}")

    storage = DataStorage()

    # 如未指定 tickers，取 CSI300 前 10 只
    if tickers is None:
        try:
            all_tickers = DataProvider.get_csi300_components()
            tickers = all_tickers[:10]
            logger.info(f"使用 CSI300 前 10 只: {tickers}")
        except Exception as e:
            logger.warning(f"获取成分股失败，仅采集市场新闻: {e}")
            tickers = []

    total_saved = 0
    total_skipped = 0

    for day_offset in range(days):
        target_date = date.today() - timedelta(days=day_offset)
        date_str = target_date.isoformat()

        logger.info(f"[{day_offset+1}/{days}] 采集 {date_str} 的新闻...")

        try:
            news_sources = collect_all_news(
                tickers=tickers,
                max_market=max_market,
                max_per_ticker=max_per_ticker,
                total_limit=total_limit,
            )

            if not news_sources:
                logger.info(f"  {date_str} 无新闻")
                continue

            logger.info(f"  采集到 {len(news_sources)} 条新闻")

            saved = 0
            skipped = 0
            for s in news_sources:
                if not s.title or not s.title.strip():
                    skipped += 1
                    continue

                title_hash = hashlib.md5(s.title.encode("utf-8")).hexdigest()[:8]
                ts = getattr(s, "published_at", None)
                if ts is None:
                    ts = target_date
                if hasattr(ts, "isoformat"):
                    ts_str = ts.isoformat()
                else:
                    ts_str = str(ts)

                ticker_val = getattr(s, "symbol", "") or getattr(s, "ticker", "")
                source_val = getattr(s, "source_name", "akshare")

                event = {
                    "event_id": f"evt_{title_hash}",
                    "timestamp": ts_str,
                    "source": source_val,
                    "event_type": "news",
                    "ticker": ticker_val,
                    "company": "",
                    "detail": s.title,
                    "sentiment": None,
                    "impact_objects": [],
                    "time_window": None,
                    "confidence": 0.5,
                    "tradability": None,
                    "tags": ["news_cold_start"],
                }

                try:
                    storage.save_event(event)
                    saved += 1
                except Exception as e:
                    logger.debug(f"  保存失败: {e}")
                    skipped += 1

            logger.success(f"  {date_str}: 入库 {saved} 条, 跳过 {skipped} 条")
            total_saved += saved
            total_skipped += skipped

        except Exception as e:
            logger.error(f"  {date_str} 采集失败: {e}")

    logger.info(f"{'='*60}")
    logger.info(f"  冷启动完成")
    logger.info(f"  总入库: {total_saved} 条")
    logger.info(f"  总跳过: {total_skipped} 条")
    logger.info(f"{'='*60}")

    # 验证
    try:
        import duckdb
        conn = duckdb.connect("data/quant.duckdb")
        result = conn.execute("SELECT COUNT(*) FROM events").fetchone()
        logger.info(f"  events 表总计: {result[0]} 条")
        result = conn.execute(
            "SELECT COUNT(*) FROM events WHERE tags LIKE '%news_cold_start%'"
        ).fetchone()
        logger.info(f"  冷启动事件: {result[0]} 条")
        conn.close()
    except Exception as e:
        logger.warning(f"  验证失败: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="事件冷启动")
    parser.add_argument("--tickers", default=None, help="股票代码 (逗号分隔)")
    parser.add_argument("--max-market", type=int, default=20, help="市场新闻条数")
    parser.add_argument("--max-per-ticker", type=int, default=3, help="每只股票条数")
    parser.add_argument("--total-limit", type=int, default=50, help="总数上限")
    parser.add_argument("--days", type=int, default=1, help="采集天数")
    args = parser.parse_args()

    tickers = [t.strip().zfill(6) for t in args.tickers.split(",")] if args.tickers else None
    cold_start_events(
        tickers=tickers,
        max_market=args.max_market,
        max_per_ticker=args.max_per_ticker,
        total_limit=args.total_limit,
        days=args.days,
    )
