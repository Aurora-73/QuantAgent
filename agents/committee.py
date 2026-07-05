"""
Multi-Agent Committee — rule-based analysis pipeline with optional LLM critique.

5 agents review the same market snapshot independently, then vote:

  DataAgent      → Data completeness, freshness, anomalies
  StrategyAgent  → Signal consolidation, cross-strategy conflict detection
  RiskAgent      → Position sizing, concentration, drawdown, VaR
  MemoryAgent    → Historical decision lookup, post-hoc return verification
  AICriticAgent  → LLM-powered reviewer (optional, falls back to rule-based)

Reference: fengyezi fund_ai_server/agents.py

Usage:
    committee = AgentCommittee()
    review = committee.review(snapshot, signals, portfolio, use_llm=True)
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
    Rule-based 5-agent committee.

    Each agent runs deterministic rules — no LLM in Phase B.
    AICriticAgent is a pass-through stub until Phase D.
    """

    def __init__(self):
        self._review_history: list[CommitteeReview] = []

    def review(self, snapshot,               # MarketSnapshot
               signals: dict = None,         # {ticker: weight}
               portfolio: dict = None,       # {ticker: weight_pct, pnl_pct, ...}
               context: dict = None,
               use_llm: bool = False) -> CommitteeReview:
        """
        Run full committee review.

        Args:
            snapshot: MarketSnapshot from FusionEngine
            signals: Strategy weight vectors {ticker: weight}
            portfolio: Current portfolio state
            context: Additional context (date, regime, etc.)
            use_llm: Enable LLM-powered AICriticAgent

        Returns:
            CommitteeReview with all votes and consensus
        """
        signals = signals or {}
        portfolio = portfolio or {}
        context = context or {}

        review = CommitteeReview()
        risk_flags_all = []

        # ---- Agent 1: DataAgent ----
        data_vote = self._data_agent(snapshot)
        review.votes.append(data_vote)
        risk_flags_all.extend(data_vote.risk_flags)

        # ---- Agent 2: StrategyAgent ----
        strat_vote = self._strategy_agent(snapshot, signals)
        review.votes.append(strat_vote)
        risk_flags_all.extend(strat_vote.risk_flags)

        # ---- Agent 3: RiskAgent ----
        risk_vote = self._risk_agent(snapshot, signals, portfolio)
        review.votes.append(risk_vote)
        risk_flags_all.extend(risk_vote.risk_flags)

        # ---- Agent 4: MemoryAgent ----
        mem_vote = self._memory_agent(snapshot, signals)
        review.votes.append(mem_vote)
        risk_flags_all.extend(mem_vote.risk_flags)

        # ---- Agent 5: AICriticAgent (LLM-powered in Phase D) ----
        ai_vote = self._ai_critic_agent(snapshot, signals, review.votes, use_llm=use_llm)
        review.votes.append(ai_vote)

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

    # ============================================================
    # Agent 1: DataAgent
    # ============================================================

    def _data_agent(self, snapshot) -> AgentVote:
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

    def _strategy_agent(self, snapshot, signals: dict) -> AgentVote:
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

    def _risk_agent(self, snapshot, signals: dict,
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

    def _memory_agent(self, snapshot, signals: dict) -> AgentVote:
        """
        Query historical decisions and post-hoc returns.

        In Phase B: stub (no decision memory yet).
        Phase C will query the real decision_memory table.
        """
        if not signals:
            return AgentVote("MemoryAgent", "hold", 0.5, "无历史参考（无信号）")

        # Placeholder — Phase C will do real queries
        return AgentVote("MemoryAgent", "hold", 0.5,
                        "历史数据不足（Phase C 接入决策记忆）",
                        ["决策记忆模块未就绪"])

    # ============================================================
    # Agent 5: AICriticAgent (LLM in Phase D, rule fallback)
    # ============================================================

    def _ai_critic_agent(self, snapshot, signals: dict,
                         other_votes: list[AgentVote],
                         use_llm: bool = False) -> AgentVote:
        """
        LLM-powered critique of other agents.

        When use_llm=True and OpenAI client is available:
          - Formats snapshot + signals + other votes into a structured prompt
          - Gets LLM analysis of risks and opportunities
          - Extracts action + confidence from LLM response

        When use_llm=False or LLM unavailable:
          - Rule-based pass-through: follows the majority vote of other agents
          - Slightly reduces confidence to indicate lack of independent analysis

        Returns:
            AgentVote from AICriticAgent
        """
        if use_llm:
            llm_vote = self._llm_critic(snapshot, signals, other_votes)
            if llm_vote is not None:
                return llm_vote

        # Fallback: rule-based pass-through
        action_counts = {"bullish": 0, "bearish": 0, "hold": 0, "caution": 0}
        for v in other_votes:
            action_counts[v.action] = action_counts.get(v.action, 0) + 1
        majority_action = max(action_counts, key=action_counts.get)

        # Slightly lower confidence to indicate no independent analysis
        base_conf = 0.4
        return AgentVote(
            "AICriticAgent", majority_action, base_conf,
            f"规则跟随: 多数→{majority_action} ({'LLM不可用' if use_llm else 'LLM未启用'})",
            ["AI 评审使用规则回退"] if use_llm else [],
        )

    def _llm_critic(self, snapshot, signals: dict,
                    other_votes: list[AgentVote]) -> Optional[AgentVote]:
        """LLM-based critique — OpenAI integration."""
        try:
            from openai import OpenAI
            from configs.settings import settings

            api_key = settings.openai_api_key
            model = getattr(settings, "llm_model", "gpt-4o-mini")
            if not api_key:
                return None

            client = OpenAI(api_key=api_key)

            # Build prompt from snapshot and votes
            vote_summary = "\n".join(
                f"- {v.agent}: {v.action} (置信度{v.confidence:.0%}, 理由: {v.reason})"
                for v in other_votes
            )

            signal_summary = ""
            if signals:
                signal_summary = "\n".join(
                    f"- {ticker}: weight={w:+.2f}"
                    for ticker, w in list(signals.items())[:10]
                )

            prompt = f"""你是一个量化交易系统的 AI 评审员 (AICriticAgent)。请评审以下市场分析和投票。

## 其他 Agent 投票
{vote_summary}

## 策略信号
{signal_summary or "- 无信号"}

## 市场方向
{getattr(snapshot, 'direction', 'neutral')} (置信度 {getattr(snapshot, 'confidence', 0.5):.0%})

## 市场状态
{getattr(snapshot, 'regime', 'unknown')}

## 你的任务
分析上述投票和信号的一致性，识别潜在风险或被忽视的机会。

请输出 JSON:
{{
    "action": "bullish/bearish/hold/caution",
    "confidence": 0.0-1.0,
    "reason": "你的分析理由 (中文, 20-50字)",
    "risk_flags": ["风险1", "风险2"]
}}"""

            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                response_format={"type": "json_object"},
                max_tokens=300,
            )

            import json
            result = json.loads(resp.choices[0].message.content)
            action = result.get("action", "hold")
            confidence = min(float(result.get("confidence", 0.5)), 0.95)
            reason = result.get("reason", "LLM 分析完成")
            risk_flags = result.get("risk_flags", [])

            logger.info(f"  AICriticAgent(LLM): {action} conf={confidence:.0%}")
            return AgentVote("AICriticAgent", action, confidence, reason, risk_flags)

        except Exception as e:
            logger.warning(f"  AICriticAgent LLM 失败: {e}")
            return None

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
