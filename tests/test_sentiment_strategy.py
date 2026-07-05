"""SentimentStrategy tests — sentiment signal, contrarian flip, aggregation."""
from __future__ import annotations

import pandas as pd
import pytest

from strategies.base import WeightVector, Direction
from strategies.sentiment.strategy import SentimentStrategy


def _make_social_context(bull_ratio=0.0, bear_ratio=0.0,
                         sentiment="neutral", confidence=0.8,
                         tickers=None):
    return {
        "ticker": "600519",
        "sentiment": {
            "social": {
                "sentiment": sentiment,
                "confidence": confidence,
                "bull_ratio": bull_ratio,
                "bear_ratio": bear_ratio,
                "tickers": tickers or ["600519"],
            },
        },
    }


class TestSignalGeneration:
    def test_bullish_social_produces_buy(self):
        strat = SentimentStrategy()
        signals = strat.generate_signal(
            pd.DataFrame(), _make_social_context(bull_ratio=0.7, sentiment="bullish")
        )
        assert len(signals) >= 1
        for s in signals:
            assert s.direction == Direction.LONG
            assert 0 < s.score <= 0.6  # capped by max_signal_strength

    def test_bearish_social_produces_sell(self):
        strat = SentimentStrategy()
        signals = strat.generate_signal(
            pd.DataFrame(), _make_social_context(bear_ratio=0.7, sentiment="bearish")
        )
        assert len(signals) >= 1
        for s in signals:
            assert s.direction == Direction.SHORT

    def test_no_sentiment_returns_empty(self):
        strat = SentimentStrategy()
        signals = strat.generate_signal(pd.DataFrame(), {"ticker": "600519"})
        assert signals == []

    def test_empty_sentiment_returns_empty(self):
        strat = SentimentStrategy()
        signals = strat.generate_signal(pd.DataFrame(), {
            "ticker": "600519", "sentiment": {},
        })
        assert signals == []

    def test_low_confidence_is_filtered(self):
        strat = SentimentStrategy()
        signals = strat.generate_signal(
            pd.DataFrame(),
            _make_social_context(bull_ratio=0.7, sentiment="bullish", confidence=0.1),
        )
        assert signals == []


class TestContrarianMode:
    def test_extreme_bull_flips_to_bear(self):
        """bull_ratio > 80% triggers contrarian flip → bearish."""
        strat = SentimentStrategy()
        signals = strat.generate_signal(
            pd.DataFrame(),
            _make_social_context(bull_ratio=0.9, sentiment="bullish"),
        )
        if signals:
            # Signal may be empty if flipped score rounds to zero
            for s in signals:
                assert s.direction == Direction.SHORT  # flipped

    def test_extreme_bear_flips_to_bull(self):
        """bear_ratio > 80% triggers contrarian flip → bullish."""
        strat = SentimentStrategy()
        signals = strat.generate_signal(
            pd.DataFrame(),
            _make_social_context(bear_ratio=0.9, sentiment="bearish"),
        )
        if signals:
            for s in signals:
                assert s.direction == Direction.LONG  # flipped

    def test_moderate_sentiment_no_flip(self):
        """bull_ratio=0.6 should not trigger contrarian."""
        strat = SentimentStrategy()
        signals = strat.generate_signal(
            pd.DataFrame(),
            _make_social_context(bull_ratio=0.6, sentiment="bullish"),
        )
        for s in signals:
            assert s.direction == Direction.LONG  # not flipped


class TestWeightVector:
    def test_weight_vector_from_sentiment(self):
        strat = SentimentStrategy()
        wv = strat.generate_weight_vector(
            pd.DataFrame(), _make_social_context(bull_ratio=0.7, sentiment="bullish")
        )
        assert isinstance(wv, WeightVector)
        assert "600519" in wv.weights
        assert 0 < wv.confidence <= 1.0
        assert wv.source == "sentiment"

    def test_weight_vector_empty_sentiment_zero(self):
        strat = SentimentStrategy()
        wv = strat.generate_weight_vector(pd.DataFrame(), {"ticker": "600519"})
        assert wv.confidence == 0.0


class TestConfig:
    def test_max_signal_strength_default_is_0_6(self):
        strat = SentimentStrategy()
        assert strat.max_signal_strength == 0.6

    def test_contrarian_defaults_to_true(self):
        strat = SentimentStrategy()
        assert strat.contrarian_mode is True
