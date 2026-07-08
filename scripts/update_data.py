"""
数据更新脚本

用法：
    python -m scripts.update_data                    # 更新沪深300（全量）
    python -m scripts.update_data --universe csi500  # 更新中证500
    python -m scripts.update_data --tickers 600519,300750  # 更新指定股票
    python -m scripts.update_data --incremental      # 增量更新（只拉缺失日期）
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


def update_market_data(target_date: date = None,
                       tickers: list[str] = None,
                       incremental: bool = True,
                       update_index: bool = True) -> dict:
    """
    独立的市场数据更新任务（不含因子/研究/日报）。

    这是 scheduler 和 daily_research 共享的纯数据更新入口。
    将数据更新与因子计算/新闻采集/日报生成解耦。

    Args:
        target_date: 目标日期（默认今天）
        tickers: 股票列表（None 则使用默认列表）
        incremental: True 时只拉 max(date)+1 到 target_date 的缺失数据；
                     False 时全量重拉并替换
        update_index: 是否更新指数数据

    Returns:
        {"tickers_updated": int, "rows_added": int, "skipped": list[str],
         "index_updated": bool}
    """
    target_date = target_date or date.today()
    target_str = target_date.isoformat()
    storage = DataStorage()

    result = {
        "tickers_updated": 0,
        "rows_added": 0,
        "skipped": [],
        "index_updated": False,
    }

    # 默认股票列表
    if tickers is None:
        try:
            tickers = DataProvider.get_csi300_components()[:20]
            logger.info(f"沪深300成分股(前20): {len(tickers)} 只")
        except Exception:
            tickers = ["000001", "000002", "600519", "300750", "002475"]
            logger.warning(f"使用默认股票列表: {tickers}")

    # ---- 指数更新 ----
    if update_index:
        for index_code, index_name in [("000300", "沪深300"), ("000905", "中证500")]:
            try:
                if incremental:
                    last = storage.get_last_date("index_daily", ticker=index_code)
                    if last is not None and last >= target_date:
                        logger.debug(f"  {index_name} 已是最新 ({last})，跳过")
                        continue
                    start = (last + timedelta(days=1)).isoformat() if last else "2020-01-01"
                else:
                    start = "2020-01-01"

                df = DataProvider.get_index_daily(index_code, start, target_str)
                if not df.empty:
                    if incremental and last is not None:
                        storage.append_index_daily(index_code, df)
                    else:
                        storage.save_index_daily(index_code, df)
                    logger.success(f"  {index_name}: +{len(df)} 条 ({start} ~ {target_str})")
                    result["index_updated"] = True
            except Exception as e:
                logger.warning(f"  {index_name} 更新失败: {e}")

    # ---- 个股更新 ----
    for i, ticker in enumerate(tickers):
        if (i + 1) % 10 == 0:
            logger.info(f"  进度: {i+1}/{len(tickers)}")

        try:
            if incremental:
                last = storage.get_last_date("stock_daily", ticker=ticker)
                if last is not None and last >= target_date:
                    result["skipped"].append(ticker)
                    continue
                start = (last + timedelta(days=1)).isoformat() if last else "2020-01-01"
            else:
                start = "2020-01-01"

            df = DataProvider.get_stock_daily(ticker, start, target_str)
            if df.empty:
                result["skipped"].append(ticker)
                continue

            df = DataCleaner.clean_ohlcv(df)

            if incremental and last is not None:
                storage.append_stock_daily(ticker, df)
            else:
                storage.save_stock_daily(ticker, df)

            result["tickers_updated"] += 1
            result["rows_added"] += len(df)
        except Exception as e:
            logger.warning(f"  {ticker} 更新失败: {e}")
            result["skipped"].append(ticker)

        time.sleep(0.3)  # 防限流

    logger.info(f"数据更新完成: 更新 {result['tickers_updated']} 只, "
                f"新增 {result['rows_added']} 行, 跳过 {len(result['skipped'])} 只")

    # 批量写入后刷新统计信息，使后续查询能利用 zone-map
    if result["tickers_updated"] > 0:
        storage.analyze("stock_daily")
        storage.analyze("raw.stock_daily")

    return result


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

    # 批量写入后刷新统计信息，使后续查询能利用 zone-map
    logger.info("  刷新 DuckDB 统计信息 (ANALYZE)...")
    storage.analyze()

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
    parser.add_argument("--incremental", action="store_true",
                       help="增量更新（只拉 max(date)+1 到今天的缺失数据）")
    args = parser.parse_args()

    tickers = [t.strip().zfill(6) for t in args.tickers.split(",")] if args.tickers else None

    if args.incremental:
        update_market_data(tickers=tickers, incremental=True)
    else:
        update_data(args.universe, tickers, args.start, args.end)
