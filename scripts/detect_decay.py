"""
策略衰减检测脚本

用法：
    python -m scripts.detect_decay
    python -m scripts.detect_decay --ticker 600519
    python -m scripts.detect_decay --universe csi300

检测已注册因子的 IC 衰减、胜率衰减、夏普衰减等信号。
"""
import sys
import argparse
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from loguru import logger

from data.provider import DataProvider
from data.storage import DataStorage
from risk.decay_detector import DecayDetector


def detect_factor_decay(factor_names: list[str] = None,
                         tickers: list[str] = None) -> dict:
    """检测因子衰减情况"""
    storage = DataStorage()
    detector = DecayDetector()

    if factor_names is None:
        result = storage.conn.execute(
            "SELECT DISTINCT factor_name FROM research.factors"
        ).fetchall()
        factor_names = sorted([r[0] for r in result])

    if not factor_names:
        logger.error("无因子数据")
        return {"error": "no_factors"}

    logger.info(f"检测 {len(factor_names)} 个因子的衰减情况")

    all_reports = {}
    for fname in factor_names:
        # 获取因子的时序 IC (从评估表)
        try:
            ic_df = storage.conn.execute(
                "SELECT eval_date, ic FROM research.factor_evaluation "
                "WHERE factor_name = ? ORDER BY eval_date",
                [fname],
            ).fetchdf()
        except Exception:
            ic_df = pd.DataFrame()

        if ic_df.empty or len(ic_df) < 10:
            logger.debug(f"  {fname}: 评估数据不足, 跳过")
            continue

        ic_series = ic_df.set_index("eval_date")["ic"].dropna()
        if len(ic_series) < 10:
            continue

        report = detector.check(ic=ic_series)
        all_reports[fname] = report

        if report.is_decaying:
            logger.warning(f"  {fname}: 衰减!")
            for a in report.alerts:
                logger.warning(f"    [{a.level.value}] {a.metric}: {a.message}")
        else:
            logger.info(f"  {fname}: 正常")

    # 按 ticker 级别检测
    if tickers:
        for ticker in tickers[:20]:  # 最多20只
            df = storage.load_stock_daily(ticker)
            if df.empty or "close" not in df.columns:
                continue
            returns = df["close"].pct_change().dropna()
            if len(returns) < 60:
                continue

            # 滚动夏普
            roll_sharpe = (returns.rolling(20).mean() /
                          returns.rolling(20).std() * np.sqrt(252)).dropna()
            # 滚动胜率
            roll_win = returns.rolling(20).apply(
                lambda x: (x > 0).mean()
            ).dropna()

            report = detector.check(
                win_rate=roll_win,
                sharpe=roll_sharpe,
                returns=returns,
            )
            if report.is_decaying:
                logger.warning(f"  {ticker}: 策略衰减! "
                             f"({report.max_level.value})")

    decaying = sum(1 for r in all_reports.values() if r.is_decaying)
    logger.info(f"{'='*60}")
    logger.info(f"衰减检测完成: {decaying}/{len(all_reports)} 个因子衰减")
    logger.info(f"{'='*60}")

    return {"checked": len(all_reports), "decaying": decaying}


def main():
    parser = argparse.ArgumentParser(description="策略衰减检测")
    parser.add_argument("--ticker", default=None, help="单只股票代码")
    parser.add_argument("--universe", default="csi300", help="股票池")
    args = parser.parse_args()

    tickers = None
    if args.ticker:
        tickers = [args.ticker.zfill(6)]
    else:
        try:
            tickers = DataProvider.get_csi300_components()[:50]
        except Exception:
            pass

    result = detect_factor_decay(tickers=tickers)
    if "error" in result:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
