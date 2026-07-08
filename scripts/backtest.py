"""
回测脚本

用法：
    python -m scripts.backtest --strategy momentum --start 2025-01-01 --end 2026-06-01
    python -m scripts.backtest --ticker 600519 --start 2025-01-01
    python -m scripts.backtest --compare last_5
    python -m scripts.backtest --output json
    python -m scripts.backtest --param-grid '{"entry_threshold": [0.03, 0.05], "rsi_overbought": [65, 70]}'
"""
import json
import sys
import argparse
import itertools
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from data.provider import DataProvider
from data.storage import DataStorage
from data.cleaner import DataCleaner
from knowledge.decision_memory import DecisionMemory
from strategies.momentum.strategy import MomentumStrategy
from research.backtest import BacktestEngine
from research.walk_forward import WalkForwardEngine
from research.factors import FactorEngine
from monitoring.metrics import MetricsTracker

from loguru import logger
from configs.settings import settings


def _record_backtest_decision(storage: DataStorage,
                              result: dict,
                              strategy_name: str,
                              ticker: str):
    """
    将一次回测结果写入 decision_memory（B2.1）。

    回测完成后调用，把回测产出的策略表现作为一条决策记录，
    供 scheduler 回填事后收益并参与决策准确率统计。

    失败不影响回测持久化（save_backtest_run 已完成），仅记录警告。
    """
    try:
        dm = DecisionMemory(storage)
        annual = float(result.get("annual_return", 0) or 0)
        sharpe = float(result.get("sharpe_ratio", 0) or 0)
        dm.record_decision(
            ticker=ticker,
            direction="backtest",
            weight=annual,
            reason=f"策略 {strategy_name} 回测，年化 {annual:.2%}, 夏普 {sharpe:.2f}",
            signal_type="backtest",
            strategy=strategy_name,
            decision_date=date.today(),
        )
        logger.success(f"  回测决策已写入 decision_memory (signal_type=backtest)")
    except Exception as e:
        logger.warning(f"  决策记忆写入失败（不影响回测结果）: {e}")


def _generate_signals(df_features: pd.DataFrame,
                      entry_threshold: float,
                      exit_threshold: float,
                      rsi_overbought: float) -> tuple:
    """
    生成动量入场/出场信号（B4.2 抽取，供单次回测与参数扫描复用）。

    逻辑与原 run_backtest 内联实现一致，仅参数化为可扫描。
    """
    entries = pd.Series(False, index=df_features.index)
    exits = pd.Series(False, index=df_features.index)

    for i in range(len(df_features)):
        row = df_features.iloc[i]
        momentum = row.get("momentum", 0)
        rsi = row.get("rsi", 50)
        trend = row.get("trend_strength", 0)

        if (momentum > entry_threshold
                and rsi < rsi_overbought
                and trend > 0):
            entries.iloc[i] = True

        if (momentum < exit_threshold
                or rsi > rsi_overbought):
            exits.iloc[i] = True

    return entries, exits


# standard 模式可扫描的参数名（与 settings.momentum_* 对应）
_SCANNABLE_PARAMS = ("entry_threshold", "exit_threshold", "rsi_overbought")


def _expand_param_grid(param_grid: dict) -> list:
    """展开参数网格为参数组合列表（笛卡尔积）。"""
    keys = list(param_grid.keys())
    unknown = [k for k in keys if k not in _SCANNABLE_PARAMS]
    if unknown:
        raise ValueError(
            f"未知的扫描参数: {unknown}；standard 模式仅支持 {list(_SCANNABLE_PARAMS)}"
        )
    return [dict(zip(keys, vals))
            for vals in itertools.product(*param_grid.values())]


def _run_single_backtest(df_features: pd.DataFrame,
                         params: dict,
                         init_cash: float,
                         fees: float,
                         slippage: float) -> dict:
    """
    用给定参数跑一次 standard 回测，返回 BacktestEngine.signal_backtest 的结果 dict。

    不做持久化、不打日志——供参数扫描循环调用。
    params 缺失的键由调用方在进入此函数前填好默认值。
    """
    entries, exits = _generate_signals(
        df_features,
        entry_threshold=params["entry_threshold"],
        exit_threshold=params["exit_threshold"],
        rsi_overbought=params["rsi_overbought"],
    )
    return BacktestEngine.signal_backtest(
        close=df_features["close"],
        entries=entries,
        exits=exits,
        init_cash=init_cash,
        fees=fees,
        slippage=slippage,
    )


def run_backtest(strategy_name: str = "momentum",
                 ticker: str = "600519",
                 start_date: str = "2025-01-01",
                 end_date: str = None,
                 output_format: str = "table",
                 param_grid: dict = None):
    """
    运行回测

    Args:
        strategy_name: 策略名称
        ticker: 股票代码
        start_date: 开始日期
        end_date: 结束日期
        output_format: 输出格式 (table/json)
        param_grid: 参数扫描网格，形如
            {"entry_threshold": [0.03, 0.05], "exit_threshold": [-0.02], "rsi_overbought": [65, 70]}
            为 None 时走单次回测（用 settings 默认参数）；非 None 时跑网格扫描，
            返回按夏普降序的指标列表，仅持久化最优组合。
    """
    logger.info(f"回测 {strategy_name} | {ticker} | {start_date} ~ {end_date or '至今'}"
                + (f" | 参数扫描: {param_grid}" if param_grid else ""))

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

    init_cash = settings.backtest_init_cash
    fees = settings.backtest_fees
    slippage = settings.backtest_slippage

    if param_grid is not None:
        return _run_param_scan(
            storage=storage,
            df_features=df_features,
            strategy_name=strategy_name,
            ticker=ticker,
            start_date=start_date,
            end_date=end_date,
            param_grid=param_grid,
            init_cash=init_cash,
            fees=fees,
            slippage=slippage,
            output_format=output_format,
        )

    # 生成信号
    logger.info("[3/4] 生成信号...")
    params = {
        "entry_threshold": settings.momentum_entry_threshold,
        "exit_threshold": settings.momentum_exit_threshold,
        "rsi_overbought": settings.momentum_rsi_overbought,
    }
    entries, exits = _generate_signals(
        df_features,
        entry_threshold=params["entry_threshold"],
        exit_threshold=params["exit_threshold"],
        rsi_overbought=params["rsi_overbought"],
    )
    logger.success(f"  入场信号: {entries.sum()} 次")
    logger.success(f"  出场信号: {exits.sum()} 次")

    # 回测
    logger.info("[4/4] 运行回测...")
    result = BacktestEngine.signal_backtest(
        close=df_features["close"],
        entries=entries,
        exits=exits,
        init_cash=init_cash,
        fees=fees,
        slippage=slippage,
    )

    # 输出结果
    _log_result(result, output_format)

    # 持久化到 DB
    try:
        result["strategy"] = strategy_name
        result["ticker"] = ticker
        result["date_start"] = start_date
        result["date_end"] = end_date or date.today().isoformat()
        result["init_cash"] = init_cash
        result["fees"] = fees
        result["slippage"] = slippage

        run_id = storage.save_backtest_run(result)
        logger.success(f"  回测结果已保存: {run_id}")

        _record_backtest_decision(storage, result, strategy_name, ticker)
    except Exception as e:
        logger.warning(f"  结果持久化失败: {e}")

    # 保存权益曲线 CSV（兼容旧流程）
    equity = result.get("equity_curve")
    if equity is not None:
        csv_path = f"backtest_{strategy_name}_{ticker}.csv"
        equity.to_csv(csv_path)
        logger.success(f"  权益曲线已保存: {csv_path}")


def _log_result(result: dict, output_format: str):
    """格式化输出单次回测结果。"""
    if output_format == "json":
        out = {k: v for k, v in result.items()
               if not isinstance(v, pd.Series)}
        logger.info(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    else:
        logger.info(f"总收益: {result['total_return']:.2%}, 年化: {result.get('annual_return', 0):.2%}, "
                    f"夏普: {result['sharpe_ratio']:.2f}, 最大回撤: {result['max_drawdown']:.2%}, "
                    f"交易次数: {result['trade_count']}")


def _run_param_scan(storage,
                    df_features: pd.DataFrame,
                    strategy_name: str,
                    ticker: str,
                    start_date: str,
                    end_date: str,
                    param_grid: dict,
                    init_cash: float,
                    fees: float,
                    slippage: float,
                    output_format: str):
    """
    standard 模式参数扫描（B4.2）。

    展开参数网格 → 每组跑一次 → 收集指标 → 按夏普降序输出 → 仅持久化最优组合。
    返回 list[dict]，每项含 {params, total_return, annual_return, sharpe_ratio, max_drawdown, trade_count}。
    """
    logger.info("[3/4] 参数扫描：展开网格...")
    combos = _expand_param_grid(param_grid)
    logger.info(f"  共 {len(combos)} 组参数组合")

    defaults = {
        "entry_threshold": settings.momentum_entry_threshold,
        "exit_threshold": settings.momentum_exit_threshold,
        "rsi_overbought": settings.momentum_rsi_overbought,
    }

    logger.info("[4/4] 运行扫描...")
    scan_results = []
    for idx, combo in enumerate(combos, 1):
        # 网格未指定的键回退到 settings 默认
        full_params = {**defaults, **combo}
        result = _run_single_backtest(df_features, full_params,
                                      init_cash, fees, slippage)
        row = {
            "params": combo,
            "total_return": float(result.get("total_return", 0) or 0),
            "annual_return": float(result.get("annual_return", 0) or 0),
            "sharpe_ratio": float(result.get("sharpe_ratio", 0) or 0),
            "max_drawdown": float(result.get("max_drawdown", 0) or 0),
            "trade_count": int(result.get("trade_count", 0) or 0),
        }
        scan_results.append(row)
        logger.info(f"  [{idx}/{len(combos)}] {combo} -> "
                    f"夏普 {row['sharpe_ratio']:.2f}, 年化 {row['annual_return']:.2%}, "
                    f"回撤 {row['max_drawdown']:.2%}, 交易 {row['trade_count']}")

    # 按夏普降序
    scan_results.sort(key=lambda r: r["sharpe_ratio"], reverse=True)

    # 表格输出（与 walk-forward --scan 风格一致）
    logger.info(f"{'='*80}")
    logger.info(f"  参数扫描结果 (按夏普降序)")
    logger.info(f"{'='*80}")
    logger.info(f"{'参数':<40} {'夏普':<8} {'收益':<10} {'回撤':<10} {'交易次数':<10}")
    logger.info(f"{'-'*80}")
    for r in scan_results:
        logger.info(f"{str(r['params']):<40} {r['sharpe_ratio']:>6.2f}  "
                    f"{r['total_return']:>+7.2%}  {r['max_drawdown']:>+7.2%}  "
                    f"{r['trade_count']:<10}")
    logger.info(f"{'='*80}")

    if output_format == "json":
        logger.info(json.dumps(scan_results, ensure_ascii=False, indent=2, default=str))

    # 持久化最优组合（与 walk-forward scan 行为一致：只存 best）
    if scan_results:
        best = scan_results[0]
        try:
            result_dict = {
                "strategy": strategy_name,
                "ticker": ticker,
                "date_start": start_date,
                "date_end": end_date or date.today().isoformat(),
                "total_return": best["total_return"],
                "annual_return": best["annual_return"],
                "sharpe_ratio": best["sharpe_ratio"],
                "max_drawdown": best["max_drawdown"],
                "trade_count": best["trade_count"],
                "init_cash": init_cash,
                "fees": fees,
                "slippage": slippage,
                "params": {
                    "mode": "standard_scan",
                    "grid": param_grid,
                    "best_params": best["params"],
                },
            }
            run_id = storage.save_backtest_run(result_dict)
            logger.success(f"  最优参数回测结果已保存: {run_id}")

            _record_backtest_decision(storage, result_dict, strategy_name, ticker)
        except Exception as e:
            logger.warning(f"  最优结果持久化失败: {e}")

    return scan_results


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

                _record_backtest_decision(storage, result_dict, "momentum_wfo", ticker)
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

            _record_backtest_decision(storage, result_dict, "momentum_wfo", ticker)
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
                       help="参数扫描 (walk-forward): --scan 'lookback=10,20,30,entry_threshold=0.03,0.05'")
    parser.add_argument("--param-grid", type=str, default=None,
                       help="参数扫描 (standard 模式)，JSON 格式: "
                            "--param-grid '{\"entry_threshold\": [0.03, 0.05], "
                            "\"exit_threshold\": [-0.02], \"rsi_overbought\": [65, 70]}'")
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
        param_grid = None
        if args.param_grid:
            try:
                param_grid = json.loads(args.param_grid)
            except json.JSONDecodeError as e:
                logger.error(f"--param-grid JSON 解析失败: {e}")
                sys.exit(2)
            if not isinstance(param_grid, dict) or not param_grid:
                logger.error("--param-grid 必须是非空 JSON 对象")
                sys.exit(2)
        run_backtest(args.strategy, args.ticker, args.start, args.end,
                     args.output, param_grid=param_grid)
