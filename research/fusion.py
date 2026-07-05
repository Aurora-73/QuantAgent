"""
FusionEngine — multi-source data fusion with dynamic weighting.

Collects data from 5 sources:
  1. Market data (行情)      — price/volume from AKShare
  2. Factor signals (因子)    — computed by FactorEngine
  3. News events (新闻)       — from EventExtractor
  4. Wiki methodology (Wiki)  — from WikiRetriever
  5. Historical facts (事实)  — from FactStore

Applies dynamic weights based on market regime, data quality, and
time decay. Resolves conflicts between sources with documented rules.

Usage:
    engine = FusionEngine()
    snapshot = engine.collect(ticker="600519", target_date=date.today())
"""
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

import pandas as pd
from loguru import logger

from configs.settings import settings


@dataclass
class SourceQuality:
    """Per-source quality assessment."""
    score: float = 1.0          # 0-1 quality score
    freshness: float = 1.0      # 0-1 time decay
    completeness: float = 1.0   # 0-1 data coverage
    note: str = ""


@dataclass
class MarketSnapshot:
    """Unified output of FusionEngine — the system's single view of current state."""
    ticker: str
    date: str
    regime: str = "unknown"
    regime_confidence: float = 0.0

    # Source availability flags
    has_price: bool = False
    has_factors: bool = False
    has_news: bool = False
    has_wiki: bool = False
    has_facts: bool = False

    # Aggregated signals
    direction: str = "neutral"   # bullish / bearish / neutral
    strength: str = "weak"       # strong / moderate / weak
    confidence: float = 0.0

    # Detailed data
    price_data: dict = field(default_factory=dict)
    factor_data: dict = field(default_factory=dict)
    news_events: list[dict] = field(default_factory=list)
    wiki_refs: list[dict] = field(default_factory=list)
    facts: list[dict] = field(default_factory=list)

    # Meta
    source_weights: dict = field(default_factory=dict)
    source_qualities: dict[str, SourceQuality] = field(default_factory=dict)
    conflicts: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class FusionEngine:
    """
    Multi-source data fusion engine.

    Implements:
      - Dynamic weight adjustment per market regime
      - Source quality assessment
      - Conflict detection and resolution
      - Intelligence-data fusion rules (source: fengyezi intelligence.py)
    """

    def __init__(self):
        # Default base weights
        self.base_weights = {
            "market_data": 0.40,
            "factor_signals": 0.30,
            "news_events": 0.15,
            "wiki_methodology": 0.10,
            "historical_facts": 0.05,
        }
        self._regime_detector = None
        self._wiki_retriever = None
        self._fact_store = None

    @property
    def regime_detector(self):
        if self._regime_detector is None:
            from research.regime_detector import MarketRegimeDetector
            self._regime_detector = MarketRegimeDetector()
        return self._regime_detector

    @property
    def wiki_retriever(self):
        if self._wiki_retriever is None:
            from knowledge.wiki_retriever import WikiRetriever
            self._wiki_retriever = WikiRetriever()
        return self._wiki_retriever

    @property
    def fact_store(self):
        if self._fact_store is None:
            from data.market_fact import FactStore
            self._fact_store = FactStore()
        return self._fact_store

    def collect(self, ticker: str, target_date: date = None,
                price_df: pd.DataFrame = None,
                factor_df: pd.DataFrame = None,
                news_events: list[dict] = None,
                wiki_query: str = None,
                extra_context: dict = None) -> MarketSnapshot:
        """
        Collect and fuse data from all available sources.

        Args:
            ticker: Stock ticker
            target_date: Target analysis date
            price_df: Pre-loaded price data (optional)
            factor_df: Pre-loaded factor data (optional)
            news_events: Pre-loaded news events (optional)
            wiki_query: Query for wiki retrieval
            extra_context: Additional context for signal aggregation

        Returns:
            MarketSnapshot with fused data and signals
        """
        target_date = target_date or date.today()
        date_str = target_date.isoformat()

        snapshot = MarketSnapshot(ticker=ticker, date=date_str)

        # ---- Step 1: Determine market regime (sets weights) ----
        self._detect_regime(snapshot, price_df)

        # ---- Step 2: Collect each source ----
        self._collect_price(snapshot, ticker, price_df)
        self._collect_factors(snapshot, ticker, factor_df)
        self._collect_news(snapshot, ticker, news_events)
        self._collect_wiki(snapshot, ticker, wiki_query,
                           extra_context.get("regime") if extra_context else None)
        self._collect_facts(snapshot, ticker, target_date)

        # ---- Step 3: Assess source quality ----
        self._assess_quality(snapshot)

        # ---- Step 4: Adjust weights dynamically ----
        self._adjust_weights(snapshot)

        # ---- Step 5: Resolve conflicts ----
        self._resolve_conflicts(snapshot)

        # ---- Step 6: Aggregate signals ----
        self._aggregate_signals(snapshot)

        logger.info(f"Fusion complete for {ticker}: direction={snapshot.direction}, "
                    f"confidence={snapshot.confidence:.2f}")
        return snapshot

    # ============================================================
    # Step 1: Regime
    # ============================================================

    def _detect_regime(self, snapshot: MarketSnapshot, price_df: pd.DataFrame = None):
        """Detect market regime from price data or default."""
        if price_df is not None and not price_df.empty and len(price_df) > 60:
            try:
                regime_enum, conf = self.regime_detector.detect(price_df)
                snapshot.regime = regime_enum.value
                snapshot.regime_confidence = conf
                logger.debug(f"Regime detected: {snapshot.regime} ({conf:.2f})")
                return
            except Exception as e:
                logger.warning(f"Regime detection failed: {e}")

        snapshot.regime = "unknown"
        snapshot.regime_confidence = 0.3

    # ============================================================
    # Step 2: Collect
    # ============================================================

    def _collect_price(self, snapshot: MarketSnapshot, ticker: str,
                       price_df: pd.DataFrame = None):
        """Collect and normalize price data."""
        if price_df is not None and not price_df.empty:
            snapshot.has_price = True
            latest = price_df.iloc[-1]
            snapshot.price_data = {
                "close": float(latest.get("close", 0)),
                "open": float(latest.get("open", 0)),
                "high": float(latest.get("high", 0)),
                "low": float(latest.get("low", 0)),
                "volume": float(latest.get("volume", 0)),
                "pct_change": float(latest.get("pct_change", 0)) if "pct_change" in price_df.columns else 0,
            }
            # Compute additional stats
            if len(price_df) >= 2:
                prev_close = float(price_df.iloc[-2].get("close", snapshot.price_data["close"]))
                if prev_close > 0:
                    snapshot.price_data["pct_change"] = (
                        snapshot.price_data["close"] / prev_close - 1
                    )

    def _collect_factors(self, snapshot: MarketSnapshot, ticker: str,
                         factor_df: pd.DataFrame = None):
        """Collect and normalize factor signals."""
        if factor_df is not None and not factor_df.empty:
            snapshot.has_factors = True
            latest = factor_df.iloc[-1]
            factor_cols = [c for c in factor_df.columns
                          if c not in ("open", "high", "low", "close", "volume",
                                       "amount", "pct_change", "turnover")]
            for col in factor_cols:
                val = latest.get(col)
                if val is not None and not (isinstance(val, float) and pd.isna(val)):
                    snapshot.factor_data[col] = float(val)

    def _collect_news(self, snapshot: MarketSnapshot, ticker: str,
                      news_events: list[dict] = None):
        """Collect relevant news events."""
        if news_events:
            snapshot.has_news = True
            # Filter events relevant to this ticker or market-wide
            for evt in news_events:
                evt_ticker = evt.get("ticker", "")
                if not evt_ticker or evt_ticker == ticker or evt_ticker == "":
                    snapshot.news_events.append(evt)

    def _collect_wiki(self, snapshot: MarketSnapshot, ticker: str,
                      wiki_query: str = None, regime: str = None):
        """Retrieve relevant wiki methodologies."""
        query = wiki_query or f"{ticker} {regime or ''}"
        try:
            results = self.wiki_retriever.search(query, regime=regime, top_k=3)
            if results:
                snapshot.has_wiki = True
                for entry, score in results:
                    snapshot.wiki_refs.append({
                        "title": entry.title,
                        "type": entry.type,
                        "score": round(score, 3),
                        "tags": entry.tags,
                    })
        except Exception as e:
            logger.warning(f"Wiki retrieval failed: {e}")

    def _collect_facts(self, snapshot: MarketSnapshot, ticker: str,
                       target_date: date):
        """Collect historical facts for the ticker."""
        try:
            facts = self.fact_store.query(
                ticker=ticker,
                start_date=target_date.replace(month=target_date.month - 1).isoformat()
                if target_date.month > 1
                else target_date.replace(year=target_date.year - 1, month=12).isoformat(),
                limit=20,
            )
            if facts:
                snapshot.has_facts = True
                for f in facts:
                    snapshot.facts.append({
                        "fact_id": f.fact_id,
                        "fact_type": f.fact_type,
                        "description": f.description,
                        "value": f.value,
                        "confidence": f.confidence,
                        "verified": f.verified,
                    })
        except Exception as e:
            logger.warning(f"Fact retrieval failed: {e}")

    # ============================================================
    # Step 3: Quality Assessment
    # ============================================================

    def _assess_quality(self, snapshot: MarketSnapshot):
        """Assess quality of each collected source."""
        # Price quality
        if snapshot.has_price:
            q = 0.9
            if snapshot.price_data.get("pct_change") is None:
                q = 0.5
            snapshot.source_qualities["market_data"] = SourceQuality(
                score=q, freshness=1.0, completeness=0.85,
            )
        else:
            snapshot.source_qualities["market_data"] = SourceQuality(
                score=0.0, note="No price data available"
            )

        # Factor quality
        if snapshot.has_factors:
            n_factors = len(snapshot.factor_data)
            q = min(n_factors / 15.0, 1.0)  # Full quality when 15+ factors
            snapshot.source_qualities["factor_signals"] = SourceQuality(
                score=q, freshness=1.0, completeness=q,
            )
        else:
            snapshot.source_qualities["factor_signals"] = SourceQuality(
                score=0.0, note="No factor data"
            )

        # News quality
        if snapshot.has_news:
            n_news = len(snapshot.news_events)
            q = min(n_news / 5.0, 1.0)
            snapshot.source_qualities["news_events"] = SourceQuality(
                score=q, freshness=1.0, completeness=q,
            )
        else:
            snapshot.source_qualities["news_events"] = SourceQuality(
                score=0.0, note="No news data"
            )

        # Wiki quality
        if snapshot.has_wiki:
            top_score = max((r["score"] for r in snapshot.wiki_refs), default=0)
            snapshot.source_qualities["wiki_methodology"] = SourceQuality(
                score=top_score, freshness=1.0, completeness=min(len(snapshot.wiki_refs) / 3.0, 1.0),
            )
        else:
            snapshot.source_qualities["wiki_methodology"] = SourceQuality(
                score=0.0, note="No wiki matches"
            )

        # Facts quality
        if snapshot.has_facts:
            n = len(snapshot.facts)
            verified = sum(1 for f in snapshot.facts if f.get("verified"))
            snapshot.source_qualities["historical_facts"] = SourceQuality(
                score=min(n / 10.0, 1.0), freshness=0.8, completeness=verified / max(n, 1),
            )
        else:
            snapshot.source_qualities["historical_facts"] = SourceQuality(
                score=0.0, note="No historical facts"
            )

    # ============================================================
    # Step 4: Dynamic Weights
    # ============================================================

    def _adjust_weights(self, snapshot: MarketSnapshot):
        """Adjust source weights based on regime and quality."""
        # Start with regime-adjusted weights
        try:
            from research.regime_detector import MarketRegime
            regime_enum = MarketRegime(snapshot.regime)
            regime_weights = self.regime_detector.get_weight_adjustments(regime_enum)
        except (ValueError, Exception):
            regime_weights = dict(self.base_weights)

        # Apply quality multiplier
        adjusted = {}
        mapping = {
            "market_data": "market_data",
            "factor_signals": "factor_signals",
            "news_events": "news_events",
            "wiki_methodology": "wiki",
            "historical_facts": "facts",
        }

        for src_key, regime_key in mapping.items():
            base = regime_weights.get(regime_key, self.base_weights.get(src_key, 0.1))
            quality = snapshot.source_qualities.get(src_key, SourceQuality())
            adjusted[src_key] = base * quality.score

        # Normalize
        total = sum(adjusted.values())
        if total > 0:
            adjusted = {k: v / total for k, v in adjusted.items()}

        snapshot.source_weights = adjusted

    # ============================================================
    # Step 5: Conflict Resolution
    # ============================================================

    def _resolve_conflicts(self, snapshot: MarketSnapshot):
        """Detect and resolve conflicts between sources."""
        # Get directional signals from each source
        signals = {}

        # Price direction
        if snapshot.has_price:
            pct = snapshot.price_data.get("pct_change", 0)
            if pct > 0.01:
                signals["price"] = "bullish"
            elif pct < -0.01:
                signals["price"] = "bearish"
            else:
                signals["price"] = "neutral"

        # Factor direction
        if snapshot.has_factors:
            bull = 0
            bear = 0
            for name, val in snapshot.factor_data.items():
                if "momentum" in name and val > 0.02:
                    bull += 1
                elif "momentum" in name and val < -0.02:
                    bear += 1
                elif "rsi" in name and val > 30:
                    bull += 1  # Not oversold
            if bull > bear:
                signals["factor"] = "bullish"
            elif bear > bull:
                signals["factor"] = "bearish"
            else:
                signals["factor"] = "neutral"

        # News sentiment
        if snapshot.has_news:
            sentiments = [e.get("sentiment", "neutral") for e in snapshot.news_events]
            pos = sum(1 for s in sentiments if s in ("positive", "bullish"))
            neg = sum(1 for s in sentiments if s in ("negative", "bearish"))
            if pos > neg:
                signals["news"] = "bullish"
            elif neg > pos:
                signals["news"] = "bearish"
            else:
                signals["news"] = "neutral"

        # Conflict resolution rules (see plan 3.1):
        # - Price + Factor aligned → high confidence
        # - Price + Factor divergent → confidence halved, flag "unclear"
        # - News vs Quant opposite → Quant wins (news may lag)
        # - Wiki only validates direction, never flips signal

        if signals.get("price") and signals.get("factor"):
            if signals["price"] == signals["factor"]:
                pass  # High confidence, no conflict
            elif signals["price"] != "neutral" and signals["factor"] != "neutral":
                snapshot.conflicts.append(
                    f"行情方向({signals['price']})与因子方向({signals['factor']})不一致"
                )
                snapshot.warnings.append("信号不明确：行情和因子方向相反")

        if signals.get("news") and signals.get("factor"):
            if (signals["news"] != signals["factor"]
                    and signals["news"] != "neutral"
                    and signals["factor"] != "neutral"):
                snapshot.conflicts.append(
                    f"新闻方向({signals['news']})与因子方向({signals['factor']})不一致 — 量化优先"
                )

        # Extreme price check
        if snapshot.has_price:
            pct = abs(snapshot.price_data.get("pct_change", 0))
            if pct > 0.095:  # Near limit-up/down
                snapshot.warnings.append("行情极度异常，技术因子降权")
                if "factor_signals" in snapshot.source_weights:
                    snapshot.source_weights["factor_signals"] *= 0.1
                    snapshot.source_weights["news_events"] = \
                        snapshot.source_weights.get("news_events", 0.15) * 0.5
                    self._renormalize_weights(snapshot)

    def _renormalize_weights(self, snapshot: MarketSnapshot):
        """Re-normalize source weights to sum to 1."""
        total = sum(snapshot.source_weights.values())
        if total > 0:
            snapshot.source_weights = {
                k: v / total for k, v in snapshot.source_weights.items()
            }

    # ============================================================
    # Step 6: Signal Aggregation
    # ============================================================

    def _aggregate_signals(self, snapshot: MarketSnapshot):
        """Aggregate all source signals into a unified direction."""
        scores = {"bullish": 0.0, "bearish": 0.0, "neutral": 0.0}

        # Price contribution
        if snapshot.has_price:
            pct = snapshot.price_data.get("pct_change", 0)
            w = snapshot.source_weights.get("market_data", 0.4)
            if pct > 0.02:
                scores["bullish"] += w
            elif pct < -0.02:
                scores["bearish"] += w
            else:
                scores["neutral"] += w

        # Factor contribution
        if snapshot.has_factors:
            w = snapshot.source_weights.get("factor_signals", 0.3)
            momentum_keys = [k for k in snapshot.factor_data if "momentum" in k]
            if momentum_keys:
                avg_mom = sum(snapshot.factor_data[k] for k in momentum_keys) / len(momentum_keys)
                if avg_mom > 0.03:
                    scores["bullish"] += w
                elif avg_mom < -0.03:
                    scores["bearish"] += w
                else:
                    scores["neutral"] += w * 0.5
                    scores["bullish" if avg_mom > 0 else "bearish"] += w * 0.5

        # News contribution
        if snapshot.has_news:
            w = snapshot.source_weights.get("news_events", 0.15)
            sentiments = [e.get("sentiment", "neutral") for e in snapshot.news_events]
            pos_ratio = sum(1 for s in sentiments if s in ("positive", "bullish")) / max(len(sentiments), 1)
            neg_ratio = sum(1 for s in sentiments if s in ("negative", "bearish")) / max(len(sentiments), 1)
            if pos_ratio > 0.5:
                scores["bullish"] += w
            elif neg_ratio > 0.5:
                scores["bearish"] += w
            else:
                scores["neutral"] += w

        # Wiki contributes to confidence but not direction

        # Determine final direction
        total = sum(scores.values())
        if total > 0:
            direction = max(scores, key=scores.get)
            confidence = scores[direction] / total
        else:
            direction = "neutral"
            confidence = 0.3

        snapshot.direction = direction
        snapshot.confidence = min(confidence, 0.95)

        # Strength
        if confidence > 0.7:
            snapshot.strength = "strong"
        elif confidence > 0.4:
            snapshot.strength = "moderate"
        else:
            snapshot.strength = "weak"

    # ============================================================
    # Intelligence-Factor Fusion (source: fengyezi intelligence.py)
    # ============================================================

    def apply_intelligence(self, snapshot: MarketSnapshot,
                           intelligence: dict) -> MarketSnapshot:
        """
        Apply market intelligence signals to modulate (not override) quant signals.

        Rules:
          - Intell bullish + Quant bullish → strengthen signal
          - Intell bearish + Quant bullish → quant wins (intelligence doesn't override)
          - Extreme intell signal (black_swan tag) → trigger risk review, don't modify signal

        Args:
            snapshot: Current MarketSnapshot
            intelligence: Intelligence signals from external source
                {direction: "bullish"/"bearish", confidence: 0.8, tags: [...]}

        Returns:
            Updated snapshot
        """
        intel_dir = intelligence.get("direction", "neutral")
        intel_conf = intelligence.get("confidence", 0.0)
        intel_tags = intelligence.get("tags", [])

        # Extreme tags → flag warning but don't modify signal
        if "black_swan" in intel_tags or "extreme_policy" in intel_tags:
            snapshot.warnings.append(
                f"极端情报信号({intel_tags})，触发风控复审，量化信号不变"
            )
            return snapshot

        # Same direction → amplify
        if intel_dir == snapshot.direction and intel_dir != "neutral":
            boost = 0.1 * intel_conf
            snapshot.confidence = min(snapshot.confidence + boost, 0.95)
            logger.debug(f"Intelligence aligned, confidence boosted to {snapshot.confidence:.2f}")

        # Opposite direction → quant wins, but note the divergence
        elif intel_dir != "neutral" and snapshot.direction != "neutral":
            if intel_dir != snapshot.direction:
                snapshot.conflicts.append(
                    f"情报方向({intel_dir})与量化方向({snapshot.direction})相反 — 量化优先"
                )
                snapshot.warnings.append("情报与量化信号分歧，保持量化方向")

        return snapshot
