"""
批量策略回测脚本

对 4 个已注册策略进行样本外回测验证，结果写入 backtest_runs 表。
使用因子引擎的动量/反转因子生成信号，用于向量化回测。

用法：
    python -m scripts.batch_backtest                            # 回测所有策略（默认 20 只）
    python -m scripts.batch_backtest --strategy momentum        # 指定策略
    python -m scripts.batch_backtest --ticker 600519            # 指定标的
    python -m scripts.batch_backtest --all-tickers              # 回测全部 300 只
    python -m scripts.batch_backtest --compare                  # 对比买入持有
    python -m scripts.batch_backtest --output results.json      # 输出 JSON
"""
import json
import sys
import argparse
import time
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from loguru import logger

from data.provider import DataProvider
from data.storage import DataStorage
from data.cleaner import DataCleaner
from research.backtest import BacktestEngine
from research.factors import FactorEngine
from strategies.registry import list_strategies
from configs.settings import settings


def get_tickers(limit: int = 20) -> list[str]:
    """获取回测标的列表"""
    storage = DataStorage()
    try:
        tickers = [r[0] for r in storage.conn.execute(
            "SELECT DISTINCT ticker FROM stock_daily ORDER BY ticker").fetchall()]
    except Exception:
        tickers = []
    if not tickers:
        try:
            csi300 = DataProvider.get_index_constituents("csi300")
            if not csi300.empty:
                tickers = csi300["ticker"].tolist()
        except Exception:
            pass
    return tickers[:limit]


def generate_signal_from_factor(
    df: pd.DataFrame,
    strategy: str,
) -> tuple[pd.Series, pd.Series]:
    """基于已注册因子值生成 entries/exits 信号"""
    close = df["close"]
    engine = FactorEngine()
    factors = engine.compute(df)

    if strategy == "momentum":
        mom = factors.get("momentum_20d", pd.Series(0, index=df.index))
        # 买入: 20日动量 > 5%; 卖出: 20日动量 < -2%
        entries = mom > 0.05
        exits = mom < -0.02

    elif strategy == "reversal":
        rev = factors.get("reversal_20d", pd.Series(0, index=df.index))
        # 买入: 20日跌幅 > 5%; 卖出: 反弹超过 2.5%
        entries = rev > 0.05
        exits = rev < 0.025

    elif strategy == "sentiment":
        mom = factors.get("momentum_5d", pd.Series(0, index=df.index))
        entries = mom > 0.03
        exits = mom < -0.015

    elif strategy == "regime_switch":
        mom20 = factors.get("momentum_20d", pd.Series(0, index=df.index))
        mom5 = factors.get("momentum_5d", pd.Series(0, index=df.index))
        entries = (mom20 > 0.03) & (mom5 > 0)
        exits = mom20 < -0.02

    else:
        mom = factors.get("momentum_20d", pd.Series(0, index=df.index))
        entries = mom > 0.05
        exits = mom < -0.02

    entries = entries.reindex(close.index, fill_value=False)
    exits = exits.reindex(close.index, fill_value=False)
    return entries, exits


def run_single_backtest(
    strategy: str,
    ticker: str,
    start_date: str = "2020-01-01",
    end_date: str = None,
) -> dict:
    """运行单次回测"""
    end_date = end_date or date.today().isoformat()

    storage = DataStorage()
    df = storage.load_stock_daily(ticker, start_date, end_date)
    if df.empty:
        df = DataProvider.get_stock_daily(ticker, start_date, end_date)
        if df.empty:
            return None
        df = DataCleaner.clean_ohlcv(df)
        storage.save_stock_daily(ticker, df)

    if len(df) < 60:
        logger.warning(f"  {ticker}: 数据不足 ({len(df)} 天)")
        return None

    close = df["close"]
    if close.dropna().empty:
        return None

    entries, exits = generate_signal_from_factor(df, strategy)

    if entries.sum() == 0:
        logger.warning(f"  {ticker}: 无入场信号")
        return None

    result = BacktestEngine.signal_backtest(
        close=close,
        entries=entries,
        exits=exits,
        init_cash=settings.backtest_init_cash,
        fees=settings.backtest_fees,
        slippage=settings.backtest_slippage,
    )

    return {
        "strategy": strategy,
        "ticker": ticker,
        "date_start": start_date,
        "date_end": end_date,
        "params_json": json.dumps({}),
        "total_return": float(result.get("total_return", 0)),
        "annual_return": float(result.get("annual_return", 0)),
        "sharpe_ratio": float(result.get("sharpe_ratio", 0)),
        "max_drawdown": float(result.get("max_drawdown", 0)),
        "win_rate": float(result.get("win_rate", 0)),
        "trade_count": int(result.get("trade_count", 0)),
        "init_cash": settings.backtest_init_cash,
        "fees": settings.backtest_fees,
        "slippage": settings.backtest_slippage,
    }


def save_result(record: dict):
    """保存回测结果到数据库"""
    if record is None:
        return
    run_id = f"{record['strategy']}_{record['ticker']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    storage = DataStorage()
    storage.conn.execute("""
        INSERT OR REPLACE INTO backtest_runs
        (run_id, strategy, ticker, date_start, date_end, params_json,
         total_return, annual_return, sharpe_ratio, max_drawdown,
         win_rate, trade_count, init_cash, fees, slippage, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        run_id, record["strategy"], record["ticker"],
        record["date_start"], record["date_end"], record["params_json"],
        record["total_return"], record["annual_return"],
        record["sharpe_ratio"], record["max_drawdown"],
        record["win_rate"], record["trade_count"],
        record["init_cash"], record["fees"], record["slippage"],
        datetime.now(),
    ))
    storage.conn.commit()


def batch_run(
    strategies: list[str] = None,
    tickers: list[str] = None,
    limit: int = 20,
    output: str = None,
):
    """批量运行回测"""
    if strategies is None:
        strategies = ["momentum", "reversal", "sentiment", "regime_switch"]

    if tickers is None:
        tickers = get_tickers(limit)

    logger.info(f"策略: {strategies}")
    logger.info(f"标的: {len(tickers)} 只")

    all_records = []
    total = len(strategies) * len(tickers)
    done = 0

    for sname in strategies:
        logger.info(f"--- {sname} ---")
        for ticker in tickers:
            record = run_single_backtest(sname, ticker,
                                          start_date="2020-01-01")
            if record:
                save_result(record)
                all_records.append(record)
            done += 1
            if done % 20 == 0:
                logger.info(f"  进度: {done}/{total}")

    logger.info(f"完成: {len(all_records)}/{total} 条有效记录")

    # 汇总
    summary = {}
    for sname in strategies:
        s_records = [r for r in all_records if r and r["strategy"] == sname]
        if not s_records:
            continue
        df_s = pd.DataFrame(s_records)
        summary[sname] = {
            "count": len(s_records),
            "avg_return": float(df_s["total_return"].mean()),
            "avg_sharpe": float(df_s["sharpe_ratio"].mean()),
            "avg_drawdown": float(df_s["max_drawdown"].mean()),
            "avg_win_rate": float(df_s["win_rate"].mean()),
            "total_trades": int(df_s["trade_count"].sum()),
        }

    result = {
        "strategies_tested": strategies,
        "tickers_tested": len(tickers),
        "total_runs": len(all_records),
        "summary": summary,
        "records": all_records,
    }

    if output:
        with open(output, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)
        logger.info(f"结果已保存: {output}")

    # 打印汇总
    print()
    print(f"{'策略':<20} {'数量':>6} {'总收益':>10} {'夏普':>8} {'回撤':>10} {'胜率':>8}")
    print("-" * 62)
    for sname, s in summary.items():
        print(f"{sname:<20} {s['count']:>6} {s['avg_return']:>9.2%} "
              f"{s['avg_sharpe']:>7.2f} {s['avg_drawdown']:>9.2%} {s['avg_win_rate']:>7.2%}")

    return result


def main():
    parser = argparse.ArgumentParser(description="批量策略回测")
    parser.add_argument("--strategy", default=None, help="指定策略")
    parser.add_argument("--ticker", default=None, help="指定股票")
    parser.add_argument("--all-tickers", action="store_true", help="回测所有标的")
    parser.add_argument("--limit", type=int, default=20, help="标的数量限制")
    parser.add_argument("--output", default=None, help="输出 JSON 文件")
    args = parser.parse_args()

    strategies = [args.strategy] if args.strategy else None
    tickers = [args.ticker] if args.ticker else None
    if args.all_tickers:
        limit = 9999
    else:
        limit = args.limit if not args.ticker else 9999

    batch_run(strategies=strategies, tickers=tickers, limit=limit, output=args.output)


if __name__ == "__main__":
    main()
