"""Tests for B4.3: 执行 Realism (strategies/execution.py).

Covers:
  - is_suspended: volume==0 检测
  - at_upper_limit / at_lower_limit: 涨跌停判定
  - check_tradable: 涨停拒买、跌停拒卖、停牌拒全部、正常放行
  - compute_impact_slippage: 小单 0、大单 > 0、随订单规模递增、零成交额 0
  - filter_signals: 过滤统计正确、保留正常信号
  - simulate_with_realism: 停牌日不成交、大单产生冲击滑点、返回结构完整
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from strategies.execution import (
    DEFAULT_CONFIG,
    RealismConfig,
    at_lower_limit,
    at_upper_limit,
    check_tradable,
    compute_impact_slippage,
    filter_signals,
    is_suspended,
    simulate_with_realism,
)


# ============================================================
# Helpers
# ============================================================

def _bar(close=100.0, volume=1_000_000, amount=None):
    """构造单根 OHLCV bar (pd.Series)。"""
    if amount is None:
        amount = close * volume
    return pd.Series({"close": close, "volume": volume, "amount": amount})


def _ohlcv(closes, volumes=None, amounts=None):
    """构造 OHLCV DataFrame。"""
    n = len(closes)
    if volumes is None:
        volumes = [1_000_000] * n
    if amounts is None:
        amounts = [c * v for c, v in zip(closes, volumes)]
    dates = pd.date_range("2025-01-01", periods=n, freq="D")
    return pd.DataFrame({
        "close": closes, "volume": volumes, "amount": amounts,
    }, index=dates)


# ============================================================
# is_suspended
# ============================================================

class TestIsSuspended:
    def test_zero_volume_is_suspended(self):
        assert is_suspended(_bar(close=100.0, volume=0)) is True

    def test_normal_volume_not_suspended(self):
        assert is_suspended(_bar(close=100.0, volume=1_000_000)) is False

    def test_missing_volume_treated_as_suspended(self):
        # 无 volume 字段 → 安全起见视为停牌
        assert is_suspended(pd.Series({"close": 100.0})) is True


# ============================================================
# at_upper_limit / at_lower_limit
# ============================================================

class TestPriceLimit:
    def test_upper_limit_exactly_10pct(self):
        bar = _bar(close=11.0)
        assert at_upper_limit(bar, prev_close=10.0, limit_pct=0.10) is True

    def test_upper_limit_below_threshold(self):
        bar = _bar(close=10.9)
        assert at_upper_limit(bar, prev_close=10.0, limit_pct=0.10) is False

    def test_upper_limit_st_5pct(self):
        bar = _bar(close=10.5)
        assert at_upper_limit(bar, prev_close=10.0, limit_pct=0.05) is True

    def test_lower_limit_exactly_10pct(self):
        bar = _bar(close=9.0)
        assert at_lower_limit(bar, prev_close=10.0, limit_pct=0.10) is True

    def test_lower_limit_above_threshold(self):
        bar = _bar(close=9.1)
        assert at_lower_limit(bar, prev_close=10.0, limit_pct=0.10) is False

    def test_star_market_20pct(self):
        bar = _bar(close=12.0)
        assert at_upper_limit(bar, prev_close=10.0, limit_pct=0.20) is True
        assert at_upper_limit(bar, prev_close=10.0, limit_pct=0.10) is True  # 也超过 10%


# ============================================================
# check_tradable
# ============================================================

class TestCheckTradable:
    def test_suspended_rejected_both_sides(self):
        bar = _bar(close=100.0, volume=0)
        ok_buy, reason_buy = check_tradable(bar, 99.0, "buy")
        ok_sell, reason_sell = check_tradable(bar, 99.0, "sell")
        assert ok_buy is False and "停牌" in reason_buy
        assert ok_sell is False and "停牌" in reason_sell

    def test_buy_at_upper_limit_rejected(self):
        bar = _bar(close=11.0)  # +10% 涨停
        ok, reason = check_tradable(bar, 10.0, "buy")
        assert ok is False and "涨停" in reason

    def test_sell_at_upper_limit_allowed(self):
        # 涨停可卖（有人挂买单）
        bar = _bar(close=11.0)
        ok, reason = check_tradable(bar, 10.0, "sell")
        assert ok is True and reason == ""

    def test_sell_at_lower_limit_rejected(self):
        bar = _bar(close=9.0)  # -10% 跌停
        ok, reason = check_tradable(bar, 10.0, "sell")
        assert ok is False and "跌停" in reason

    def test_buy_at_lower_limit_allowed(self):
        # 跌停可买（有人挂卖单）
        bar = _bar(close=9.0)
        ok, reason = check_tradable(bar, 10.0, "buy")
        assert ok is True and reason == ""

    def test_normal_day_allowed_both_sides(self):
        bar = _bar(close=10.5)  # +5%
        assert check_tradable(bar, 10.0, "buy") == (True, "")
        assert check_tradable(bar, 10.0, "sell") == (True, "")


# ============================================================
# compute_impact_slippage
# ============================================================

class TestComputeImpactSlippage:
    def test_small_order_zero_impact(self):
        # 订单 = 1% 日成交额 < 5% 阈值 → 0
        impact = compute_impact_slippage(order_value=10_000,
                                         daily_turnover=1_000_000)
        assert impact == 0.0

    def test_large_order_positive_impact(self):
        # 订单 = 20% 日成交额 > 5% 阈值 → > 0
        impact = compute_impact_slippage(order_value=200_000,
                                         daily_turnover=1_000_000)
        assert impact > 0.0
        # 平方根模型: 0.1 * sqrt(0.2) ≈ 0.0447
        assert impact == pytest.approx(0.1 * np.sqrt(0.2), rel=1e-6)

    def test_impact_scales_with_order_size(self):
        turnover = 1_000_000
        small = compute_impact_slippage(100_000, turnover)   # 10%
        large = compute_impact_slippage(500_000, turnover)   # 50%
        assert large > small > 0

    def test_zero_turnover_returns_zero(self):
        # 停牌日（turnover=0）→ 0，避免除零
        assert compute_impact_slippage(100_000, 0) == 0.0

    def test_threshold_boundary(self):
        # 订单正好 = 5% 阈值 → 视为大单（< 严格小于，等于阈值不算小单）→ 产生冲击
        impact = compute_impact_slippage(order_value=50_000,
                                         daily_turnover=1_000_000)
        assert impact > 0.0
        assert impact == pytest.approx(0.1 * np.sqrt(0.05), rel=1e-6)

    def test_just_below_threshold_zero(self):
        # 订单略低于 5% 阈值 → 小单 → 0
        impact = compute_impact_slippage(order_value=49_999,
                                         daily_turnover=1_000_000)
        assert impact == 0.0

    def test_custom_config_changes_coefficient(self):
        cfg = RealismConfig(impact_coefficient=0.5)
        impact = compute_impact_slippage(200_000, 1_000_000, config=cfg)
        # 0.5 * sqrt(0.2)
        assert impact == pytest.approx(0.5 * np.sqrt(0.2), rel=1e-6)


# ============================================================
# filter_signals
# ============================================================

class TestFilterSignals:
    def test_rejects_suspended_entry_and_exit(self):
        # day 1 停牌（volume=0），同时有入场和出场信号
        ohlcv = _ohlcv([100.0, 100.0, 100.0],
                       volumes=[1_000_000, 0, 1_000_000])
        entries = pd.Series([False, True, False], index=ohlcv.index)
        exits = pd.Series([False, True, False], index=ohlcv.index)

        e_f, x_f, stats = filter_signals(entries, exits, ohlcv)

        assert e_f.iloc[1] is False or e_f.iloc[1] == False  # rejected
        assert x_f.iloc[1] is False or x_f.iloc[1] == False
        assert stats["suspended_days"] == 1
        assert stats["rejected_entries"] == 1
        assert stats["rejected_exits"] == 1

    def test_rejects_upper_limit_entry_only(self):
        # day 1 涨停（close 110 vs prev 100），有入场信号；出场信号应保留
        ohlcv = _ohlcv([100.0, 110.0, 100.0])
        entries = pd.Series([False, True, False], index=ohlcv.index)
        exits = pd.Series([False, True, False], index=ohlcv.index)

        e_f, x_f, stats = filter_signals(entries, exits, ohlcv)

        assert bool(e_f.iloc[1]) is False  # 入场被拒
        assert bool(x_f.iloc[1]) is True   # 出场保留（涨停可卖）
        assert stats["upper_limit_days"] == 1
        assert stats["rejected_entries"] == 1
        assert stats["rejected_exits"] == 0

    def test_rejects_lower_limit_exit_only(self):
        # day 1 跌停（close 90 vs prev 100），有出场信号；入场信号应保留
        ohlcv = _ohlcv([100.0, 90.0, 100.0])
        entries = pd.Series([False, True, False], index=ohlcv.index)
        exits = pd.Series([False, True, False], index=ohlcv.index)

        e_f, x_f, stats = filter_signals(entries, exits, ohlcv)

        assert bool(e_f.iloc[1]) is True   # 入场保留（跌停可买）
        assert bool(x_f.iloc[1]) is False  # 出场被拒
        assert stats["lower_limit_days"] == 1
        assert stats["rejected_entries"] == 0
        assert stats["rejected_exits"] == 1

    def test_normal_signals_preserved(self):
        ohlcv = _ohlcv([100.0, 102.0, 101.0])  # 无涨跌停、无停牌
        entries = pd.Series([True, False, True], index=ohlcv.index)
        exits = pd.Series([False, True, False], index=ohlcv.index)

        e_f, x_f, stats = filter_signals(entries, exits, ohlcv)

        assert e_f.equals(entries)
        assert x_f.equals(exits)
        assert stats["rejected_entries"] == 0
        assert stats["rejected_exits"] == 0

    def test_stats_count_multiple_days(self):
        # 构造清晰的涨跌停/停牌日：
        #   day0: 100 (基准，无前收)
        #   day1: 110 vs 100  → +10% 涨停
        #   day2: 100 vs 110  → -9.09% 非（不足 10%）
        #   day3: 90  vs 100  → -10% 跌停
        #   day4: 100 vs 90   → +11.1% 涨停 (>=10%)
        #   day5: volume=0    → 停牌
        closes = [100.0, 110.0, 100.0, 90.0, 100.0, 100.0]
        volumes = [1e6, 1e6, 1e6, 1e6, 1e6, 0]
        ohlcv = _ohlcv(closes, volumes=volumes)
        entries = pd.Series([True]*6, index=ohlcv.index)
        exits = pd.Series([True]*6, index=ohlcv.index)

        _, _, stats = filter_signals(entries, exits, ohlcv)

        assert stats["upper_limit_days"] == 2   # day1, day4
        assert stats["lower_limit_days"] == 1   # day3
        assert stats["suspended_days"] == 1     # day5
        # 入场被拒：day1(涨停)、day4(涨停)、day5(停牌) = 3
        assert stats["rejected_entries"] == 3
        # 出场被拒：day3(跌停)、day5(停牌) = 2
        assert stats["rejected_exits"] == 2


# ============================================================
# simulate_with_realism
# ============================================================

class TestSimulateWithRealism:
    def test_returns_expected_keys(self):
        ohlcv = _ohlcv([100.0, 101.0, 102.0, 101.0])
        entries = pd.Series([True, False, False, True], index=ohlcv.index)
        exits = pd.Series([False, False, True, False], index=ohlcv.index)

        result = simulate_with_realism(ohlcv, entries, exits, init_cash=100_000)

        for key in ("total_return", "annual_return", "sharpe_ratio",
                    "max_drawdown", "win_rate", "trade_count",
                    "equity_curve", "realism_stats", "avg_impact_slippage"):
            assert key in result, f"missing key: {key}"

    def test_suspended_day_prevents_trade(self):
        # day 0 入场信号但 day 0 停牌 → 不应成交，trade_count=0
        ohlcv = _ohlcv([100.0, 101.0, 102.0],
                       volumes=[0, 1_000_000, 1_000_000])
        entries = pd.Series([True, False, False], index=ohlcv.index)
        exits = pd.Series([False, False, True], index=ohlcv.index)

        result = simulate_with_realism(ohlcv, entries, exits, init_cash=100_000)

        assert result["trade_count"] == 0
        assert result["realism_stats"]["suspended_days"] == 1
        assert result["realism_stats"]["rejected_entries"] == 1

    def test_upper_limit_blocks_buy(self):
        # day 0 涨停（110 vs 前一日... 需要前一日数据）
        # day 0: 100 (基准), day 1: 110 (涨停), 入场信号在 day 1 → 被拒
        ohlcv = _ohlcv([100.0, 110.0, 110.0])
        entries = pd.Series([False, True, False], index=ohlcv.index)
        exits = pd.Series([False, False, True], index=ohlcv.index)

        result = simulate_with_realism(ohlcv, entries, exits, init_cash=100_000)

        assert result["realism_stats"]["upper_limit_days"] == 1
        assert result["realism_stats"]["rejected_entries"] == 1
        # 入场被拒 → 后续无持仓 → 无交易
        assert result["trade_count"] == 0

    def test_large_order_produces_impact_slippage(self):
        # 构造一个会成交的场景，且订单金额 > 5% 日成交额
        # 日成交额 = close * volume；init_cash=100_000，volume 设小让成交额小
        ohlcv = _ohlcv([100.0, 101.0, 105.0, 104.0],
                       volumes=[1_000, 1_000, 1_000, 1_000])  # 成交额 ~10万
        entries = pd.Series([True, False, False, False], index=ohlcv.index)
        exits = pd.Series([False, False, False, True], index=ohlcv.index)

        result = simulate_with_realism(ohlcv, entries, exits, init_cash=100_000)

        # 订单 100_000 vs 日成交额 ~100_000 → ratio ~1 → 大单
        assert result["trade_count"] == 1
        assert result["avg_impact_slippage"] > 0.0

    def test_small_order_zero_impact(self):
        # 日成交额远大于订单 → 小单 → 无冲击
        ohlcv = _ohlcv([100.0, 101.0, 105.0, 104.0],
                       volumes=[10_000_000]*4)  # 成交额 ~10亿
        entries = pd.Series([True, False, False, False], index=ohlcv.index)
        exits = pd.Series([False, False, False, True], index=ohlcv.index)

        result = simulate_with_realism(ohlcv, entries, exits, init_cash=100_000)

        assert result["trade_count"] == 1
        assert result["avg_impact_slippage"] == 0.0

    def test_no_trades_returns_zero(self):
        ohlcv = _ohlcv([100.0, 101.0, 102.0])
        entries = pd.Series([False, False, False], index=ohlcv.index)
        exits = pd.Series([False, False, False], index=ohlcv.index)

        result = simulate_with_realism(ohlcv, entries, exits, init_cash=100_000)

        assert result["trade_count"] == 0
        assert result["total_return"] == 0.0
        assert result["avg_impact_slippage"] == 0.0

    def test_custom_config_applied(self):
        # 用 ST 配置（5% 涨跌停），close=10.5 应被判涨停
        ohlcv = _ohlcv([100.0, 105.0, 100.0])  # day1: +5%
        entries = pd.Series([False, True, False], index=ohlcv.index)
        exits = pd.Series([False, False, True], index=ohlcv.index)

        st_cfg = RealismConfig(price_limit_pct=0.05)
        result = simulate_with_realism(ohlcv, entries, exits,
                                       init_cash=100_000, config=st_cfg)

        # day1 +5% 在 ST 配置下是涨停 → 入场被拒
        assert result["realism_stats"]["upper_limit_days"] == 1
        assert result["realism_stats"]["rejected_entries"] == 1
