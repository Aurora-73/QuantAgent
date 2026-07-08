"""执行 realism 模块（B4.3）

提供交易执行层面的 realism 校验与模拟：
  - 涨跌停限制：买入时拒绝涨停股、卖出时拒绝跌停股
  - 停牌检测：volume == 0 视为停牌，拒绝成交
  - 市场冲击：大单（> 日成交额 5%）按平方根模型追加滑点

设计原则：纯函数 + 可选模拟器，不修改现有 BacktestEngine。
回测主链路不受影响；调用方可通过 filter_signals 预过滤信号，
或用 simulate_with_realism 跑一个 realism-aware 的回测。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from loguru import logger


@dataclass
class RealismConfig:
    """执行 realism 配置。

    Attributes:
        price_limit_pct: 涨跌停幅度（普通股 0.10；ST 0.05；科创板/创业板 0.20）
        large_order_threshold: 大单定义——订单金额 > 该比例 * 日成交额
        impact_coefficient: 市场冲击系数（平方根模型 impact = coeff * sqrt(order/turnover)）
        base_slippage: 基础滑点（与 BacktestEngine 默认 0.001 一致）
        fees: 手续费率
    """
    price_limit_pct: float = 0.10
    large_order_threshold: float = 0.05
    impact_coefficient: float = 0.10
    base_slippage: float = 0.001
    fees: float = 0.001


DEFAULT_CONFIG = RealismConfig()


# ============================================================
# 单项检查
# ============================================================

def is_suspended(bar: pd.Series) -> bool:
    """停牌检测：当日成交量 == 0 视为停牌。"""
    vol = bar.get("volume", 0)
    try:
        return float(vol) == 0.0
    except (TypeError, ValueError):
        return True


def _pct_change(cur: float, prev: float) -> float:
    """安全计算涨跌幅；prev 为 0 或 None 时返回 0（无法判断）。"""
    if prev is None or prev == 0:
        return 0.0
    return (cur - prev) / abs(prev)


def at_upper_limit(bar: pd.Series, prev_close: float,
                   limit_pct: float = 0.10,
                   tol: float = 1e-6) -> bool:
    """是否触及涨停（涨跌幅 >= limit_pct）。"""
    close = bar.get("close", np.nan)
    if close is None or (isinstance(close, float) and np.isnan(close)):
        return False
    return _pct_change(float(close), prev_close) >= limit_pct - tol


def at_lower_limit(bar: pd.Series, prev_close: float,
                   limit_pct: float = 0.10,
                   tol: float = 1e-6) -> bool:
    """是否触及跌停（涨跌幅 <= -limit_pct）。"""
    close = bar.get("close", np.nan)
    if close is None or (isinstance(close, float) and np.isnan(close)):
        return False
    return _pct_change(float(close), prev_close) <= -(limit_pct - tol)


def check_tradable(bar: pd.Series,
                   prev_close: float,
                   side: str,
                   config: RealismConfig = None) -> tuple:
    """
    检查某 bar 是否可成交。

    Args:
        bar: 含 close/volume 的 OHLCV 行
        prev_close: 前一交易日收盘价
        side: "buy" 或 "sell"
        config: realism 配置

    Returns:
        (tradable, reason) — reason 为空串表示可成交，否则为拒绝原因。
        涨停可卖不可买；跌停可买不可卖。
    """
    config = config or DEFAULT_CONFIG

    if is_suspended(bar):
        return False, "停牌（volume=0）"

    if side == "buy" and at_upper_limit(bar, prev_close, config.price_limit_pct):
        return False, "涨停，无法买入"
    if side == "sell" and at_lower_limit(bar, prev_close, config.price_limit_pct):
        return False, "跌停，无法卖出"

    return True, ""


# ============================================================
# 市场冲击
# ============================================================

def compute_impact_slippage(order_value: float,
                            daily_turnover: float,
                            config: RealismConfig = None) -> float:
    """
    市场冲击滑点（平方根模型）。

    小单（< large_order_threshold * daily_turnover）不产生冲击，返回 0；
    大单返回 impact_coefficient * sqrt(order_value / daily_turnover)。
    """
    config = config or DEFAULT_CONFIG
    if daily_turnover is None or daily_turnover <= 0:
        return 0.0
    if order_value is None or order_value <= 0:
        return 0.0
    if order_value < config.large_order_threshold * daily_turnover:
        return 0.0
    ratio = order_value / daily_turnover
    return float(config.impact_coefficient * np.sqrt(ratio))


# ============================================================
# 信号过滤
# ============================================================

def filter_signals(entries: pd.Series,
                   exits: pd.Series,
                   ohlcv: pd.DataFrame,
                   config: RealismConfig = None) -> tuple:
    """
    按 realism 规则过滤不可交易日的信号。

    Args:
        entries: 买入信号 (bool Series，index 对齐 ohlcv)
        exits: 卖出信号 (bool Series)
        ohlcv: 含 close/volume/amount 列的 DataFrame
        config: realism 配置

    Returns:
        (entries_filtered, exits_filtered, stats)
        stats: {rejected_entries, rejected_exits, suspended_days,
                upper_limit_days, lower_limit_days}
    """
    config = config or DEFAULT_CONFIG
    entries_f = entries.copy()
    exits_f = exits.copy()

    prev_close = ohlcv["close"].shift(1)

    stats = {
        "rejected_entries": 0, "rejected_exits": 0,
        "suspended_days": 0, "upper_limit_days": 0, "lower_limit_days": 0,
    }

    for i in range(len(ohlcv)):
        bar = ohlcv.iloc[i]
        pc = prev_close.iloc[i]
        # 第一日无前收，无法判断涨跌停（_pct_change 返回 0 → 不会误判涨停）
        pc = 0.0 if (pc is None or (isinstance(pc, float) and np.isnan(pc))) else float(pc)

        if is_suspended(bar):
            stats["suspended_days"] += 1
            if entries_f.iloc[i]:
                entries_f.iloc[i] = False
                stats["rejected_entries"] += 1
            if exits_f.iloc[i]:
                exits_f.iloc[i] = False
                stats["rejected_exits"] += 1
            continue

        if at_upper_limit(bar, pc, config.price_limit_pct):
            stats["upper_limit_days"] += 1
            if entries_f.iloc[i]:
                entries_f.iloc[i] = False
                stats["rejected_entries"] += 1

        if at_lower_limit(bar, pc, config.price_limit_pct):
            stats["lower_limit_days"] += 1
            if exits_f.iloc[i]:
                exits_f.iloc[i] = False
                stats["rejected_exits"] += 1

    return entries_f, exits_f, stats


# ============================================================
# 可选模拟器（realism-aware 回测）
# ============================================================

def simulate_with_realism(ohlcv: pd.DataFrame,
                          entries: pd.Series,
                          exits: pd.Series,
                          init_cash: float = 1_000_000,
                          config: RealismConfig = None) -> dict:
    """
    realism-aware 回测模拟器（B4.3 可选路径）。

    应用三重 realism：
      1. 停牌日不成交
      2. 涨停拒买、跌停拒卖
      3. 大单按平方根模型追加滑点

    返回与 BacktestEngine.signal_backtest 相同结构的 dict（外加 realism_stats /
    avg_impact_slippage），便于与现有回测结果对比。

    Args:
        ohlcv: 含 close/volume/amount 列的 DataFrame
        entries/exits: 信号（index 对齐 ohlcv）
        init_cash: 初始资金
        config: realism 配置
    """
    config = config or DEFAULT_CONFIG

    entries_f, exits_f, stats = filter_signals(entries, exits, ohlcv, config)
    logger.info(f"realism 过滤: 拒买 {stats['rejected_entries']}, "
                f"拒卖 {stats['rejected_exits']}, "
                f"停牌 {stats['suspended_days']} 日, "
                f"涨停 {stats['upper_limit_days']} 日, "
                f"跌停 {stats['lower_limit_days']} 日")

    cash = init_cash
    shares = 0
    equity = []
    entry_value = 0.0
    trade_pnls = []
    impact_slippages = []

    for i in range(len(ohlcv)):
        bar = ohlcv.iloc[i]
        price = float(bar["close"])
        daily_turnover = float(bar.get("amount", 0) or 0)

        if entries_f.iloc[i] and shares == 0:
            order_value = cash  # 全仓买入
            impact = compute_impact_slippage(order_value, daily_turnover, config)
            impact_slippages.append(impact)
            buy_price = price * (1 + config.base_slippage + impact)
            shares = int(cash / (buy_price * (1 + config.fees)))
            entry_value = shares * buy_price * (1 + config.fees)
            cash -= entry_value

        elif exits_f.iloc[i] and shares > 0:
            order_value = shares * price
            impact = compute_impact_slippage(order_value, daily_turnover, config)
            impact_slippages.append(impact)
            sell_price = price * (1 - config.base_slippage - impact)
            exit_value = shares * sell_price * (1 - config.fees)
            trade_pnls.append(exit_value - entry_value)
            cash += exit_value
            shares = 0

        equity.append(cash + shares * price)

    equity = pd.Series(equity, index=ohlcv.index)
    total_return = float(equity.iloc[-1] / init_cash - 1) if len(equity) else 0.0
    returns = equity.pct_change().dropna()
    sharpe = (0.0 if returns.std() < 1e-10
              else float(returns.mean() / returns.std() * np.sqrt(252)))
    peak = equity.expanding().max()
    max_dd = float(((equity - peak) / peak).min()) if len(equity) else 0.0
    win_rate = (sum(1 for p in trade_pnls if p > 0) / len(trade_pnls)
                if trade_pnls else 0.0)

    return {
        "total_return": total_return,
        "annual_return": total_return,  # 简化，与 _simple_signal_backtest 一致
        "sharpe_ratio": sharpe,
        "max_drawdown": max_dd,
        "win_rate": float(win_rate),
        "trade_count": len(trade_pnls),
        "equity_curve": equity,
        "realism_stats": stats,
        "avg_impact_slippage": (float(np.mean(impact_slippages))
                                if impact_slippages else 0.0),
    }
