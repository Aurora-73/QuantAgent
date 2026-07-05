"""
数据更新脚本

用法：
    python -m scripts.update_data                    # 更新沪深300
    python -m scripts.update_data --universe csi500  # 更新中证500
    python -m scripts.update_data --tickers 600519,300750  # 更新指定股票
"""
import sys
import argparse
import time
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.provider import DataProvider
from data.storage import DataStorage
from data.cleaner import DataCleaner

from loguru import logger


def update_data(universe: str = "csi300",
                tickers: list[str] = None,
                start_date: str = "2020-01-01",
                end_date: str = None):
    """
    更新数据

    Args:
        universe: 股票池 (csi300 / csi500)
        tickers: 指定股票列表
        start_date: 开始日期
        end_date: 结束日期
    """
    end_date = end_date or date.today().isoformat()

    logger.info(f"{'='*60}")
    logger.info(f"  数据更新")
    logger.info(f"  股票池: {universe}")
    logger.info(f"  区间: {start_date} ~ {end_date}")
    logger.info(f"{'='*60}")

    storage = DataStorage()

    # 获取股票列表
    if tickers is None:
        if universe == "csi300":
            tickers = DataProvider.get_csi300_components()
        elif universe == "csi500":
            tickers = DataProvider.get_csi500_components()
        else:
            tickers = DataProvider.get_csi300_components()

    logger.info(f"股票数量: {len(tickers)}")

    # 更新指数
    logger.info("[1/3] 更新指数数据...")
    for index_code, index_name in [("000300", "沪深300"), ("000905", "中证500")]:
        try:
            df = DataProvider.get_index_daily(index_code, start_date, end_date)
            if not df.empty:
                storage.save_index_daily(index_code, df)
                logger.success(f"  {index_name}: {len(df)} 条")
        except Exception as e:
            logger.warning(f"  {index_name} 失败: {e}")

    # 更新个股
    logger.info(f"[2/3] 更新个股数据 ({len(tickers)} 只)...")
    success = 0
    failed = []

    for i, ticker in enumerate(tickers):
        if (i + 1) % 10 == 0:
            logger.info(f"  进度: {i+1}/{len(tickers)}")

        try:
            df = DataProvider.get_stock_daily(ticker, start_date, end_date)
            if not df.empty:
                df = DataCleaner.clean_ohlcv(df)
                storage.save_stock_daily(ticker, df)
                success += 1
        except Exception as e:
            failed.append((ticker, str(e)))

        time.sleep(0.3)  # 防限流

    logger.success(f"  成功: {success}")
    if failed:
        logger.error(f"  失败: {len(failed)}")
        for t, e in failed[:5]:
            logger.error(f"  {t}: {e}")

    # 统计
    logger.info("[3/3] 数据统计...")
    stats = storage.get_table_stats()
    for k, v in stats.items():
        logger.info(f"  {k}: {v}")

    logger.success(f"{'='*60}")
    logger.success(f"  数据更新完成!")
    logger.success(f"{'='*60}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="数据更新")
    parser.add_argument("--universe", default="csi300", help="股票池 (csi300/csi500)")
    parser.add_argument("--tickers", default=None, help="指定股票 (逗号分隔)")
    parser.add_argument("--start", default="2020-01-01", help="开始日期")
    parser.add_argument("--end", default=None, help="结束日期")
    args = parser.parse_args()

    tickers = args.tickers.split(",") if args.tickers else None
    update_data(args.universe, tickers, args.start, args.end)
