"""
MCP Risk Tools — stress test, Brinson attribution, decay detection, backtest.
"""
from __future__ import annotations

import json
from datetime import date, timedelta

import numpy as np
import pandas as pd

from data.storage import DataStorage
from risk.stress_test import StressTestEngine
from risk.attribution import BrinsonAttribution
from risk.decay_detector import DecayDetector
from strategies.registry import list_strategies as get_registered_strategies
import strategies.momentum.strategy  # noqa: F401
import strategies.event_driven.strategy  # noqa: F401
import strategies.sentiment.strategy  # noqa: F401
import strategies.regime_switch.strategy  # noqa: F401


def run_stress_test(ticker: str = "600519") -> str:
    """运行压力测试（4个历史危机场景）"""
    try:
        storage = DataStorage()
        df = storage.load_stock_daily(ticker)
        if df.empty:
            return json.dumps({"error": f"无数据: {ticker}"}, ensure_ascii=False)
        returns = df["close"].pct_change().dropna()
        engine = StressTestEngine()
        report = engine.run(returns)
        results = []
        for r in report.results:
            entry = {
                "scenario": r.scenario_name,
                "portfolio_return": round(r.portfolio_return, 4) if r.portfolio_return is not None else None,
                "max_drawdown": round(r.max_drawdown, 4) if r.max_drawdown is not None else None,
                "recovery_days": r.recovery_days,
                "survived": r.survived,
            }
            if r.recovery_days == -2:
                entry["note"] = "该时段数据不足，无法回测"
            results.append(entry)
        return json.dumps({
            "ticker": ticker,
            "scenarios": results,
            "worst": report.worst_scenario,
            "all_survived": report.all_survived,
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def run_brinson_attribution(portfolio_weights: str, benchmark_weights: str,
                            portfolio_returns: str, benchmark_returns: str) -> str:
    """
    运行 Brinson 收益归因

    Args:
        portfolio_weights: JSON dict, e.g. '{"白酒":0.4,"新能源":0.3}'
        benchmark_weights: JSON dict
        portfolio_returns: JSON dict, e.g. '{"白酒":0.02,"新能源":-0.01}'
        benchmark_returns: JSON dict
    """
    try:
        pw = json.loads(portfolio_weights)
        bw = json.loads(benchmark_weights)
        pr = json.loads(portfolio_returns)
        br = json.loads(benchmark_returns)

        if not all(isinstance(x, dict) for x in [pw, bw, pr, br]):
            return json.dumps({"error": "所有参数必须是 JSON 对象 (dict)，收到非 dict 类型。示例: "
                                        "'{\"白酒\":0.4,\"新能源\":0.3}'"}, ensure_ascii=False)

        attr = BrinsonAttribution()
        result = attr.attribute(
            portfolio_weights=pw,
            benchmark_weights=bw,
            portfolio_returns=pr,
            benchmark_returns=br,
        )
        return json.dumps({
            "total_excess_return": round(result.total_excess_return, 6),
            "allocation_effect": round(result.allocation_effect, 6),
            "selection_effect": round(result.selection_effect, 6),
            "interaction_effect": round(result.interaction_effect, 6),
            "sum_of_parts": round(result.sum_of_parts, 6),
            "sector_details": result.sector_details,
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def run_decay_detection(ticker: str = "600519") -> str:
    """运行策略衰减检测"""
    try:
        storage = DataStorage()
        df = storage.load_stock_daily(ticker)
        if df.empty:
            return json.dumps({"error": f"无数据: {ticker}"}, ensure_ascii=False)

        close = df["close"]
        returns = close.pct_change().dropna()

        # 模拟滚动胜率和夏普
        win_rate = (returns.rolling(20).apply(lambda x: (x > 0).mean()).dropna())
        sharpe = (returns.rolling(20).mean() / returns.rolling(20).std() * np.sqrt(252)).dropna()
        ic = returns.rolling(5).corr(close.pct_change(5).shift(-5)).dropna()

        detector = DecayDetector()
        report = detector.check(win_rate=win_rate, sharpe=sharpe, ic=ic, returns=returns)

        alerts = []
        for a in report.alerts:
            alerts.append({
                "level": a.level.value,
                "metric": a.metric,
                "message": a.message,
                "current_value": round(a.current_value, 4),
                "threshold": round(a.threshold, 4),
            })
        return json.dumps({
            "ticker": ticker,
            "is_decaying": report.is_decaying,
            "max_level": report.max_level.value,
            "alerts": alerts,
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def get_risk_report(ticker: str = "600519") -> str:
    """综合风险报告（压力测试 + 衰减检测）"""
    try:
        stress = json.loads(run_stress_test(ticker))
        decay = json.loads(run_decay_detection(ticker))
        return json.dumps({
            "ticker": ticker,
            "stress_test": stress,
            "decay_detection": decay,
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def list_strategies() -> str:
    """列出已注册的交易策略"""
    try:
        strategies = get_registered_strategies()
        return json.dumps({"count": len(strategies), "strategies": strategies}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def get_strategy_config(strategy_name: str) -> str:
    """获取策略配置"""
    try:
        from strategies.registry import create_strategy
        instance = create_strategy(strategy_name)
        params = instance.get_params()
        return json.dumps({"strategy": strategy_name, "config": params}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def run_backtest(strategy: str = "momentum", ticker: str = "600519",
                 start_date: str = "2025-01-01", end_date: str = "") -> str:
    """运行回测"""
    # ---------- 参数验证 ----------
    if not strategy or not strategy.strip():
        return json.dumps({"error": "策略名称不能为空"}, ensure_ascii=False)
    if not ticker or not ticker.strip():
        return json.dumps({"error": "股票代码不能为空"}, ensure_ascii=False)

    try:
        sd = date.fromisoformat(start_date)
    except (ValueError, TypeError):
        return json.dumps({"error": f"无效的开始日期格式: {start_date}"}, ensure_ascii=False)
    if sd > date.today():
        return json.dumps({"error": f"开始日期 {start_date} 是未来日期"}, ensure_ascii=False)

    if end_date:
        try:
            ed = date.fromisoformat(end_date)
        except (ValueError, TypeError):
            return json.dumps({"error": f"无效的结束日期格式: {end_date}"}, ensure_ascii=False)
        if sd > ed:
            return json.dumps({"error": "开始日期不能晚于结束日期"}, ensure_ascii=False)

    try:
        from scripts.backtest import run_backtest as _run_bt
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            _run_bt(
                strategy_name=strategy, ticker=ticker,
                start_date=start_date, end_date=end_date or None,
                output_format="json",
            )
        output = buf.getvalue()
        if not output.strip():
            return json.dumps({"error": "回测未产生结果（可能无数据或无交易信号）",
                               "ticker": ticker, "strategy": strategy}, ensure_ascii=False)
        return output
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def compare_backtest_runs(limit: int = 5) -> str:
    """对比最近多次回测结果"""
    try:
        storage = DataStorage()
        df = storage.load_backtest_runs(limit=limit)
        if df.empty:
            return json.dumps({"count": 0, "runs": []}, ensure_ascii=False)
        runs = []
        for _, row in df.iterrows():
            runs.append({
                "run_id": str(row.get("run_id", "")),
                "strategy": str(row.get("strategy", "")),
                "ticker": str(row.get("ticker", "")),
                "created_at": str(row.get("created_at", ""))[:19],
                "total_return": round(float(row.get("total_return", 0)), 4),
                "sharpe_ratio": round(float(row.get("sharpe_ratio", 0)), 4),
                "max_drawdown": round(float(row.get("max_drawdown", 0)), 4),
                "trade_count": int(row.get("trade_count", 0)),
            })
        return json.dumps({"count": len(runs), "runs": runs}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def run_health_check() -> str:
    """运行系统健康检查"""
    try:
        from scripts.health_check import HealthChecker
        checker = HealthChecker()
        results = checker.check_all()
        return json.dumps({
            "total": len(results),
            "passed": sum(1 for r in results if r["status"] == "pass"),
            "warnings": sum(1 for r in results if r["status"] == "warn"),
            "failed": sum(1 for r in results if r["status"] == "fail"),
            "details": results,
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def get_market_regime(days: int = 60) -> str:
    """获取当前市场状态识别结果"""
    try:
        from research.regime_detector import MarketRegimeDetector
        storage = DataStorage()
        df = storage.load_index_daily("000300")
        if df.empty:
            return json.dumps({"regime": "unknown", "confidence": 0.0}, ensure_ascii=False)
        detector = MarketRegimeDetector()
        regime_enum, confidence = detector.detect(df)
        return json.dumps({
            "regime": regime_enum.value,
            "confidence": round(confidence, 4),
            "description": detector.get_regime_label_cn(regime_enum),
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e), "regime": "unknown"}, ensure_ascii=False)
