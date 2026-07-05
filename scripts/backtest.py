"""
回测脚本

用法：
    python -m scripts.backtest --strategy momentum --start 2025-01-01 --end 2026-06-01
    python -m scripts.backtest --ticker 600519 --start 2025-01-01
    python -m scripts.backtest --compare last_5
    python -m scripts.backtest --output json
"""
import json
import sys
import argparse
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from data.provider import DataProvider
from data.storage import DataStorage
from data.cleaner import DataCleaner
from strategies.momentum.strategy import MomentumStrategy
from research.backtest import BacktestEngine
from research.walk_forward import WalkForwardEngine
from research.factors import FactorEngine
from monitoring.metrics import MetricsTracker

from loguru import logger
from configs.settings import settings


def run_backtest(strategy_name: str = "momentum",
                 ticker: str = "600519",
                 start_date: str = "2025-01-01",
                 end_date: str = None,
                 output_format: str = "table"):
    """
    运行回测

    Args:
        strategy_name: 策略名称
        ticker: 股票代码
        start_date: 开始日期
        end_date: 结束日期
        output_format: 输出格式 (table/json)
    """
    logger.info(f"回测 {strategy_name} | {ticker} | {start_date} ~ {end_date or '至今'}")

    # 获取数据
    logger.info("[1/4] 获取数据...")
    storage = DataStorage()
    df = storage.load_stock_daily(ticker, start_date, end_date)

    if df.empty:
        logger.info("  本地无数据，从数据源获取...")
        df = DataProvider.get_stock_daily(ticker, start_date, end_date)
        if not df.empty:
            df = DataCleaner.clean_ohlcv(df)
            storage.save_stock_daily(ticker, df)

    if df.empty:
        logger.error("  无数据，无法回测")
        return

    logger.success(f"  获取 {len(df)} 条数据")

    # 准备特征
    logger.info("[2/4] 准备特征...")
    strategy = MomentumStrategy()
    df_features = strategy.prepare_features(df)
    logger.success(f"  生成 {len(df_features.columns)} 个特征列")

    # 生成信号
    logger.info("[3/4] 生成信号...")
    entries = pd.Series(False, index=df_features.index)
    exits = pd.Series(False, index=df_features.index)

    for i in range(len(df_features)):
        row = df_features.iloc[i]
        momentum = row.get("momentum", 0)
        rsi = row.get("rsi", 50)
        trend = row.get("trend_strength", 0)

        # 入场条件
        if (momentum > settings.momentum_entry_threshold
                and rsi < settings.momentum_rsi_overbought
                and trend > 0):
            entries.iloc[i] = True

        # 出场条件
        if (momentum < settings.momentum_exit_threshold
                or rsi > settings.momentum_rsi_overbought):
            exits.iloc[i] = True

    logger.success(f"  入场信号: {entries.sum()} 次")
    logger.success(f"  出场信号: {exits.sum()} 次")

    # 回测
    logger.info("[4/4] 运行回测...")
    result = BacktestEngine.signal_backtest(
        close=df_features["close"],
        entries=entries,
        exits=exits,
        init_cash=settings.backtest_init_cash,
        fees=settings.backtest_fees,
        slippage=settings.backtest_slippage,
    )

    # 输出结果
    if output_format == "json":
        out = {k: v for k, v in result.items()
               if not isinstance(v, pd.Series)}
        logger.info(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    else:
        logger.info(f"总收益: {result['total_return']:.2%}, 年化: {result.get('annual_return', 0):.2%}, "
                    f"夏普: {result['sharpe_ratio']:.2f}, 最大回撤: {result['max_drawdown']:.2%}, "
                    f"交易次数: {result['trade_count']}")

    # 持久化到 DB
    try:
        result["strategy"] = strategy_name
        result["ticker"] = ticker
        result["date_start"] = start_date
        result["date_end"] = end_date or date.today().isoformat()
        result["init_cash"] = settings.backtest_init_cash
        result["fees"] = settings.backtest_fees
        result["slippage"] = settings.backtest_slippage

        run_id = storage.save_backtest_run(result)
        logger.success(f"  回测结果已保存: {run_id}")
    except Exception as e:
        logger.warning(f"  结果持久化失败: {e}")

    # 保存权益曲线 CSV（兼容旧流程）
    equity = result.get("equity_curve")
    if equity is not None:
        csv_path = f"backtest_{strategy_name}_{ticker}.csv"
        equity.to_csv(csv_path)
        logger.success(f"  权益曲线已保存: {csv_path}")


def compare_runs(n: int = 3):
    """对比最近 N 次回测结果"""
    storage = DataStorage()
    df = storage.load_backtest_runs(limit=n)

    if df.empty:
        logger.info("无回测记录")
        return

    logger.info(f"{'='*80}")
    logger.info(f"  最近 {len(df)} 次回测对比")
    logger.info(f"{'='*80}")
    logger.info(f"{'创建时间':<20} {'策略':<12} {'标的':<10} {'总收益':<10} {'年化':<10} "
          f"{'夏普':<8} {'最大回撤':<10} {'交易次数':<10}")
    logger.info(f"{'-'*80}")

    for _, row in df.iterrows():
        ts = str(row.get("created_at", ""))[:16] if row.get("created_at") else ""
        logger.info(f"{ts:<20} {str(row.get('strategy', '')):<12} {str(row.get('ticker', '')):<10} "
              f"{float(row.get('total_return', 0)):>+7.2%}  "
              f"{float(row.get('annual_return', 0)):>+7.2%}  "
              f"{float(row.get('sharpe_ratio', 0)):>6.2f}  "
              f"{float(row.get('max_drawdown', 0)):>+7.2%}  "
              f"{int(row.get('trade_count', 0)):<10}")

    logger.info(f"{'='*80}")


def run_walk_forward(ticker: str = "600519",
                     start_date: str = "2020-01-01",
                     end_date: str = None,
                     train_window: int = 252,
                     test_window: int = 63,
                     step: int = 63,
                     scan: str = None):
    """运行 Walk-Forward 回测"""
    logger.info(f"WFO {ticker} | 训练{train_window}日 测试{test_window}日 步进{step}日")

    storage = DataStorage()
    df = storage.load_stock_daily(ticker, start_date, end_date)
    if df.empty:
        logger.error("无数据")
        return

    close = df["close"]

    def momentum_signal(close_slice: pd.Series, params: dict) -> tuple:
        """基于动量参数的信号生成函数"""
        lookback = params.get("lookback", 20)
        entry_thresh = params.get("entry_threshold", 0.05)
        exit_thresh = params.get("exit_threshold", -0.02)

        mom = close_slice.pct_change(lookback)
        entries = mom > entry_thresh
        exits = mom < exit_thresh
        return entries, exits

    engine = WalkForwardEngine(
        train_window=train_window,
        test_window=test_window,
        step=step,
    )

    if scan:
        # 参数扫描模式
        param_grid = {}
        for pair in scan.split(","):
            pair = pair.strip()
            if "=" not in pair:
                continue
            key, values_str = pair.split("=", 1)
            values = []
            for v in values_str.split(","):
                v = v.strip()
                try:
                    values.append(int(v) if v.isdigit() or (v.startswith("-") and v[1:].isdigit()) else float(v))
                except ValueError:
                    values.append(v)
            param_grid[key] = values

        logger.info(f"参数扫描: {param_grid}")
        scan_results = engine.parameter_scan(close, momentum_signal, param_grid)

        logger.info(f"{'='*80}")
        logger.info(f"  参数扫描结果 (按夏普降序)")
        logger.info(f"{'='*80}")
        logger.info(f"{'参数':<30} {'夏普':<8} {'收益':<10} {'回撤':<10} {'稳定性':<8} {'胜率':<8}")
        logger.info(f"{'-'*80}")
        for r in scan_results:
            param_str = str(r["params"])
            logger.info(f"{param_str:<30} {r['avg_sharpe']:>6.2f}  "
                  f"{r['avg_return']:>+7.2%}  {r['avg_max_drawdown']:>+7.2%}  "
                  f"{r['stability']:>6.0%}  {r['win_periods']}/{r['total_periods']}")
        logger.info(f"{'='*80}")

        # 保存最优参数到 DB
        if scan_results:
            best = scan_results[0]
            try:
                result_dict = {
                    "strategy": "momentum_wfo",
                    "ticker": ticker,
                    "date_start": start_date,
                    "date_end": end_date or date.today().isoformat(),
                    "total_return": best["avg_return"],
                    "annual_return": best["avg_return"],
                    "sharpe_ratio": best["avg_sharpe"],
                    "max_drawdown": best["avg_max_drawdown"],
                    "win_rate": best["stability"],
                    "trade_count": best["total_periods"],
                    "params": {
                        "mode": "walk_forward",
                        "scan": param_grid,
                        "best_params": best["params"],
                        "train_window": train_window,
                        "test_window": test_window,
                        "step": step,
                    },
                }
                run_id = storage.save_backtest_run(result_dict)
                logger.success(f"WFO 结果已保存: {run_id}")
            except Exception as e:
                logger.warning(f"保存失败: {e}")
    else:
        # 普通 WFO 模式
        result = engine.run(close, momentum_signal)
        logger.info(f"WFO 结果: {result.total_periods} 窗口, "
                    f"平均收益 {result.avg_return:.2%}, "
                    f"平均夏普 {result.avg_sharpe:.2f}, "
                    f"稳定性 {result.stability:.0%}")

        # 保存到 DB
        try:
            result_dict = {
                "strategy": "momentum_wfo",
                "ticker": ticker,
                "date_start": start_date,
                "date_end": end_date or date.today().isoformat(),
                "total_return": result.avg_return,
                "annual_return": result.avg_return,
                "sharpe_ratio": result.avg_sharpe,
                "max_drawdown": result.avg_max_drawdown,
                "win_rate": result.stability,
                "trade_count": result.total_periods,
                "params": {
                    "mode": "walk_forward",
                    "train_window": train_window,
                    "test_window": test_window,
                    "step": step,
                },
            }
            run_id = storage.save_backtest_run(result_dict)
            logger.success(f"WFO 结果已保存: {run_id}")
        except Exception as e:
            logger.warning(f"保存失败: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="回测工具")
    parser.add_argument("--strategy", default="momentum", help="策略名称")
    parser.add_argument("--ticker", default="600519", help="股票代码")
    parser.add_argument("--start", default="2025-01-01", help="开始日期")
    parser.add_argument("--end", default=None, help="结束日期")
    parser.add_argument("--compare", type=int, default=0,
                       help="对比最近 N 次回测 (不运行新回测)")
    parser.add_argument("--output", choices=["table", "json"], default="table",
                       help="输出格式")
    parser.add_argument("--mode", choices=["standard", "walk-forward"], default="standard",
                       help="回测模式")
    parser.add_argument("--train-window", type=int, default=252,
                       help="WFO 训练窗口 (天)")
    parser.add_argument("--test-window", type=int, default=63,
                       help="WFO 测试窗口 (天)")
    parser.add_argument("--step", type=int, default=63,
                       help="WFO 滑动步进 (天)")
    parser.add_argument("--scan", type=str, default=None,
                       help="参数扫描: --scan 'lookback=10,20,30,entry_threshold=0.03,0.05'")
    args = parser.parse_args()

    if args.compare > 0:
        compare_runs(args.compare)
    elif args.mode == "walk-forward":
        run_walk_forward(
            ticker=args.ticker,
            start_date=args.start,
            end_date=args.end,
            train_window=args.train_window,
            test_window=args.test_window,
            step=args.step,
            scan=args.scan,
        )
    else:
        run_backtest(args.strategy, args.ticker, args.start, args.end, args.output)
