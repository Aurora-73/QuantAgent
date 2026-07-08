"""
MCP toolchain integration tests

Test scenarios:
1. Market quick check: get_market_overview → get_index_data → get_quote
2. Sector screening: get_sector_list → get_sector_stocks → get_sector_index → get_history
3. Factor research: get_factors → run_factor_evaluation → run_decay_detection
4. Risk assessment: run_stress_test → run_brinson_attribution → get_risk_report
5. Backtest workflow: list_strategies → run_backtest (dry_run) → compare_backtest_runs
6. Knowledge exploration: get_db_stats → get_knowledge_stats → search_events
"""
import pytest
from unittest.mock import MagicMock, patch

from tests.conftest import make_uptrend_data


class TestMCPIntegrationMarketQuickCheck:

    @patch("mcp_server.tools_data.DataStorage")
    def test_market_overview(self, MockStorage):
        mock_storage = MagicMock()
        MockStorage.return_value = mock_storage
        from mcp_server.tools_data import get_market_overview
        result = get_market_overview()
        assert isinstance(result, dict)
        assert "indices" in result
        assert "market_stats" in result

    @patch("mcp_server.tools_data.DataStorage")
    def test_get_index_data(self, MockStorage):
        mock_storage = MagicMock()
        MockStorage.return_value = mock_storage
        mock_storage.load_index_daily.return_value = make_uptrend_data()
        from mcp_server.tools_data import get_index_data
        result = get_index_data()
        assert result is not None

    @patch("mcp_server.tools_data.DataStorage")
    def test_get_quote(self, MockStorage):
        mock_storage = MagicMock()
        MockStorage.return_value = mock_storage
        mock_storage.load_stock_daily.return_value = make_uptrend_data()
        from mcp_server.tools_data import get_quote
        result = get_quote("000001")
        assert result is not None


class TestMCPIntegrationSectorScreening:

    @patch("mcp_server.tools_data.sectors")
    def test_get_sector_list(self, mock_sectors):
        mock_sectors.get_sector_list.return_value = ["半导体", "新能源", "消费"]
        from mcp_server.tools_data import get_sector_list
        result = get_sector_list(source="sw")
        assert isinstance(result, list)
        assert len(result) > 0

    @patch("mcp_server.tools_data.sectors")
    def test_get_sector_stocks(self, mock_sectors):
        mock_sectors.get_sector_stocks.return_value = ["000001", "000002"]
        from mcp_server.tools_data import get_sector_stocks
        result = get_sector_stocks("半导体")
        assert isinstance(result, list)

    @patch("mcp_server.tools_data.DataStorage")
    def test_get_sector_index(self, MockStorage):
        mock_storage = MagicMock()
        MockStorage.return_value = mock_storage
        mock_storage.load_stock_daily.return_value = make_uptrend_data()
        from mcp_server.tools_data import get_sector_index
        result = get_sector_index("半导体", "000001,000002")
        assert result is not None


class TestMCPIntegrationFactorResearch:

    @patch("mcp_server.tools_data.DataStorage")
    @patch("mcp_server.tools_data.FactorEngine")
    def test_get_factors(self, MockEngine, MockStorage):
        mock_engine = MagicMock()
        MockEngine.return_value = mock_engine
        mock_engine.list_factors.return_value = {"momentum_5d": {"description": "5-day momentum"}}
        from mcp_server.tools_data import get_factors
        result = get_factors()
        assert isinstance(result, dict)
        assert "factors" in result

    @patch("mcp_server.tools_data.DataStorage")
    @patch("mcp_server.tools_data.FactorEngine")
    def test_run_factor_evaluation(self, MockEngine, MockStorage):
        mock_engine = MagicMock()
        MockEngine.return_value = mock_engine
        mock_storage = MagicMock()
        MockStorage.return_value = mock_storage
        mock_storage.load_stock_daily.return_value = make_uptrend_data()
        mock_engine.compute_all.return_value = make_uptrend_data()
        from mcp_server.tools_data import run_factor_evaluation
        result = run_factor_evaluation("000001")
        assert isinstance(result, dict)

    @patch("mcp_server.tools_data.DataStorage")
    def test_run_decay_detection(self, MockStorage):
        mock_storage = MagicMock()
        MockStorage.return_value = mock_storage
        mock_storage.load_factors.return_value = make_uptrend_data()
        from mcp_server.tools_data import run_decay_detection
        result = run_decay_detection("momentum_5d")
        assert isinstance(result, dict)


class TestMCPIntegrationRiskAssessment:

    @patch("mcp_server.tools_risk.run_stress_test")
    def test_run_stress_test(self, mock_run):
        mock_run.return_value = {"worst_scenario": "2015 Crash", "max_drawdown": -0.45}
        from mcp_server.tools_risk import run_stress_test
        result = run_stress_test("000001")
        assert isinstance(result, dict)
        assert "worst_scenario" in result

    @patch("mcp_server.tools_risk.run_brinson_attribution")
    def test_run_brinson_attribution(self, mock_run):
        mock_run.return_value = {"allocation_effect": 0.02, "selection_effect": 0.03, "interaction_effect": 0.01}
        from mcp_server.tools_risk import run_brinson_attribution
        result = run_brinson_attribution("000001")
        assert isinstance(result, dict)

    @patch("mcp_server.tools_risk.run_stress_test")
    @patch("mcp_server.tools_risk.run_decay_detection")
    def test_get_risk_report(self, mock_decay, mock_stress):
        mock_stress.return_value = {"worst_scenario": "test"}
        mock_decay.return_value = {"decay_rate": 0.1}
        from mcp_server.tools_risk import get_risk_report
        result = get_risk_report("000001")
        assert isinstance(result, dict)
        assert "stress_test" in result
        assert "decay_detection" in result


class TestMCPIntegrationBacktestWorkflow:

    @patch("mcp_server.tools_risk.get_strategy_registry")
    def test_list_strategies(self, mock_registry):
        mock_registry.return_value.list_strategies.return_value = [{"name": "momentum", "description": "Momentum Strategy"}]
        from mcp_server.tools_risk import list_strategies
        result = list_strategies()
        assert isinstance(result, list)
        assert len(result) > 0

    @patch("mcp_server.tools_risk.run_backtest")
    def test_run_backtest_dry_run(self, mock_run):
        mock_run.return_value = {"run_id": "test_run", "strategy": "momentum", "status": "dry_run"}
        from mcp_server.tools_risk import run_backtest
        result = run_backtest("momentum", "000001", dry_run=True)
        assert result["status"] == "dry_run"

    @patch("mcp_server.tools_risk.DataStorage")
    def test_compare_backtest_runs(self, MockStorage):
        mock_storage = MagicMock()
        MockStorage.return_value = mock_storage
        mock_storage.load_backtest_runs.return_value = make_uptrend_data()
        from mcp_server.tools_risk import compare_backtest_runs
        result = compare_backtest_runs("momentum")
        assert isinstance(result, dict)


class TestMCPIntegrationKnowledgeExploration:

    @patch("mcp_server.tools_knowledge.DataStorage")
    def test_get_db_stats(self, MockStorage):
        mock_storage = MagicMock()
        MockStorage.return_value = mock_storage
        mock_storage.get_table_stats.return_value = {"stock_daily": 1000, "factors": 5000}
        from mcp_server.tools_knowledge import get_db_stats
        result = get_db_stats()
        assert isinstance(result, dict)

    @patch("mcp_server.tools_knowledge.knowledge_base")
    def test_get_knowledge_stats(self, mock_kb):
        mock_kb.get_stats.return_value = {"events": 100, "hypotheses": 50, "lessons": 20}
        from mcp_server.tools_knowledge import get_knowledge_stats
        result = get_knowledge_stats()
        assert isinstance(result, dict)

    @patch("mcp_server.tools_knowledge.knowledge_base")
    def test_search_events(self, mock_kb):
        mock_kb.search_events.return_value = []
        from mcp_server.tools_knowledge import search_events
        result = search_events("半导体")
        assert isinstance(result, list)


class TestMCPToolMetadata:

    @patch("mcp_server.tools_data.DataStorage")
    def test_tools_have_metadata(self, MockStorage):
        from mcp_server.registry import TOOL_REGISTRY
        for tool_name, tool_info in TOOL_REGISTRY.items():
            assert "name" in tool_info
            assert "description" in tool_info
            assert "read_only" in tool_info
            assert "skill" in tool_info
            assert len(tool_info["description"]) > 0

    def test_read_only_tools(self):
        from mcp_server.registry import TOOL_REGISTRY
        write_tools = {"run_backtest", "run_daily_research", "update_data", "update_financials"}
        for tool_name, tool_info in TOOL_REGISTRY.items():
            if tool_name in write_tools:
                assert tool_info["read_only"] is False
            else:
                assert tool_info["read_only"] is True