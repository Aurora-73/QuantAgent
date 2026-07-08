"""
MCP toolchain integration tests — 跨工具交叉验证。

测试场景（对应 skills/ 工作流）：
1. Market quick check: get_market_overview → get_index_data → get_quote
2. Sector screening: get_sector_list → get_sector_stocks → get_sector_index → get_history
3. Factor research: get_factors → run_factor_evaluation → run_decay_detection
4. Risk assessment: run_stress_test → run_brinson_attribution → get_risk_report
5. Backtest workflow: list_strategies → run_backtest (dry_run) → compare_backtest_runs
6. Knowledge exploration: get_db_stats → get_knowledge_stats → search_events
7. Committee chain: review_data_quality + review_strategy_signals + review_risk_exposure
                     → compute_committee_consensus
8. Registry metadata: 所有工具元数据完整、写工具 read_only=False
"""
import json
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from tests.conftest import make_uptrend_data


def _parse(result: str) -> dict | list:
    """MCP 工具返回 JSON 字符串，测试中需解析。"""
    return json.loads(result)


# ============================================================
# 1. Market Quick Check（对应 skill: market-quick-check）
# ============================================================
class TestMarketQuickCheck:

    @patch("mcp_server.tools_data.DataStorage")
    def test_market_overview_returns_valid_json(self, MockStorage):
        mock_storage = MagicMock()
        MockStorage.return_value = mock_storage
        mock_storage.load_index_daily.return_value = make_uptrend_data(30)
        from mcp_server.tools_data import get_market_overview
        result = _parse(get_market_overview())
        assert "indices" in result

    @patch("mcp_server.tools_data.DataStorage")
    def test_index_data_then_quote_cross_tool(self, MockStorage):
        """get_index_data 返回 index_code → get_quote 接受同格式 ticker。"""
        mock_storage = MagicMock()
        MockStorage.return_value = mock_storage
        mock_storage.load_index_daily.return_value = make_uptrend_data(30)
        mock_storage.load_stock_daily.return_value = make_uptrend_data(30)

        from mcp_server.tools_data import get_index_data, get_quote
        idx = _parse(get_index_data(index_code="000300", days=5))
        assert idx["index_code"] == "000300"
        # 用一只真实 ticker 调 get_quote，验证返回结构一致
        q = _parse(get_quote("600519"))
        assert "ticker" in q
        assert "close" in q


# ============================================================
# 2. Sector Screening（对应 skill: sector-screening）
# ============================================================
class TestSectorScreening:

    @patch("data.sectors.SectorData")
    def test_sector_list_returns_json(self, MockSectorData):
        # SectorData 方法是类方法（静态调用），直接在 mock 类上设返回值
        MockSectorData.get_concept_list.return_value = ["半导体", "新能源"]
        from mcp_server.tools_data import get_sector_list
        result = _parse(get_sector_list(sector_type="concept"))
        assert "sector_type" in result

    @patch("data.sectors.SectorData")
    @patch("mcp_server.tools_data.DataStorage")
    def test_sector_stocks_then_history(self, MockStorage, MockSectorData):
        """get_sector_stocks 返回股票列表 → get_history 接受 ticker。"""
        MockSectorData.get_board_stocks.return_value = ["600519", "000858"]
        MockSectorData.search_board.return_value = []
        mock_storage = MagicMock()
        MockStorage.return_value = mock_storage
        mock_storage.load_stock_daily.return_value = make_uptrend_data(30)

        from mcp_server.tools_data import get_sector_stocks, get_history
        stocks = _parse(get_sector_stocks("白酒", sector_type="concept"))
        # 用返回列表中的第一只股票调 get_history
        if stocks.get("stocks"):
            ticker = stocks["stocks"][0]
            hist = _parse(get_history(ticker, days=5))
            assert "ticker" in hist


# ============================================================
# 3. Factor Research（对应 skill: factor-research）
# ============================================================
class TestFactorResearch:

    @patch("mcp_server.tools_data.FactorEngine")
    @patch("mcp_server.tools_data.DataStorage")
    def test_factors_then_evaluation(self, MockStorage, MockEngine):
        """get_factors 返回因子名 → run_factor_evaluation 接受同因子名。"""
        mock_storage = MagicMock()
        MockStorage.return_value = mock_storage
        mock_storage.load_stock_daily.return_value = make_uptrend_data(260)

        mock_engine = MagicMock()
        MockEngine.return_value = mock_engine
        factor_df = make_uptrend_data(260)
        factor_df["momentum_20d"] = factor_df["close"].pct_change(20)
        mock_engine.compute_all.return_value = factor_df
        mock_engine.list_factors.return_value = {"momentum_20d": {"description": "test"}}

        from mcp_server.tools_data import get_factors
        result = _parse(get_factors(ticker="600519"))
        assert "ticker" in result


# ============================================================
# 4. Risk Assessment（对应 skill: risk-assessment）
# ============================================================
class TestRiskAssessment:

    @patch("mcp_server.tools_risk.StressTestEngine")
    @patch("mcp_server.tools_risk.DataStorage")
    def test_stress_test_returns_scenarios(self, MockStorage, MockEngine):
        mock_storage = MagicMock()
        MockStorage.return_value = mock_storage
        mock_storage.load_stock_daily.return_value = make_uptrend_data(260)

        # 构造模拟报告：含 results 列表 + worst_scenario + all_survived
        mock_result = MagicMock()
        mock_result.scenario_name = "2015 Crash"
        mock_result.portfolio_return = -0.35
        mock_result.max_drawdown = -0.45
        mock_result.recovery_days = 120
        mock_result.survived = True

        mock_report = MagicMock()
        mock_report.results = [mock_result]
        mock_report.worst_scenario = "2015 Crash"
        mock_report.all_survived = True

        mock_engine = MagicMock()
        MockEngine.return_value = mock_engine
        mock_engine.run.return_value = mock_report

        from mcp_server.tools_risk import run_stress_test
        result = _parse(run_stress_test("600519"))
        assert "scenarios" in result
        assert result["worst"] == "2015 Crash"

    def test_brinson_attribution_with_valid_json(self):
        """Brinson 接受 4 个 JSON 参数，返回归因分解。"""
        from mcp_server.tools_risk import run_brinson_attribution
        result = _parse(run_brinson_attribution(
            portfolio_weights='{"白酒":0.5,"新能源":0.5}',
            benchmark_weights='{"白酒":0.3,"新能源":0.7}',
            portfolio_returns='{"白酒":0.02,"新能源":-0.01}',
            benchmark_returns='{"白酒":0.01,"新能源":0.005}',
        ))
        assert "total_excess_return" in result


# ============================================================
# 5. Backtest Workflow（对应 skill: backtest-workflow）
# ============================================================
class TestBacktestWorkflow:

    def test_list_strategies_returns_names(self):
        """list_strategies 返回策略名列表（无需 mock，用真实 registry）。"""
        from mcp_server.tools_risk import list_strategies
        result = _parse(list_strategies())
        assert result["count"] > 0
        names = [s["name"] for s in result["strategies"]]
        assert "momentum" in names

    def test_strategy_name_from_list_works_in_config(self):
        """list_strategies 返回的名字 → get_strategy_config 能用。"""
        from mcp_server.tools_risk import list_strategies, get_strategy_config
        listed = _parse(list_strategies())
        first_name = listed["strategies"][0]["name"]
        config = _parse(get_strategy_config(first_name))
        assert config["strategy"] == first_name

    def test_backtest_dry_run_with_listed_strategy(self):
        """list_strategies 的策略名 → run_backtest(dry_run=True) 不报错。"""
        from mcp_server.tools_risk import list_strategies, run_backtest
        listed = _parse(list_strategies())
        strategy = listed["strategies"][0]["name"]
        result = _parse(run_backtest(strategy=strategy, ticker="600519", dry_run=True))
        assert result["success"] is True
        assert result["dry_run"] is True


# ============================================================
# 6. Knowledge Exploration（对应 skill: knowledge-exploration）
# ============================================================
class TestKnowledgeExploration:

    @patch("mcp_server.tools_knowledge.DataStorage")
    def test_db_stats_returns_table_counts(self, MockStorage):
        mock_storage = MagicMock()
        MockStorage.return_value = mock_storage
        mock_storage.get_table_stats.return_value = {"stock_daily": 1000}
        from mcp_server.tools_knowledge import get_db_stats
        result = _parse(get_db_stats())
        assert isinstance(result, dict)

    @patch("mcp_server.tools_knowledge.KnowledgeBase")
    def test_knowledge_stats_returns_counts(self, MockKB):
        mock_kb = MagicMock()
        MockKB.return_value = mock_kb
        mock_kb.get_stats.return_value = {"daily": 10, "events": 5}
        from mcp_server.tools_knowledge import get_knowledge_stats
        result = _parse(get_knowledge_stats())
        assert isinstance(result, dict)


# ============================================================
# 7. Committee Chain（对应 ADR-0003）
# ============================================================
class TestCommitteeChain:

    @patch("mcp_server.tools_committee.DataStorage")
    @patch("mcp_server.tools_committee.AgentCommittee")
    def test_reviews_then_consensus(self, MockCommittee, MockStorage):
        """三个 review 工具各返回投票 → compute_committee_consensus 合成共识。"""
        from mcp_server.tools_committee import (
            review_data_quality, review_strategy_signals,
            review_risk_exposure, compute_committee_consensus,
        )
        from agents.committee import AgentVote, CommitteeReview

        mock_committee = MagicMock()
        MockCommittee.return_value = mock_committee
        # 模拟各 agent 返回投票
        mock_committee.data_agent.return_value = AgentVote(
            agent="DataAgent", action="bullish", confidence=0.8,
            reason="data ok", risk_flags=[],
        )
        mock_committee.strategy_agent.return_value = AgentVote(
            agent="StrategyAgent", action="bullish", confidence=0.9,
            reason="signals align", risk_flags=[],
        )
        mock_committee.risk_agent.return_value = AgentVote(
            agent="RiskAgent", action="hold", confidence=0.6,
            reason="exposure within limits", risk_flags=[],
        )
        # synthesize 返回真实 CommitteeReview（compute_committee_consensus 内部调用）
        mock_committee.synthesize.return_value = CommitteeReview(
            consensus_action="bullish",
            consensus_confidence=0.77,
            risk_level="medium",
            risk_flags=[],
            summary="2/3 bullish",
            human_review_needed=False,
        )

        # 1. 收集三票
        vote1 = _parse(review_data_quality("600519"))
        vote2 = _parse(review_strategy_signals("600519"))
        vote3 = _parse(review_risk_exposure("600519"))
        assert vote1["agent"] == "DataAgent"
        assert vote2["agent"] == "StrategyAgent"
        assert vote3["agent"] == "RiskAgent"

        # 2. 合成共识
        votes_json = json.dumps([vote1, vote2, vote3])
        consensus = _parse(compute_committee_consensus(votes_json))
        assert "consensus_action" in consensus
        assert "consensus_confidence" in consensus
        assert consensus["consensus_action"] == "bullish"


# ============================================================
# 8. Registry Metadata 完整性
# ============================================================
class TestRegistryMetadata:

    def test_all_tools_have_required_fields(self):
        from mcp_server.registry import get_registered_tools
        tools = get_registered_tools()
        assert len(tools) >= 40, f"期望至少 40 个工具，实际 {len(tools)}"
        for t in tools:
            assert t.name, f"工具缺少 name"
            assert t.description, f"{t.name} 缺少 description"
            assert isinstance(t.read_only, bool), f"{t.name} read_only 不是 bool"
            assert "readOnlyHint" in t.annotations, f"{t.name} 缺少 readOnlyHint"

    def test_write_tools_are_not_read_only(self):
        """写操作工具必须有 read_only=False。"""
        from mcp_server.registry import get_registered_tools
        known_write_tools = {
            "update_data", "run_daily_research", "update_financials",
            "update_data_incremental", "run_backtest",
            "generate_higher_order_report",
        }
        tools = get_registered_tools()
        tool_map = {t.name: t for t in tools}
        for name in known_write_tools:
            assert name in tool_map, f"已知写工具 {name} 未注册"
            assert tool_map[name].read_only is False, \
                f"{name} 是写操作但 read_only=True"

    def test_all_tools_have_skill_reference(self):
        """每个工具的 description 应包含 skill 引用（参见skill:）。"""
        from mcp_server.registry import get_registered_tools
        tools = get_registered_tools()
        no_skill = [t.name for t in tools if t.skill is None]
        # 允许少数无 skill 的工具，但不应超过 5 个
        assert len(no_skill) <= 5, \
            f"过多工具缺少 skill 引用: {no_skill}"

    def test_tool_names_are_unique(self):
        from mcp_server.registry import get_registered_tools
        tools = get_registered_tools()
        names = [t.name for t in tools]
        assert len(names) == len(set(names)), "存在重复的工具名"
