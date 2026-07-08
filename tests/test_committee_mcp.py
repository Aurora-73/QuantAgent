"""Tests for ADR-0003: Agent committee refactor + MCP tools.

Covers:
  - 4 rule-based agents (Data/Strategy/Risk/Memory) behaviour
  - MemoryAgent wired to DecisionMemory (accuracy branches)
  - No LLM methods remain (_llm_critic / _ai_critic_agent removed)
  - synthesize() consensus from a pre-collected vote list
  - review() full 4-agent flow
  - 5 MCP tools in mcp_server/tools_committee.py (return structure + error handling)
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

import pytest

from agents.committee import AgentCommittee, AgentVote, CommitteeReview


# ============================================================
# Helpers
# ============================================================

def make_snapshot(**kw):
    """Build a lightweight MarketSnapshot-like object for agent tests."""
    defaults = dict(
        ticker="000300",
        date="2026-07-09",
        regime="unknown",
        regime_confidence=0.3,
        has_price=True,
        has_factors=True,
        has_news=False,
        has_wiki=False,
        has_facts=False,
        direction="neutral",
        strength="weak",
        confidence=0.5,
        price_data={"pct_change": 0.02},
        factor_data={},
        news_events=[],
        wiki_refs=[],
        facts=[],
        source_weights={},
        source_qualities={},
        conflicts=[],
        warnings=[],
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def make_storage_with_accuracy(accuracy: dict):
    """Mock storage whose get_decision_accuracy returns the given dict."""
    storage = MagicMock()
    storage.get_decision_accuracy.return_value = accuracy
    return storage


# ============================================================
# DataAgent
# ============================================================

class TestDataAgent:
    def test_good_coverage_is_bullish(self):
        c = AgentCommittee()
        snap = make_snapshot(has_price=True, has_factors=True, has_news=True,
                             has_wiki=True, has_facts=True)
        vote = c.data_agent(snap)
        assert vote.agent == "DataAgent"
        assert vote.action == "bullish"
        assert vote.confidence == 0.9

    def test_missing_data_is_caution(self):
        c = AgentCommittee()
        snap = make_snapshot(has_price=False, has_factors=False,
                             has_news=False, has_wiki=False, has_facts=False)
        vote = c.data_agent(snap)
        assert vote.action == "caution"
        assert any("缺少" in f for f in vote.risk_flags)

    def test_partial_coverage_is_hold(self):
        c = AgentCommittee()
        snap = make_snapshot(has_price=True, has_factors=True,
                             has_news=False, has_wiki=False, has_facts=False)
        vote = c.data_agent(snap)
        assert vote.action == "hold"

    def test_price_anomaly_flagged(self):
        c = AgentCommittee()
        snap = make_snapshot(price_data={"pct_change": 0.12})  # > 9.5%
        vote = c.data_agent(snap)
        assert any("异常" in f for f in vote.risk_flags)


# ============================================================
# StrategyAgent
# ============================================================

class TestStrategyAgent:
    def test_no_signals_hold(self):
        c = AgentCommittee()
        vote = c.strategy_agent(make_snapshot(), {})
        assert vote.action == "hold"
        assert "无策略信号" in vote.reason

    def test_consistent_long_signals_bullish(self):
        c = AgentCommittee()
        vote = c.strategy_agent(
            make_snapshot(direction="neutral"),
            {"000300": 0.4, "600519": 0.3},
        )
        assert vote.action == "bullish"

    def test_short_signal_flagged(self):
        c = AgentCommittee()
        vote = c.strategy_agent(
            make_snapshot(direction="neutral"),
            {"000300": -0.3},
        )
        assert any("做空" in f for f in vote.risk_flags)

    def test_signal_direction_conflict_with_snapshot(self):
        c = AgentCommittee()
        vote = c.strategy_agent(
            make_snapshot(direction="bullish"),
            {"000300": -0.4},  # bearish signal vs bullish snapshot
        )
        assert any("分歧" in f for f in vote.risk_flags)


# ============================================================
# RiskAgent
# ============================================================

class TestRiskAgent:
    def test_clean_portfolio_bullish(self):
        c = AgentCommittee()
        vote = c.risk_agent(
            make_snapshot(),
            {"000300": 0.3, "600519": 0.2},
            {"max_drawdown": 0},
        )
        assert vote.action == "bullish"

    def test_concentration_flag(self):
        c = AgentCommittee()
        vote = c.risk_agent(
            make_snapshot(),
            {"000300": 0.6},  # > 50%
            {"max_drawdown": 0},
        )
        assert any("权重" in f for f in vote.risk_flags)

    def test_total_exposure_flag(self):
        c = AgentCommittee()
        vote = c.risk_agent(
            make_snapshot(),
            {"000300": 0.6, "600519": 0.6},  # total > 100%
            {"max_drawdown": 0},
        )
        assert any("总敞口" in f for f in vote.risk_flags)

    def test_drawdown_caution(self):
        c = AgentCommittee()
        vote = c.risk_agent(
            make_snapshot(),
            {"000300": 0.3},
            {"max_drawdown": -0.08},
        )
        assert any("回撤" in f for f in vote.risk_flags)

    def test_extreme_volatility_flag(self):
        c = AgentCommittee()
        vote = c.risk_agent(
            make_snapshot(regime="extreme_volatility"),
            {"000300": 0.3},
            {"max_drawdown": 0},
        )
        assert any("极端波动" in f for f in vote.risk_flags)


# ============================================================
# MemoryAgent
# ============================================================

class TestMemoryAgent:
    def test_no_storage_reports_not_ready(self):
        c = AgentCommittee()  # no storage
        vote = c.memory_agent(make_snapshot(), {"000300": 0.3})
        assert vote.action == "hold"
        assert "决策记忆模块未就绪" in vote.risk_flags

    def test_no_signals_hold(self):
        c = AgentCommittee(storage=make_storage_with_accuracy({"total": 100}))
        vote = c.memory_agent(make_snapshot(), {})
        assert vote.action == "hold"
        assert "无历史参考" in vote.reason

    def test_insufficient_samples_hold(self):
        c = AgentCommittee(storage=make_storage_with_accuracy({"total": 3, "correct": 2}))
        vote = c.memory_agent(make_snapshot(), {"000300": 0.3})
        assert vote.action == "hold"
        assert "样本不足" in vote.reason

    def test_high_accuracy_supports_direction(self):
        c = AgentCommittee(storage=make_storage_with_accuracy(
            {"total": 20, "correct": 15, "accuracy": 0.75}))
        vote = c.memory_agent(make_snapshot(), {"000300": 0.4})
        assert vote.action == "bullish"
        assert "支持当前方向" in vote.reason

    def test_low_accuracy_caution(self):
        c = AgentCommittee(storage=make_storage_with_accuracy(
            {"total": 20, "correct": 6, "accuracy": 0.3}))
        vote = c.memory_agent(make_snapshot(), {"000300": 0.4})
        assert vote.action == "caution"
        assert any("准确率偏低" in f for f in vote.risk_flags)

    def test_bearish_signal_high_accuracy(self):
        c = AgentCommittee(storage=make_storage_with_accuracy(
            {"total": 20, "correct": 15, "accuracy": 0.75}))
        vote = c.memory_agent(make_snapshot(), {"000300": -0.4})
        assert vote.action == "bearish"

    def test_query_failure_falls_back(self):
        storage = MagicMock()
        storage.get_decision_accuracy.side_effect = RuntimeError("db down")
        c = AgentCommittee(storage=storage)
        vote = c.memory_agent(make_snapshot(), {"000300": 0.3})
        assert vote.action == "hold"
        assert any("查询异常" in f for f in vote.risk_flags)

    def test_non_dict_accuracy_treated_as_empty(self):
        storage = MagicMock()
        storage.get_decision_accuracy.return_value = None
        c = AgentCommittee(storage=storage)
        vote = c.memory_agent(make_snapshot(), {"000300": 0.3})
        assert vote.action == "hold"
        assert "样本不足" in vote.reason


# ============================================================
# synthesize + review
# ============================================================

class TestSynthesize:
    def test_consensus_bullish_from_majority(self):
        c = AgentCommittee()
        votes = [
            AgentVote("DataAgent", "bullish", 0.9, "ok"),
            AgentVote("StrategyAgent", "bullish", 0.7, "ok"),
            AgentVote("RiskAgent", "hold", 0.6, "ok"),
            AgentVote("MemoryAgent", "bullish", 0.7, "ok"),
        ]
        review = c.synthesize(votes)
        assert review.consensus_action == "bullish"
        assert len(review.votes) == 4
        assert isinstance(review.summary, str) and review.summary

    def test_caution_escalation_when_caution_ratio_high(self):
        c = AgentCommittee()
        votes = [
            AgentVote("DataAgent", "caution", 0.8, "bad"),
            AgentVote("StrategyAgent", "caution", 0.7, "bad"),
            AgentVote("RiskAgent", "bullish", 0.5, "ok"),
            AgentVote("MemoryAgent", "hold", 0.4, "ok"),
        ]
        review = c.synthesize(votes)
        # caution confidence sum dominates → consensus caution
        assert review.consensus_action == "caution"
        assert review.human_review_needed is True

    def test_risk_level_from_flags(self):
        c = AgentCommittee()
        votes = [
            AgentVote("RiskAgent", "caution", 0.8, "bad",
                      ["极端波动", "触及警戒线", "总敞口超过100%"]),
        ]
        review = c.synthesize(votes)
        assert review.risk_level in ("high", "critical")

    def test_review_runs_four_agents(self):
        c = AgentCommittee(storage=make_storage_with_accuracy({"total": 0}))
        snap = make_snapshot()
        review = c.review(snap, {"000300": 0.3}, {"max_drawdown": 0})
        agent_names = [v.agent for v in review.votes]
        assert agent_names == ["DataAgent", "StrategyAgent", "RiskAgent", "MemoryAgent"]
        assert len(review.votes) == 4  # exactly 4, no AICriticAgent


class TestNoLlmRemnants:
    def test_no_llm_critic_method(self):
        c = AgentCommittee()
        assert not hasattr(c, "_llm_critic")

    def test_no_ai_critic_agent_method(self):
        c = AgentCommittee()
        assert not hasattr(c, "_ai_critic_agent")

    def test_review_has_no_use_llm_param(self):
        import inspect
        sig = inspect.signature(AgentCommittee.review)
        assert "use_llm" not in sig.parameters


# ============================================================
# MCP tools
# ============================================================

class TestMcpReviewDataQuality:
    def test_returns_vote_json(self):
        from mcp_server import tools_committee
        with patch.object(tools_committee, "_build_snapshot",
                          return_value=make_snapshot()):
            out = tools_committee.review_data_quality("000300", "2026-07-09")
        data = json.loads(out)
        assert data["agent"] == "DataAgent"
        assert "action" in data and "confidence" in data

    def test_snapshot_failure_returns_error(self):
        from mcp_server import tools_committee
        with patch.object(tools_committee, "_build_snapshot", return_value=None):
            out = tools_committee.review_data_quality("000300")
        data = json.loads(out)
        assert "error" in data


class TestMcpReviewStrategySignals:
    def test_parses_signals_and_returns_vote(self):
        from mcp_server import tools_committee
        with patch.object(tools_committee, "_build_snapshot",
                          return_value=make_snapshot(direction="neutral")):
            out = tools_committee.review_strategy_signals(
                "000300", '{"000300": 0.4, "600519": 0.3}')
        data = json.loads(out)
        assert data["agent"] == "StrategyAgent"
        assert data["action"] == "bullish"

    def test_invalid_signals_json_does_not_crash(self):
        from mcp_server import tools_committee
        with patch.object(tools_committee, "_build_snapshot",
                          return_value=make_snapshot()):
            out = tools_committee.review_strategy_signals("000300", "not-json")
        data = json.loads(out)
        assert data["agent"] == "StrategyAgent"
        # invalid signals → treated as empty → hold
        assert data["action"] == "hold"


class TestMcpReviewRiskExposure:
    def test_returns_risk_vote(self):
        from mcp_server import tools_committee
        with patch.object(tools_committee, "_build_snapshot",
                          return_value=make_snapshot()):
            out = tools_committee.review_risk_exposure(
                "000300", '{"000300": 0.3}', '{"max_drawdown": 0}')
        data = json.loads(out)
        assert data["agent"] == "RiskAgent"
        assert data["action"] == "bullish"

    def test_concentration_flag_passthrough(self):
        from mcp_server import tools_committee
        with patch.object(tools_committee, "_build_snapshot",
                          return_value=make_snapshot()):
            out = tools_committee.review_risk_exposure(
                "000300", '{"000300": 0.6}', '{"max_drawdown": 0}')
        data = json.loads(out)
        assert any("权重" in f for f in data["risk_flags"])


class TestMcpReviewDecisionHistory:
    def test_returns_memory_vote_and_accuracy(self):
        from mcp_server import tools_committee
        storage = make_storage_with_accuracy(
            {"total": 20, "correct": 15, "accuracy": 0.75})
        with patch.object(tools_committee, "DataStorage", return_value=storage):
            out = tools_committee.review_decision_history(
                "000300", '{"000300": 0.4}')
        data = json.loads(out)
        assert data["agent"] == "MemoryAgent"
        assert data["action"] == "bullish"
        assert data["accuracy_stats"]["total"] == 20

    def test_insufficient_samples(self):
        from mcp_server import tools_committee
        storage = make_storage_with_accuracy({"total": 2, "correct": 1})
        with patch.object(tools_committee, "DataStorage", return_value=storage):
            out = tools_committee.review_decision_history(
                "000300", '{"000300": 0.4}')
        data = json.loads(out)
        assert data["action"] == "hold"
        assert "样本不足" in data["reason"]


class TestMcpComputeConsensus:
    def test_synthesizes_votes(self):
        from mcp_server import tools_committee
        votes = [
            {"agent": "DataAgent", "action": "bullish", "confidence": 0.9,
             "reason": "ok", "risk_flags": []},
            {"agent": "StrategyAgent", "action": "bullish", "confidence": 0.7,
             "reason": "ok", "risk_flags": []},
            {"agent": "RiskAgent", "action": "hold", "confidence": 0.6,
             "reason": "ok", "risk_flags": []},
        ]
        out = tools_committee.compute_committee_consensus(json.dumps(votes))
        data = json.loads(out)
        assert data["consensus_action"] == "bullish"
        assert data["vote_count"] == 3
        assert "summary" in data

    def test_empty_votes_returns_error(self):
        from mcp_server import tools_committee
        out = tools_committee.compute_committee_consensus("[]")
        data = json.loads(out)
        assert "error" in data

    def test_invalid_json_returns_error(self):
        from mcp_server import tools_committee
        out = tools_committee.compute_committee_consensus("not-json")
        data = json.loads(out)
        assert "error" in data

    def test_risk_flags_aggregated(self):
        from mcp_server import tools_committee
        votes = [
            {"agent": "RiskAgent", "action": "caution", "confidence": 0.8,
             "reason": "bad", "risk_flags": ["极端波动", "触及警戒线"]},
            {"agent": "DataAgent", "action": "caution", "confidence": 0.7,
             "reason": "bad", "risk_flags": ["总敞口超过100%"]},
        ]
        out = tools_committee.compute_committee_consensus(json.dumps(votes))
        data = json.loads(out)
        assert len(data["risk_flags"]) == 3
        assert data["human_review_needed"] is True
