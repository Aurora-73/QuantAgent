"""
投资假设自动生成（B2.3）。

从因子评估结果（IC）和回测结果自动生成投资假设，初始状态为 `draft`。
**必须复用** `HYPOTHESIS_TRANSITIONS` 状态机，不另造状态语义。

触发条件：
  - IC > 0.05 的因子 → "{factor} 具有正向预测能力"
  - IC < -0.05 的因子 → "{factor} 具有反向预测能力"
  - 回测年化 > 15% → "{strategy} 在 {market_regime} 下有效"

存储：调 `kb.save_hypothesis(dict)`，落地到 `knowledge/hypotheses/hypotheses.jsonl`。
状态流转：自动生成 → draft → active → verified/invalidated → obsolete
"""
from __future__ import annotations

from datetime import date
from typing import Optional

import pandas as pd
from loguru import logger

from knowledge.knowledge_base import (
    KnowledgeBase,
    HYPOTHESIS_INITIAL_STATUS,
    HYPOTHESIS_TRANSITIONS,
)


# 假设生成的默认阈值
IC_THRESHOLD = 0.05
BACKTEST_RETURN_THRESHOLD = 0.15


def _detect_market_regime(storage=None) -> str:
    """
    简单市场风格检测：基于沪深300近 60 日收益判断。

    Returns:
        "uptrend" / "downtrend" / "rangebound" / "unknown"
    """
    try:
        if storage is None:
            from data.storage import DataStorage
            storage = DataStorage()

        df = storage.load_index_daily("000300")
        if df.empty or "close" not in df.columns or len(df) < 60:
            return "unknown"

        recent = df["close"].tail(60)
        ret_60d = float(recent.iloc[-1] / recent.iloc[0] - 1)
        vol = float(recent.pct_change().std())

        if ret_60d > 0.05:
            return "uptrend"
        elif ret_60d < -0.05:
            return "downtrend"
        else:
            return "rangebound"
    except Exception:
        return "unknown"


def generate_factor_hypothesis(factor_name: str,
                               ic_value: float,
                               ticker: str = "",
                               kb: KnowledgeBase = None,
                               validation_run_id: str = None) -> Optional[str]:
    """
    根据因子 IC 值生成假设。

    Args:
        factor_name: 因子名称
        ic_value: IC 值（> 0.05 正向，< -0.05 反向）
        ticker: 关联标的（可选）
        kb: KnowledgeBase 实例
        validation_run_id: 关联的验证回测 run_id（可选）

    Returns:
        假设 ID，未达阈值返回 None
    """
    kb = kb or KnowledgeBase()

    if ic_value is None or pd.isna(ic_value):
        return None

    ic_value = float(ic_value)

    if ic_value > IC_THRESHOLD:
        direction = "正向预测能力"
    elif ic_value < -IC_THRESHOLD:
        direction = "反向预测能力"
    else:
        return None  # IC 不显著，不生成

    hypothesis = {
        "title": f"{factor_name} 具有{direction}",
        "description": (
            f"因子 {factor_name} 的 IC = {ic_value:.4f}，"
            f"{'超过' if abs(ic_value) > IC_THRESHOLD else '低于'}阈值 {IC_THRESHOLD}，"
            f"表明该因子对未来收益具有{direction}。"
        ),
        "category": "factor_ic",
        "factor_name": factor_name,
        "ic_value": round(ic_value, 6),
        "ticker": ticker,
        "status": HYPOTHESIS_INITIAL_STATUS,  # "draft"
        "validation_run_id": validation_run_id,
        "source": "auto_generated",
    }

    hyp_id = kb.save_hypothesis(hypothesis)
    logger.info(f"生成因子假设: {hypothesis['title']} (id={hyp_id})")
    return hyp_id


def generate_backtest_hypothesis(strategy: str,
                                 annual_return: float,
                                 ticker: str = "",
                                 run_id: str = None,
                                 kb: KnowledgeBase = None,
                                 storage=None,
                                 market_regime: str = None) -> Optional[str]:
    """
    根据回测结果生成假设。

    Args:
        strategy: 策略名称
        annual_return: 年化收益率
        ticker: 回测标的
        run_id: 关联的回测 run_id（用于后续验证）
        kb: KnowledgeBase 实例
        storage: DataStorage 实例（用于市场风格检测）
        market_regime: 指定市场风格；None 则自动检测

    Returns:
        假设 ID，未达阈值返回 None
    """
    kb = kb or KnowledgeBase()

    if annual_return is None or pd.isna(annual_return):
        return None

    annual_return = float(annual_return)

    if annual_return <= BACKTEST_RETURN_THRESHOLD:
        return None  # 回测收益不显著，不生成

    regime = market_regime or _detect_market_regime(storage)

    hypothesis = {
        "title": f"{strategy} 在 {regime} 市场下有效",
        "description": (
            f"策略 {strategy} 在标的 {ticker or '未知'} 的回测中，"
            f"年化收益 {annual_return:.2%} 超过阈值 {BACKTEST_RETURN_THRESHOLD:.0%}，"
            f"当前市场风格为 {regime}。"
        ),
        "category": "backtest_performance",
        "strategy": strategy,
        "annual_return": round(annual_return, 6),
        "ticker": ticker,
        "market_regime": regime,
        "status": HYPOTHESIS_INITIAL_STATUS,  # "draft"
        "validation_run_id": run_id,
        "source": "auto_generated",
    }

    hyp_id = kb.save_hypothesis(hypothesis)
    logger.info(f"生成回测假设: {hypothesis['title']} (id={hyp_id})")
    return hyp_id


def auto_generate_from_factors(ticker: str,
                               storage=None,
                               kb: KnowledgeBase = None,
                               ic_threshold: float = IC_THRESHOLD) -> list[str]:
    """
    批量：对指定标的的所有因子做 IC 评估，生成假设。

    Args:
        ticker: 标的代码
        storage: DataStorage 实例
        kb: KnowledgeBase 实例
        ic_threshold: IC 阈值（覆盖默认值）

    Returns:
        生成的假设 ID 列表
    """
    global IC_THRESHOLD
    old_threshold = IC_THRESHOLD
    IC_THRESHOLD = ic_threshold
    try:
        kb = kb or KnowledgeBase()
        if storage is None:
            from data.storage import DataStorage
            storage = DataStorage()

        from research.factors import FactorEngine
        from research.evaluator import FactorEvaluator

        # 加载行情数据
        df = storage.load_stock_daily(ticker)
        if df.empty or "close" not in df.columns:
            logger.warning(f"无 {ticker} 行情数据，跳过因子假设生成")
            return []

        # 计算所有因子
        fe = FactorEngine()
        df_factors = fe.compute_all(df)

        generated = []
        factor_names = list(fe.list_factors().keys())

        for fname in factor_names:
            if fname not in df_factors.columns:
                continue
            factor_series = df_factors[fname].dropna()
            if len(factor_series) < 60:
                continue

            try:
                report = FactorEvaluator.full_report(factor_series, df_factors["close"])
                ic_value = report.get("ic", {}).get("ic")
                if ic_value is not None and not pd.isna(ic_value):
                    hyp_id = generate_factor_hypothesis(fname, ic_value, ticker, kb)
                    if hyp_id:
                        generated.append(hyp_id)
            except Exception as e:
                logger.debug(f"因子 {fname} 评估失败: {e}")

        logger.info(f"标的 {ticker} 生成 {len(generated)} 条因子假设")
        return generated
    finally:
        IC_THRESHOLD = old_threshold


def auto_generate_from_backtests(storage=None,
                                 kb: KnowledgeBase = None,
                                 return_threshold: float = BACKTEST_RETURN_THRESHOLD,
                                 days: int = 90) -> list[str]:
    """
    批量：扫描最近回测记录，为高收益策略生成假设。

    Args:
        storage: DataStorage 实例
        kb: KnowledgeBase 实例
        return_threshold: 年化收益阈值
        days: 回溯天数

    Returns:
        生成的假设 ID 列表
    """
    kb = kb or KnowledgeBase()
    if storage is None:
        from data.storage import DataStorage
        storage = DataStorage()

    runs = storage.load_backtest_runs(limit=50)
    if runs.empty:
        logger.info("无回测记录，跳过回测假设生成")
        return []

    generated = []
    for _, row in runs.iterrows():
        strategy = str(row.get("strategy", ""))
        ticker = str(row.get("ticker", ""))
        annual_return = row.get("annual_return")
        run_id = str(row.get("run_id", ""))

        if annual_return is None or pd.isna(annual_return):
            continue

        if float(annual_return) > return_threshold:
            hyp_id = generate_backtest_hypothesis(
                strategy=strategy,
                annual_return=float(annual_return),
                ticker=ticker,
                run_id=run_id,
                kb=kb,
                storage=storage,
            )
            if hyp_id:
                generated.append(hyp_id)

    logger.info(f"从回测记录生成 {len(generated)} 条假设")
    return generated
