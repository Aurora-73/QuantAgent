"""
Market regime detector — identifies the current market state.

5 regimes:
  - trend:          Strong directional movement (ADX-like metric > threshold)
  - oscillating:    Range-bound, low directional movement
  - extreme_vol:    Realized vol > 2x long-term average
  - earnings_season: Date-based (Mar-Apr Q4 reports, Aug-Sep H1 reports)
  - policy_window:  Date-based (NPC/CPPCC sessions, PBOC meetings, etc.)

Usage:
    detector = MarketRegimeDetector()
    regime, confidence = detector.detect(index_df)
"""
from datetime import date, datetime
from enum import Enum
from typing import Optional

import numpy as np
import pandas as pd
from loguru import logger


class MarketRegime(Enum):
    TREND = "trend"
    OSCILLATING = "oscillating"
    EXTREME_VOL = "extreme_volatility"
    EARNINGS_SEASON = "earnings_season"
    POLICY_WINDOW = "policy_window"


class MarketRegimeDetector:
    """Rule-based market regime detection using index data."""

    def __init__(self,
                 trend_adx_threshold: float = 25.0,
                 vol_lookback_long: int = 60,
                 vol_lookback_short: int = 20,
                 vol_spike_multiplier: float = 2.0,
                 osc_max_range_pct: float = 0.03):
        self.trend_adx_threshold = trend_adx_threshold
        self.vol_lookback_long = vol_lookback_long
        self.vol_lookback_short = vol_lookback_short
        self.vol_spike_multiplier = vol_spike_multiplier
        self.osc_max_range_pct = osc_max_range_pct

    def detect(self, df: pd.DataFrame,
               target_date: date = None) -> tuple[MarketRegime, float]:
        """
        Detect market regime from index OHLCV data.

        Args:
            df: OHLCV DataFrame for market index
            target_date: Specific date to detect (default: last row)

        Returns:
            (MarketRegime, confidence 0-1)
        """
        if df.empty or len(df) < self.vol_lookback_long:
            logger.warning("Insufficient data for regime detection, defaulting to oscillating")
            return MarketRegime.OSCILLATING, 0.3

        target_date = target_date or date.today()

        # 1. Check date-based regimes first (they override technical)
        cal_regime, cal_conf = self._check_calendar_regime(target_date)
        if cal_regime is not None:
            return cal_regime, cal_conf

        # 2. Check extreme volatility
        vol_regime, vol_conf = self._check_extreme_vol(df)
        if vol_regime is not None:
            return vol_regime, vol_conf

        # 3. Trend vs oscillating (ADX-based)
        return self._check_trend_vs_oscillating(df)

    def _check_calendar_regime(self, target_date: date) -> tuple[Optional[MarketRegime], float]:
        """Check if current date falls in a calendar-based regime."""
        month = target_date.month
        day = target_date.day

        # China earnings seasons
        # Q4 + annual reports: Jan 1 - Apr 30
        if (month == 1 and day >= 1) or month in (2, 3) or (month == 4 and day <= 30):
            return MarketRegime.EARNINGS_SEASON, 0.85

        # H1 reports: Jul 1 - Aug 31
        if month == 7 or month == 8:
            return MarketRegime.EARNINGS_SEASON, 0.80

        # Policy windows (NPC/CPPCC "Two Sessions": early March)
        if month == 3 and day <= 15:
            return MarketRegime.POLICY_WINDOW, 0.75

        # Central Economic Work Conference: mid-December
        if month == 12 and 10 <= day <= 25:
            return MarketRegime.POLICY_WINDOW, 0.70

        # Q3 PBOC monetary policy report: mid-November
        if month == 11 and 10 <= day <= 20:
            return MarketRegime.POLICY_WINDOW, 0.65

        return None, 0.0

    def _check_extreme_vol(self, df: pd.DataFrame) -> tuple[Optional[MarketRegime], float]:
        """Check for extreme volatility regime."""
        returns = df["close"].pct_change().dropna()

        if len(returns) < self.vol_lookback_long:
            return None, 0.0

        short_vol = returns.iloc[-self.vol_lookback_short:].std() * np.sqrt(252)
        long_vol = returns.iloc[-self.vol_lookback_long:].std() * np.sqrt(252)

        if long_vol < 1e-8:
            return None, 0.0

        ratio = short_vol / long_vol

        if ratio > self.vol_spike_multiplier:
            conf = min(ratio / 4.0, 1.0)  # ratio=2→0.5, ratio=4→1.0
            return MarketRegime.EXTREME_VOL, conf

        return None, 0.0

    def _check_trend_vs_oscillating(self, df: pd.DataFrame) -> tuple[MarketRegime, float]:
        """ADX-based trend vs oscillating detection."""
        adx = self._calc_adx(df)

        if adx is None or np.isnan(adx):
            return MarketRegime.OSCILLATING, 0.4

        # Check range-bound condition: Donchian channel width
        high_n = df["high"].iloc[-20:].max()
        low_n = df["low"].iloc[-20:].min()
        close_last = df["close"].iloc[-1]
        range_pct = (high_n - low_n) / close_last if close_last > 0 else 0

        if adx > self.trend_adx_threshold and range_pct > self.osc_max_range_pct:
            conf = min((adx - self.trend_adx_threshold) / 30.0 + 0.5, 0.95)
            return MarketRegime.TREND, conf
        else:
            conf = max(0.35, 0.7 - adx / 50.0)
            return MarketRegime.OSCILLATING, conf

    def _calc_adx(self, df: pd.DataFrame, period: int = 14) -> Optional[float]:
        """Calculate ADX-like trend strength indicator."""
        if len(df) < period + 1:
            return None

        high = df["high"]
        low = df["low"]
        close = df["close"]

        up_move = high.diff()
        down_move = -low.diff()

        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)

        tr = pd.concat([
            high - low,
            (high - close.shift(1)).abs(),
            (low - close.shift(1)).abs(),
        ], axis=1).max(axis=1)

        atr = tr.rolling(period).mean()
        plus_di = 100 * pd.Series(plus_dm, index=df.index).rolling(period).mean() / atr
        minus_di = 100 * pd.Series(minus_dm, index=df.index).rolling(period).mean() / atr

        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 1e-8)
        adx = dx.rolling(period).mean()

        return float(adx.iloc[-1]) if not pd.isna(adx.iloc[-1]) else None

    def get_weight_adjustments(self, regime: MarketRegime) -> dict:
        """Get source weight adjustments for a given regime."""
        adjustments = {
            MarketRegime.TREND: {
                "market_data": 0.35, "factor_signals": 0.35,
                "news_events": 0.15, "wiki": 0.10, "facts": 0.05,
            },
            MarketRegime.OSCILLATING: {
                "market_data": 0.30, "factor_signals": 0.25,
                "news_events": 0.30, "wiki": 0.10, "facts": 0.05,
            },
            MarketRegime.EXTREME_VOL: {
                "market_data": 0.25, "factor_signals": 0.20,
                "news_events": 0.35, "wiki": 0.15, "facts": 0.05,
            },
            MarketRegime.EARNINGS_SEASON: {
                "market_data": 0.30, "factor_signals": 0.25,
                "news_events": 0.35, "wiki": 0.05, "facts": 0.05,
            },
            MarketRegime.POLICY_WINDOW: {
                "market_data": 0.25, "factor_signals": 0.15,
                "news_events": 0.40, "wiki": 0.15, "facts": 0.05,
            },
        }
        return adjustments.get(regime, adjustments[MarketRegime.OSCILLATING])

    def get_regime_label_cn(self, regime: MarketRegime) -> str:
        labels = {
            MarketRegime.TREND: "趋势市",
            MarketRegime.OSCILLATING: "震荡市",
            MarketRegime.EXTREME_VOL: "极端波动",
            MarketRegime.EARNINGS_SEASON: "财报季",
            MarketRegime.POLICY_WINDOW: "政策窗口",
        }
        return labels.get(regime, "未知")
