"""
批量因子计算脚本

用法：
    python -m scripts.compute_factors --universe csi300
    python -m scripts.compute_factors --tickers 600519,300750,000001
    python -m scripts.compute_factors --universe csi300 --workers 4

对指定股票池批量计算全部 29 个注册因子，结果写入 research.factors 表。
"""
import sys
import argparse
import time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import date

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from loguru import logger

from data.provider import DataProvider
from data.storage import DataStorage
from data.cleaner import DataCleaner
from research.factors import FactorEngine


def compute_factors_for_ticker(ticker: str, params: dict = None) -> dict:
    """计算单只股票的全部因子，返回统计信息"""
    storage = DataStorage()
    engine = FactorEngine()

    try:
        df = storage.load_stock_daily(ticker)
        if df.empty:
            logger.warning(f"  {ticker}: 无本地数据，尝试从数据源获取...")
            df = DataProvider.get_stock_daily(ticker)
            if not df.empty:
                df = DataCleaner.clean_ohlcv(df)
                storage.save_stock_daily(ticker, df)

        if df.empty:
            return {"ticker": ticker, "status": "skip", "reason": "无数据", "factor_count": 0}

        # 合并基本面数据（如果有）
        try:
            fin_df = storage.load_financials(ticker)
            if not fin_df.empty:
                fin_df["report_date"] = pd.to_datetime(fin_df["report_date"])
                fin_cols = ["revenue", "net_profit", "roe", "eps"]
                fin_ff = fin_df[["report_date"] + fin_cols].set_index("report_date")
                daterange = pd.date_range(
                    start=min(fin_ff.index.min(), df.index.min()),
                    end=df.index.max(),
                    freq="D",
                )
                fin_ff = fin_ff.reindex(daterange).ffill()
                df = df.join(fin_ff, how="left")
        except Exception:
            pass

        df_with_factors = engine.compute_all(df, params=params)

        factor_names = engine.list_factors()
        storage.save_factors_batch(ticker, df_with_factors)

        saved = sum(1 for col in df_with_factors.columns if col in factor_names)

        return {
            "ticker": ticker,
            "status": "ok",
            "rows": len(df_with_factors),
            "factor_count": saved,
            "total_factors": len(factor_names),
        }
    except Exception as e:
        logger.error(f"  {ticker}: 失败 - {e}")
        return {"ticker": ticker, "status": "error", "reason": str(e), "factor_count": 0}


def main():
    parser = argparse.ArgumentParser(description="批量因子计算")
    parser.add_argument("--universe", default="csi300", help="股票池 (csi300 / zz500 等)")
    parser.add_argument("--tickers", default=None, help="逗号分隔的股票代码 (如 600519,300750)")
    parser.add_argument("--workers", type=int, default=1, help="并行工作进程数 (默认 1)")
    parser.add_argument("--start-idx", type=int, default=0, help="起始股票索引 (断点续跑)")
    parser.add_argument("--end-idx", type=int, default=None, help="结束股票索引")
    parser.add_argument("--params", default=None,
                        help='因子参数覆盖，JSON格式 (如 \'{"momentum": {"lookback": 10}}\')')
    args = parser.parse_args()

    # 解析因子参数
    factor_params = {}
    if args.params:
        try:
            import json
            factor_params = json.loads(args.params)
            logger.info(f"因子参数覆盖: {factor_params}")
        except json.JSONDecodeError as e:
            logger.error(f"--params JSON 解析失败: {e}")
            sys.exit(1)

    # 获取股票列表
    if args.tickers:
        tickers = [t.strip().zfill(6) for t in args.tickers.split(",")]
    else:
        try:
            tickers = DataProvider.get_csi300_components()
            logger.info(f"获取到 {len(tickers)} 只沪深300成分股")
        except Exception as e:
            logger.error(f"获取成分股失败: {e}")
            sys.exit(1)

    if not tickers:
        logger.error("股票列表为空")
        sys.exit(1)

    # 切片支持断点续跑
    tickers = tickers[args.start_idx:args.end_idx]
    total = len(tickers)
    logger.info(f"因子批量计算: {total} 只股票 ({args.start_idx}..{args.end_idx or 'end'})")
    if factor_params:
        logger.info(f"因子参数: {factor_params}")

    start_time = time.time()
    results = []

    if args.workers > 1:
        with ProcessPoolExecutor(max_workers=args.workers) as executor:
            futures = {executor.submit(compute_factors_for_ticker, t, factor_params): t for t in tickers}
            for i, future in enumerate(as_completed(futures), 1):
                r = future.result()
                results.append(r)
                if i % 10 == 0 or i == total:
                    elapsed = time.time() - start_time
                    logger.info(f"  进度: {i}/{total} ({elapsed:.0f}s)")
    else:
        for i, ticker in enumerate(tickers, 1):
            logger.info(f"[{i}/{total}] {ticker}")
            r = compute_factors_for_ticker(ticker, factor_params)
            results.append(r)
            if i % 10 == 0 or i == total:
                elapsed = time.time() - start_time
                ok = sum(1 for r in results if r["status"] == "ok")
                skip = sum(1 for r in results if r["status"] == "skip")
                err = sum(1 for r in results if r["status"] == "error")
                logger.info(f"  进度: {i}/{total} | OK:{ok} Skip:{skip} Err:{err} ({elapsed:.0f}s)")

    # 汇总
    elapsed = time.time() - start_time
    ok = sum(1 for r in results if r["status"] == "ok")
    skip = sum(1 for r in results if r["status"] == "skip")
    err = sum(1 for r in results if r["status"] == "error")
    total_factors = 0
    for r in results:
        if r["status"] == "ok":
            total_factors = max(total_factors, r.get("total_factors", 0))

    logger.info(f"{'='*60}")
    logger.info(f"因子计算完成: 耗时 {elapsed:.0f}s ({elapsed/60:.1f}min)")
    logger.info(f"  总股票: {total} | 成功: {ok} | 跳过: {skip} | 失败: {err}")
    logger.info(f"  每只股票因子数: {total_factors}")

    # 验证 DB 中的因子数量
    try:
        storage = DataStorage()
        result = storage.conn.execute(
            "SELECT COUNT(DISTINCT factor_name) FROM research.factors"
        ).fetchone()
        logger.info(f"  DB 中因子总数: {result[0]}")
    except Exception:
        pass

    logger.info(f"{'='*60}")

    if err > 0:
        failed = [r["ticker"] for r in results if r["status"] == "error"]
        logger.warning(f"失败股票: {', '.join(failed)}")

    sys.exit(0 if err == 0 else 1)


if __name__ == "__main__":
    main()
