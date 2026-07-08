"""
Multi-Agent Committee — rule-based analysis pipeline.

4 agents review the same market snapshot independently, then vote:

  DataAgent      → Data completeness, freshness, anomalies
  StrategyAgent  → Signal consolidation, cross-strategy conflict detection
  RiskAgent      → Position sizing, concentration, drawdown, VaR
  MemoryAgent    → Historical decision lookup, post-hoc return verification

Per ADR-001: the former AICriticAgent (OpenAI LLM) was removed — the project
is an MCP Server and LLM reasoning is provided by the external agent that
orchestrates these review tools. Each agent is also exposed as an MCP tool
(see mcp_server/tools_committee.py) so the external agent can spawn subagents,
each invoking its own review tool, then synthesise the consensus itself.

Usage:
    committee = AgentCommittee(storage)
    review = committee.review(snapshot, signals, portfolio)
"""
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

from loguru import logger


@dataclass
class AgentVote:
    """Single agent's vote."""
    agent: str
    action: str          # bullish / bearish / hold / caution
    confidence: float    # 0-1
    reason: str
    risk_flags: list[str] = field(default_factory=list)


@dataclass
class CommitteeReview:
    """Result of multi-agent review."""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    votes: list[AgentVote] = field(default_factory=list)
    consensus_action: str = "hold"
    consensus_confidence: float = 0.0
    risk_level: str = "medium"   # low / medium / high / critical
    risk_flags: list[str] = field(default_factory=list)
    summary: str = ""
    human_review_needed: bool = False


class AgentCommittee:
    """
    Rule-based 4-agent committee.

    Each agent runs deterministic rules. MemoryAgent queries DecisionMemory
    when a storage handle is supplied; otherwise it reports insufficient data.
    """

    def __init__(self, storage=None):
        """
        Args:
            storage: optional DataStorage for MemoryAgent decision lookups.
        """
        self._storage = storage
        self._review_history: list[CommitteeReview] = []

    def review(self, snapshot,               # MarketSnapshot
               signals: dict = None,         # {ticker: weight}
               portfolio: dict = None,       # {ticker: weight_pct, pnl_pct, ...}
               context: dict = None) -> CommitteeReview:
        """
        Run full committee review (4 agents + consensus).

        Args:
            snapshot: MarketSnapshot from FusionEngine
            signals: Strategy weight vectors {ticker: weight}
            portfolio: Current portfolio state
            context: Additional context (date, regime, etc.)

        Returns:
            CommitteeReview with all votes and consensus
        """
        signals = signals or {}
        portfolio = portfolio or {}
        context = context or {}

        review = CommitteeReview()
        risk_flags_all = []

        # ---- Agent 1: DataAgent ----
        data_vote = self.data_agent(snapshot)
        review.votes.append(data_vote)
        risk_flags_all.extend(data_vote.risk_flags)

        # ---- Agent 2: StrategyAgent ----
        strat_vote = self.strategy_agent(snapshot, signals)
        review.votes.append(strat_vote)
        risk_flags_all.extend(strat_vote.risk_flags)

        # ---- Agent 3: RiskAgent ----
        risk_vote = self.risk_agent(snapshot, signals, portfolio)
        review.votes.append(risk_vote)
        risk_flags_all.extend(risk_vote.risk_flags)

        # ---- Agent 4: MemoryAgent ----
        mem_vote = self.memory_agent(snapshot, signals)
        review.votes.append(mem_vote)
        risk_flags_all.extend(mem_vote.risk_flags)

        # ---- Consensus ----
        review.risk_flags = list(set(risk_flags_all))
        self._compute_consensus(review)

        # Risk level escalation
        review.risk_level = self._assess_risk_level(review)
        review.human_review_needed = (
            review.risk_level in ("high", "critical")
            or review.consensus_action == "caution"
            or len(review.risk_flags) >= 3
        )

        review.summary = self._generate_summary(review)
        self._review_history.append(review)

        logger.info(f"Committee: consensus={review.consensus_action}, "
                    f"risk={review.risk_level}, human_review={review.human_review_needed}")
        return review

    def synthesize(self, votes: list[AgentVote]) -> CommitteeReview:
        """
        Compute consensus from a pre-collected list of agent votes.

        Use this when the individual agent reviews ran separately (e.g. each
        via its own MCP tool / subagent) and the caller now wants the shared
        consensus, risk level, and summary without re-running the agents.
        """
        review = CommitteeReview(votes=list(votes))
        review.risk_flags = list(set(
            f for v in votes for f in v.risk_flags
        ))
        self._compute_consensus(review)
        review.risk_level = self._assess_risk_level(review)
        review.human_review_needed = (
            review.risk_level in ("high", "critical")
            or review.consensus_action == "caution"
            or len(review.risk_flags) >= 3
        )
        review.summary = self._generate_summary(review)
        return review

    # ============================================================
    # Agent 1: DataAgent
    # ============================================================

    def data_agent(self, snapshot) -> AgentVote:
        """Check data completeness, freshness, and anomalies."""
        issues = []
        available = 0
        total = 5

        if snapshot.has_price:
            available += 1
            pct = abs(snapshot.price_data.get("pct_change", 0))
            if pct > 0.095:
                issues.append(f"价格异常波动 {pct:.1%}")
        else:
            issues.append("缺少行情数据")

        if snapshot.has_factors:
            available += 1
        else:
            issues.append("缺少因子数据")

        if snapshot.has_news:
            available += 1
        if snapshot.has_wiki:
            available += 1
        if snapshot.has_facts:
            available += 1

        coverage = available / total
        if coverage >= 0.8 and not issues:
            return AgentVote("DataAgent", "bullish", 0.9,
                           f"数据覆盖良好 ({available}/{total})")
        elif coverage >= 0.4:
            return AgentVote("DataAgent", "hold", 0.5,
                           f"数据覆盖不足 ({available}/{total})", issues)
        else:
            return AgentVote("DataAgent", "caution", 0.3,
                           f"数据严重缺失 ({available}/{total})", issues)

    # ============================================================
    # Agent 2: StrategyAgent
    # ============================================================

    def strategy_agent(self, snapshot, signals: dict) -> AgentVote:
        """Analyze strategy signals for consistency and conflicts."""
        if not signals:
            return AgentVote("StrategyAgent", "hold", 0.3, "无策略信号")

        # Aggregate signal direction
        long_count = sum(1 for w in signals.values() if w > 0.1)
        short_count = sum(1 for w in signals.values() if w < -0.1)
        flat_count = sum(1 for w in signals.values() if abs(w) <= 0.1)

        flags = []
        if short_count > 0:
            flags.append(f"存在{short_count}个做空信号（A股限制做空）")

        # Check conflict with snapshot direction
        total_weight = sum(signals.values())
        signal_dir = "bullish" if total_weight > 0.1 else ("bearish" if total_weight < -0.1 else "neutral")

        if signal_dir != "neutral" and snapshot.direction != "neutral":
            if signal_dir != snapshot.direction:
                flags.append(f"策略方向({signal_dir})与融合方向({snapshot.direction})分歧")

        if long_count > flat_count and not flags:
            return AgentVote("StrategyAgent", "bullish", 0.7,
                           f"{long_count}个做多信号, 信号一致")
        elif long_count > 0:
            return AgentVote("StrategyAgent", "bullish", 0.5,
                           f"{long_count}做多, {flat_count}观望", flags)
        else:
            return AgentVote("StrategyAgent", "hold", 0.4,
                           "无明显方向信号", flags)

    # ============================================================
    # Agent 3: RiskAgent
    # ============================================================

    def risk_agent(self, snapshot, signals: dict,
                    portfolio: dict) -> AgentVote:
        """Check position sizing, concentration, drawdown, VaR."""
        flags = []

        # Check concentration
        if signals:
            max_w = max(abs(w) for w in signals.values())
            if max_w > 0.5:
                flags.append(f"单一标的权重{max_w:.0%}过高")

            total_exp = sum(abs(w) for w in signals.values())
            if total_exp > 1.0:
                flags.append(f"总敞口{total_exp:.0%}超过100%")

        # Check portfolio drawdown
        portfolio_dd = portfolio.get("max_drawdown", 0)
        if portfolio_dd < -0.05:
            flags.append(f"组合回撤{portfolio_dd:.1%}触及警戒线")

        # Extreme volatility flag
        if snapshot.regime == "extreme_volatility":
            flags.append("极端波动环境，建议降低仓位")

        # Conflicting signals in snapshot
        if snapshot.conflicts:
            flags.extend(snapshot.conflicts)

        if len(flags) >= 3:
            return AgentVote("RiskAgent", "caution", 0.8,
                           f"{len(flags)}个风险信号", flags)
        elif flags:
            return AgentVote("RiskAgent", "hold", 0.6,
                           f"{len(flags)}个风险提示", flags)
        else:
            return AgentVote("RiskAgent", "bullish", 0.8,
                           "风控检查通过")

    # ============================================================
    # Agent 4: MemoryAgent
    # ============================================================

    def memory_agent(self, snapshot, signals: dict) -> AgentVote:
        """
        Query historical decisions and post-hoc returns from DecisionMemory.

        Looks up recent decision accuracy for the tickers in `signals`. When
        accuracy is high and aligns with the signal direction, raises
        confidence; when accuracy is poor or contradicts the signal, flags a
        caution. Falls back to "insufficient data" when no storage or no
        history is available.
        """
        if not signals:
            return AgentVote("MemoryAgent", "hold", 0.5, "无历史参考（无信号）")

        if self._storage is None:
            return AgentVote("MemoryAgent", "hold", 0.4,
                            "决策记忆未接入（无 storage）",
                            ["决策记忆模块未就绪"])

        try:
            from knowledge.decision_memory import DecisionMemory
            dm = DecisionMemory(self._storage)
            accuracy = dm.get_accuracy(days=90) or {}
        except Exception as e:
            logger.warning(f"MemoryAgent 查询失败: {e}")
            return AgentVote("MemoryAgent", "hold", 0.4,
                            f"决策记忆查询失败: {e}",
                            ["决策记忆查询异常"])

        total = accuracy.get("total", 0) if isinstance(accuracy, dict) else 0
        if not total or total < 5:
            return AgentVote("MemoryAgent", "hold", 0.4,
                            f"历史样本不足 ({total} 条决策)")

        correct = accuracy.get("correct", 0)
        acc_ratio = correct / total if total else 0.0

        # Aggregate signal direction
        total_weight = sum(signals.values())
        signal_dir = "bullish" if total_weight > 0.1 else (
            "bearish" if total_weight < -0.1 else "neutral")

        flags = []
        if acc_ratio >= 0.6:
            return AgentVote("MemoryAgent", signal_dir if signal_dir != "neutral" else "hold",
                            min(0.5 + (acc_ratio - 0.5), 0.85),
                            f"历史决策准确率 {acc_ratio:.0%} ({correct}/{total})，支持当前方向")
        elif acc_ratio <= 0.4:
            flags.append(f"历史决策准确率偏低 ({acc_ratio:.0%})")
            return AgentVote("MemoryAgent", "caution", 0.6,
                            f"历史决策准确率 {acc_ratio:.0%} ({correct}/{total})，建议谨慎",
                            flags)

        return AgentVote("MemoryAgent", "hold", 0.5,
                        f"历史决策准确率 {acc_ratio:.0%} ({correct}/{total})，参考价值有限",
                        flags)

    # ============================================================
    # Consensus
    # ============================================================

    def _compute_consensus(self, review: CommitteeReview):
        """Compute consensus from agent votes."""
        action_votes = {"bullish": 0, "bearish": 0, "hold": 0, "caution": 0}
        confidence_sum = 0.0

        for vote in review.votes:
            w = vote.confidence
            action_votes[vote.action] = action_votes.get(vote.action, 0) + w
            confidence_sum += w

        # Weighted consensus
        review.consensus_action = max(action_votes, key=action_votes.get)
        if confidence_sum > 0:
            review.consensus_confidence = min(
                action_votes[review.consensus_action] / confidence_sum, 0.95
            )

        # If "caution" has significant votes, escalate
        caution_ratio = action_votes.get("caution", 0) / max(confidence_sum, 0.01)
        if caution_ratio > 0.3:
            review.consensus_action = "caution"

    def _assess_risk_level(self, review: CommitteeReview) -> str:
        """Escalate risk level based on flags."""
        n_flags = len(review.risk_flags)

        # Count critical keywords
        critical_keywords = ["极端", "黑天鹅", "熔断", "触及警戒线", "严重缺失"]
        critical_count = sum(
            1 for f in review.risk_flags
            if any(kw in f for kw in critical_keywords)
        )

        if critical_count >= 2 or n_flags >= 5:
            return "critical"
        elif critical_count >= 1 or n_flags >= 3:
            return "high"
        elif n_flags >= 1:
            return "medium"
        return "low"

    def _generate_summary(self, review: CommitteeReview) -> str:
        """Generate human-readable summary."""
        vote_summary = ", ".join(
            f"{v.agent}→{v.action}" for v in review.votes
        )
        return (
            f"[{review.risk_level.upper()}风险] "
            f"共识: {review.consensus_action} (置信度{review.consensus_confidence:.0%}). "
            f"投票: {vote_summary}. "
            f"风控信号: {len(review.risk_flags)}个. "
            f"{'[!] 需要人工复核' if review.human_review_needed else '[OK] 无需人工干预'}"
        )

    # ============================================================
    # History
    # ============================================================

    def get_history(self, limit: int = 10) -> list[CommitteeReview]:
        return self._review_history[-limit:]

    def get_last_review(self) -> Optional[CommitteeReview]:
        return self._review_history[-1] if self._review_history else None
