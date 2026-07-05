"""
基本面数据更新脚本

从 baostock 拉取财务报表数据，写入 DuckDB research.financials 表。

用法:
    python -m scripts.update_fundamentals                     # 更新沪深300全部股票
    python -m scripts.update_fundamentals --tickers 603005     # 更新指定股票
    python -m scripts.update_fundamentals --tickers 603005,600519  # 多只
    python -m scripts.update_fundamentals --year 2025 --quarter 4  # 指定报告期
"""
import sys
import argparse
import time
from datetime import date, datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.provider import DataProvider, HAS_BAOSTOCK
from data.storage import DataStorage

from loguru import logger


def _parse_baostock_financials(
    ticker: str,
    reports: dict[str, pd.DataFrame],
    year: int,
    quarter: int,
) -> pd.DataFrame:
    """
    将 baostock 财务报表合并为 financials 表记录。

    实际字段名 (baostock 0.9.x):
      profit:  code, pubDate, statDate, roeAvg, npMargin, gpMargin,
               netProfit, epsTTM, MBRevenue, totalShare, liqaShare
      growth:  code, pubDate, statDate, YOYEquity, YOYAsset, YOYNI, YOYEPSBasic, YOYPNI
      balance: code, pubDate, statDate, currentRatio, quickRatio, cashRatio,
               YOYLiability, liabilityToAsset, assetToEquity
    """
    profit = reports.get("profit")
    if profit is None or profit.empty:
        return pd.DataFrame()

    stat_date = profit["statDate"].iloc[0] if "statDate" in profit.columns else None
    if not stat_date:
        return pd.DataFrame()

    report_type = f"Q{quarter}" if quarter else "annual"

    def safe_val(df, col):
        if df is None or df.empty or col not in df.columns:
            return None
        try:
            return float(df[col].iloc[0])
        except (ValueError, TypeError):
            return None

    row = {
        "report_date": stat_date,
        "report_type": report_type,
        "revenue": safe_val(profit, "MBRevenue"),
        "net_profit": safe_val(profit, "netProfit"),
        "roe": safe_val(profit, "roeAvg"),
        "total_assets": None,  # not available from baostock financial APIs
        "equity": None,        # not available from baostock financial APIs
        "eps": safe_val(profit, "epsTTM"),
    }

    return pd.DataFrame([row])


def update_fundamentals(
    tickers: list[str] = None,
    year: int = None,
    quarter: int = None,
):
    """更新基本面数据"""
    if not HAS_BAOSTOCK:
        logger.error("baostock 未安装，无法获取财务报表")
        return

    if year is None:
        year = datetime.now().year
    if quarter is None:
        month = datetime.now().month
        quarter = (month - 1) // 3
        quarter = max(1, quarter)

    # 确定显示的报告期
    quarter_names = {1: "Q1(一季报)", 2: "Q2(中报)", 3: "Q3(三季报)", 4: "Q4(年报)"}
    q_name = quarter_names.get(quarter, f"Q{quarter}")

    logger.info(f"基本面数据更新 - {year}年 {q_name}")
    logger.info(f"股票数量: {len(tickers)}")

    # 获取股票列表
    if tickers is None:
        try:
            tickers = DataProvider.get_csi300_components()
            logger.info(f"使用沪深300成分股: {len(tickers)} 只")
        except Exception:
            logger.error("获取成分股失败，请指定 --tickers")
            return

    storage = DataStorage()
    success = 0
    failed = []

    for i, ticker in enumerate(tickers):
        if (i + 1) % 10 == 0:
            logger.info(f"  进度: {i+1}/{len(tickers)} (成功: {success}, 失败: {len(failed)})")

        try:
            reports = DataProvider.get_stock_financial_reports(ticker, year, quarter)
            df = _parse_baostock_financials(ticker, reports, year, quarter)

            if not df.empty:
                storage.save_financials(ticker, df)
                logger.debug(f"  {ticker}: {df['report_date'].iloc[0]}")
                success += 1
            else:
                logger.debug(f"  {ticker}: 无财务数据")
                failed.append((ticker, "无数据"))
        except Exception as e:
            failed.append((ticker, str(e)))
            logger.debug(f"  {ticker}: {e}")

        time.sleep(0.3)  # baostock 防限流

    logger.success(f"完成: 成功 {success}, 失败 {len(failed)}")
    if failed:
        logger.warning(f"失败明细 (前10):")
        for t, e in failed[:10]:
            logger.warning(f"  {t}: {e}")

    # 统计
    count = storage.conn.execute(
        "SELECT COUNT(*) FROM research.financials"
    ).fetchone()[0]
    logger.info(f"research.financials 表总计: {count} 条")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="更新基本面数据")
    parser.add_argument("--tickers", default=None, help="股票代码 (逗号分隔)")
    parser.add_argument("--year", type=int, default=None, help="财报年份")
    parser.add_argument("--quarter", type=int, default=None, help="季度 (1-4)")
    args = parser.parse_args()

    tickers = args.tickers.split(",") if args.tickers else None
    update_fundamentals(tickers, args.year, args.quarter)
