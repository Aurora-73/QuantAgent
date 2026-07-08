"""
MCP Committee Tools — expose the 4-agent committee review as individual tools.

Per ADR-001 the rule-based committee (Data/Strategy/Risk/Memory agents) is the
single source of review logic; the former LLM critic was removed. The external
MCP agent orchestrates a review by spawning one subagent per role, each
invoking its own tool here, then calling `compute_committee_consensus` (or
reasoning over the votes itself) to synthesise the final call.

Tools:
  review_data_quality       — DataAgent: data completeness / freshness / anomalies
  review_strategy_signals   — StrategyAgent: signal consistency / conflicts
  review_risk_exposure      — RiskAgent: concentration / drawdown / exposure
  review_decision_history   — MemoryAgent: historical decision accuracy
  compute_committee_consensus — synthesise a list of votes into one consensus
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Optional

from loguru import logger

from agents.committee import AgentCommittee, AgentVote
from data.storage import DataStorage
from mcp_server.registry import register_mcp_tool


def _resolve_ticker(ticker: str) -> str:
    t = ticker.strip().upper().replace(".SS", "").replace(".SZ", "")
    return t.zfill(6)


def _parse_date(s: Optional[str]) -> date:
    if not s:
        return date.today()
    return date.fromisoformat(str(s)[:10])


def _vote_to_dict(vote: AgentVote) -> dict:
    return {
        "agent": vote.agent,
        "action": vote.action,
        "confidence": round(vote.confidence, 3),
        "reason": vote.reason,
        "risk_flags": list(vote.risk_flags),
    }


def _build_snapshot(ticker: str, target_date: date):
    """
    Build a MarketSnapshot via FusionEngine, loading price/factor data from
    storage. Returns (snapshot, error_str); on failure snapshot is None.
    """
    from research.fusion import FusionEngine

    storage = DataStorage()
    start = (target_date - timedelta(days=160)).isoformat()
    price_df = storage.load_stock_daily(ticker, start_date=start)

    factor_df = None
    if not price_df.empty:
        try:
            from research.factors import FactorEngine
            factor_df = FactorEngine().compute_all(price_df)
        except Exception as e:
            logger.debug(f"factor compute skipped for {ticker}: {e}")
            factor_df = None

    fusion = FusionEngine()
    snapshot = fusion.collect(
        ticker=ticker,
        target_date=target_date,
        price_df=price_df if not price_df.empty else None,
        factor_df=factor_df if factor_df is not None and not factor_df.empty else None,
        extra_context={"regime": "unknown"},
    )
    return snapshot


def _parse_json_arg(raw: str, default):
    """Best-effort JSON parse for tool arguments passed as strings."""
    if not raw or not isinstance(raw, str):
        return default
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return default


@register_mcp_tool(
    name="review_data_quality",
    description="数据质量评审（DataAgent）：检查行情/因子/新闻等数据覆盖度、新鲜度与价格异常。返回一个结构化投票，供委员会共识合成",
    read_only=True,
    skill="risk-review",
)
def review_data_quality(ticker: str, target_date: str = "") -> str:
    """
    运行 DataAgent 评审。构建该标的市场快照后检查数据覆盖度与价格异常波动。

    Args:
        ticker: 股票代码
        target_date: 目标日期 (YYYY-MM-DD)，默认今天
    """
    try:
        ticker = _resolve_ticker(ticker)
        d = _parse_date(target_date)
        snapshot = _build_snapshot(ticker, d)
        if snapshot is None:
            return json.dumps({"error": f"无法构建快照: {ticker}"}, ensure_ascii=False)
        committee = AgentCommittee()
        vote = committee.data_agent(snapshot)
        return json.dumps(_vote_to_dict(vote), ensure_ascii=False)
    except Exception as e:
        logger.warning(f"review_data_quality 失败: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@register_mcp_tool(
    name="review_strategy_signals",
    description="策略信号评审（StrategyAgent）：分析信号方向一致性、跨策略冲突与做空检测。返回一个结构化投票",
    read_only=True,
    skill="risk-review",
)
def review_strategy_signals(ticker: str,
                            signals_json: str = "{}",
                            target_date: str = "") -> str:
    """
    运行 StrategyAgent 评审。

    Args:
        ticker: 股票代码（用于构建快照方向）
        signals_json: 策略权重向量 JSON，如 '{"000300": 0.3, "600519": -0.2}'
        target_date: 目标日期 (YYYY-MM-DD)
    """
    try:
        ticker = _resolve_ticker(ticker)
        d = _parse_date(target_date)
        signals = _parse_json_arg(signals_json, {})
        if not isinstance(signals, dict):
            signals = {}
        signals = {str(k): float(v) for k, v in signals.items()}

        snapshot = _build_snapshot(ticker, d)
        if snapshot is None:
            return json.dumps({"error": f"无法构建快照: {ticker}"}, ensure_ascii=False)
        committee = AgentCommittee()
        vote = committee.strategy_agent(snapshot, signals)
        return json.dumps(_vote_to_dict(vote), ensure_ascii=False)
    except Exception as e:
        logger.warning(f"review_strategy_signals 失败: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@register_mcp_tool(
    name="review_risk_exposure",
    description="风险敞口评审（RiskAgent）：检查单一标的权重、总敞口、组合回撤与极端波动。返回一个结构化投票",
    read_only=True,
    skill="risk-review",
)
def review_risk_exposure(ticker: str,
                         signals_json: str = "{}",
                         portfolio_json: str = "{}",
                         target_date: str = "") -> str:
    """
    运行 RiskAgent 评审。

    Args:
        ticker: 股票代码（用于构建快照的市场状态）
        signals_json: 策略权重向量 JSON
        portfolio_json: 组合状态 JSON，如 '{"max_drawdown": -0.03, "total_value": 1000000}'
        target_date: 目标日期 (YYYY-MM-DD)
    """
    try:
        ticker = _resolve_ticker(ticker)
        d = _parse_date(target_date)
        signals = _parse_json_arg(signals_json, {})
        if not isinstance(signals, dict):
            signals = {}
        signals = {str(k): float(v) for k, v in signals.items()}
        portfolio = _parse_json_arg(portfolio_json, {})
        if not isinstance(portfolio, dict):
            portfolio = {}

        snapshot = _build_snapshot(ticker, d)
        if snapshot is None:
            return json.dumps({"error": f"无法构建快照: {ticker}"}, ensure_ascii=False)
        committee = AgentCommittee()
        vote = committee.risk_agent(snapshot, signals, portfolio)
        return json.dumps(_vote_to_dict(vote), ensure_ascii=False)
    except Exception as e:
        logger.warning(f"review_risk_exposure 失败: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@register_mcp_tool(
    name="review_decision_history",
    description="决策历史评审（MemoryAgent）：查询近 90 天决策准确率，结合信号方向给出历史参考投票与准确率统计",
    read_only=True,
    skill="risk-review",
)
def review_decision_history(ticker: str = "",
                            signals_json: str = "{}",
                            days: int = 90) -> str:
    """
    运行 MemoryAgent 评审。查询 DecisionMemory 历史决策准确率。

    Args:
        ticker: 股票代码（可选，记录用）
        signals_json: 策略权重向量 JSON，用于判断信号方向
        days: 回溯天数（默认 90）
    """
    try:
        signals = _parse_json_arg(signals_json, {})
        if not isinstance(signals, dict):
            signals = {}

        storage = DataStorage()
        committee = AgentCommittee(storage=storage)

        # Build a lightweight snapshot placeholder; memory_agent only uses
        # `signals` and storage, not snapshot fields.
        class _LightSnapshot:
            pass
        snapshot = _LightSnapshot()

        vote = committee.memory_agent(snapshot, signals)

        # Augment with raw accuracy stats for transparency
        accuracy = {}
        try:
            from knowledge.decision_memory import DecisionMemory
            accuracy = DecisionMemory(storage).get_accuracy(days=days) or {}
        except Exception:
            pass

        result = _vote_to_dict(vote)
        result["accuracy_stats"] = accuracy
        return json.dumps(result, ensure_ascii=False, default=str)
    except Exception as e:
        logger.warning(f"review_decision_history 失败: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@register_mcp_tool(
    name="compute_committee_consensus",
    description="委员会共识合成：接收各 agent 的投票列表，计算加权共识动作、风险等级与人工复核标记。用于在分别调用各评审工具后汇总",
    read_only=True,
    skill="risk-review",
)
def compute_committee_consensus(votes_json: str) -> str:
    """
    合成委员会共识。

    Args:
        votes_json: 投票列表 JSON，每项形如
            {"agent": "DataAgent", "action": "bullish", "confidence": 0.9,
             "reason": "...", "risk_flags": []}
    """
    try:
        raw_votes = _parse_json_arg(votes_json, [])
        if not isinstance(raw_votes, list) or not raw_votes:
            return json.dumps(
                {"error": "votes_json 必须是非空投票列表"}, ensure_ascii=False
            )

        votes = []
        for v in raw_votes:
            if not isinstance(v, dict):
                continue
            votes.append(AgentVote(
                agent=str(v.get("agent", "Unknown")),
                action=str(v.get("action", "hold")),
                confidence=float(v.get("confidence", 0.5)),
                reason=str(v.get("reason", "")),
                risk_flags=list(v.get("risk_flags", [])),
            ))

        if not votes:
            return json.dumps(
                {"error": "未解析到有效投票"}, ensure_ascii=False
            )

        committee = AgentCommittee()
        review = committee.synthesize(votes)
        return json.dumps({
            "consensus_action": review.consensus_action,
            "consensus_confidence": round(review.consensus_confidence, 3),
            "risk_level": review.risk_level,
            "risk_flags": review.risk_flags,
            "human_review_needed": review.human_review_needed,
            "summary": review.summary,
            "vote_count": len(review.votes),
        }, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"compute_committee_consensus 失败: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)
