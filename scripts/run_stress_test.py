"""
压力测试脚本

用法：
    python -m scripts.run_stress_test --ticker 600519
    python -m scripts.run_stress_test --universe csi300

对指定股票在 4 个历史危机场景（2015股灾、2018贸易战、
2020疫情、2024回调）下的表现进行压力测试。
"""
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
from loguru import logger

from data.provider import DataProvider
from data.storage import DataStorage
from risk.stress_test import StressTestEngine


def run_stress_test_for_ticker(ticker: str) -> dict:
    """对单只股票运行压力测试"""
    storage = DataStorage()
    df = storage.load_stock_daily(ticker)

    if df.empty or "close" not in df.columns:
        logger.warning(f"  {ticker}: 无数据")
        return {"ticker": ticker, "error": "no_data"}

    returns = df["close"].pct_change().dropna()
    if len(returns) < 252:
        logger.warning(f"  {ticker}: 数据不足 ({len(returns)} 天)")
        return {"ticker": ticker, "error": "insufficient_data"}

    engine = StressTestEngine()
    report = engine.run(returns)

    result = {
        "ticker": ticker,
        "worst_scenario": report.worst_scenario,
        "all_survived": report.all_survived,
        "scenarios": [],
    }
    for r in report.results:
        result["scenarios"].append({
            "scenario": r.scenario_name,
            "portfolio_return": round(r.portfolio_return, 4) if r.portfolio_return is not None else None,
            "max_drawdown": round(r.max_drawdown, 4) if r.max_drawdown is not None else None,
            "recovery_days": r.recovery_days,
            "survived": r.survived,
        })

    return result


def main():
    parser = argparse.ArgumentParser(description="压力测试")
    parser.add_argument("--ticker", default=None, help="单只股票代码")
    parser.add_argument("--universe", default="csi300", help="股票池 (多只时取前10只)")
    args = parser.parse_args()

    if args.ticker:
        tickers = [args.ticker.zfill(6)]
    else:
        try:
            tickers = DataProvider.get_csi300_components()[:10]
        except Exception:
            logger.error("获取成分股失败")
            sys.exit(1)

    logger.info(f"压力测试: {len(tickers)} 只股票")
    logger.info(f"场景: 2015股灾 / 2018贸易战 / 2020疫情 / 2024回调")
    logger.info(f"{'='*60}")

    all_survived = True
    for i, ticker in enumerate(tickers):
        logger.info(f"[{i+1}/{len(tickers)}] {ticker}")
        r = run_stress_test_for_ticker(ticker)

        if "error" in r:
            continue

        for s in r["scenarios"]:
            status = "✅" if s["survived"] else "❌"
            ret_str = f"{s['portfolio_return']:+.2%}" if s["portfolio_return"] is not None else "N/A"
            dd_str = f"{s['max_drawdown']:+.2%}" if s['max_drawdown'] is not None else "N/A"
            rec_str = f"{s['recovery_days']}天恢复" if s["recovery_days"] > 0 else (
                "未恢复" if s["recovery_days"] == -1 else "N/A"
            )
            logger.info(f"  {status} {s['scenario']:12s} | 收益:{ret_str:>8s} | "
                       f"回撤:{dd_str:>8s} | {rec_str}")

        if not r.get("all_survived", True):
            all_survived = False

    logger.info(f"{'='*60}")
    logger.info(f"全部存活: {all_survived}")
    logger.info(f"{'='*60}")

    sys.exit(0 if all_survived else 1)


if __name__ == "__main__":
    main()
