"""Event schema consistency tests — all Event models share the canonical base."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime

from data.schema import Event as BaseEvent, Sentiment, Direction, OrderSide, Signal


class TestCanonicalEvent:
    def test_minimal_construction(self):
        e = BaseEvent(event_id="e1", event_type="test", symbol="600519",
                      timestamp=datetime.now(), detail="test event")
        assert e.event_id == "e1"
        assert e.symbol == "600519"
        assert e.sentiment == Sentiment.NEUTRAL
        assert e.confidence == 0.5
        assert e.company == ""
        assert e.impact_horizon == ""

    def test_full_construction(self):
        ts = datetime.now()
        e = BaseEvent(event_id="e2", event_type="earnings_beat", symbol="NVDA",
                      timestamp=ts, detail="Strong quarter", company="NVIDIA",
                      sentiment=Sentiment.POSITIVE, confidence=0.85,
                      source="reuters", tags=["tech", "semiconductor"],
                      impact_horizon="short")
        assert e.company == "NVIDIA"
        assert e.impact_horizon == "short"
        assert e.source == "reuters"

    def test_asdict_roundtrip(self):
        ts = datetime.now()
        e = BaseEvent(event_id="e3", event_type="rate_cut", symbol="000300",
                      timestamp=ts, detail="Rate cut 25bp", source="fed")
        d = asdict(e)
        restored = BaseEvent(**d)
        assert restored.event_id == e.event_id
        assert restored.symbol == e.symbol

    def test_sentiment_enum_values(self):
        assert Sentiment.POSITIVE.value == "positive"
        assert Sentiment.NEGATIVE.value == "negative"
        assert Sentiment.NEUTRAL.value == "neutral"


class TestNewsEvent:
    def test_news_event_inherits_base(self):
        from news.schema import Event as NewsEvent, NewsSource, SourceTier
        ts = datetime.now()
        src = NewsSource(url="https://example.com", source_name="test",
                         tier=SourceTier.TIER_1, title="Test", published_at=ts)
        ne = NewsEvent(event_id="n1", event_type="earnings_beat", symbol="NVDA",
                       timestamp=ts, detail="Beat", sources=[src])
        # Inherited fields
        assert ne.symbol == "NVDA"
        assert ne.company == ""
        assert ne.sentiment.value == "neutral"
        # Child-specific
        assert ne.source_count == 1
        assert ne.dedup_key == ""
        assert ne.max_tier == SourceTier.TIER_1

    def test_add_source_boost_confidence(self):
        from news.schema import Event as NewsEvent, NewsSource, SourceTier, TIER_WEIGHT
        ts = datetime.now()
        ne = NewsEvent(event_id="n2", event_type="earnings_beat", symbol="NVDA",
                       timestamp=ts, detail="Beat", confidence=0.5)
        for i in range(3):
            src = NewsSource(url=f"https://src{i}.com", source_name=f"src{i}",
                             tier=SourceTier.TIER_2, title=f"Title {i}", published_at=ts,
                             raw_id=str(i))
            ne.add_source(src)
        assert ne.source_count == 3
        assert ne.confidence > 0.5  # boosted by multi-source

    def test_dedup_rejects_duplicate_raw_id(self):
        from news.schema import Event as NewsEvent, NewsSource, SourceTier
        ts = datetime.now()
        ne = NewsEvent(event_id="n3", event_type="other", symbol="AAPL",
                       timestamp=ts, detail="dup test")
        src = NewsSource(url="https://x.com", source_name="x", tier=SourceTier.TIER_1,
                         title="X", published_at=ts, raw_id="dup1")
        ne.add_source(src)
        ne.add_source(src)  # same raw_id
        assert ne.source_count == 1  # not 2


class TestSignalContract:
    def test_signal_score_range(self):
        s = Signal(symbol="600519", timestamp=datetime.now(),
                   direction=Direction.LONG, strength="strong", score=0.8,
                   source="test")
        assert -1.0 <= s.score <= 1.0

    def test_signal_negative_score(self):
        s = Signal(symbol="600519", timestamp=datetime.now(),
                   direction=Direction.SHORT, strength="weak", score=-0.6,
                   source="test")
        assert s.score < 0

    def test_order_side_enum(self):
        assert OrderSide.BUY.value == "buy"
        assert OrderSide.SELL.value == "sell"
