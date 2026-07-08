"""
MCP Server — MCP tools for Claude Code integration.

Tool organization (loveMentor pattern):
  tools_data.py      → market data, quotes, history, factors, indices
  tools_risk.py      → risk, stress test, Brinson, decay, backtest
  tools_knowledge.py → reports, events, wiki, decisions, sentiment

Usage:
    python -m mcp_server.server           # stdio transport
    python -m mcp_server.server --sse     # SSE transport on :8080
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

try:
    from mcp.server.fastmcp import FastMCP
    HAS_FASTMCP = True
except ImportError:
    HAS_FASTMCP = False

from configs.settings import settings

# Resolve relative paths against project root (not CWD),
# because MCP clients may not honour cwd in config.
_project_root = Path(__file__).parent.parent
if settings.db_path and not Path(settings.db_path).is_absolute():
    settings.db_path = str((_project_root / settings.db_path).resolve())
if settings.knowledge_dir and not Path(settings.knowledge_dir).is_absolute():
    settings.knowledge_dir = str((_project_root / settings.knowledge_dir).resolve())
if settings.log_dir and not Path(settings.log_dir).is_absolute():
    settings.log_dir = str((_project_root / settings.log_dir).resolve())

# Import all tool modules (plain functions)
from mcp_server import tools_data
from mcp_server import tools_risk
from mcp_server import tools_knowledge

# Import strategies to trigger @register_strategy decorators
import strategies.momentum.strategy  # noqa: F401
import strategies.event_driven.strategy  # noqa: F401
import strategies.sentiment.strategy  # noqa: F401
import strategies.regime_switch.strategy  # noqa: F401

mcp = FastMCP("quant-system", log_level="WARNING")


# ============================================================
# Data Tools
# ============================================================

mcp.tool(
    name="get_quote",
    description="获取指定股票的最新行情数据。用于市场快速检查，参见skill:market-quick-check",
    annotations={"readOnlyHint": True},
)(tools_data.get_quote)

mcp.tool(
    name="get_history",
    description="获取股票历史行情数据。用于行业选股分析，参见skill:sector-screening",
    annotations={"readOnlyHint": True},
)(tools_data.get_history)

mcp.tool(
    name="get_factors",
    description="获取已注册的因子列表或指定因子的数值。用于因子研究，参见skill:factor-research",
    annotations={"readOnlyHint": True},
)(tools_data.get_factors)

mcp.tool(
    name="get_index_data",
    description="获取指数行情数据（默认沪深300）。用于市场快速检查和行业选股，参见skill:market-quick-check, skill:sector-screening",
    annotations={"readOnlyHint": True},
)(tools_data.get_index_data)

mcp.tool(
    name="get_universe",
    description="获取系统跟踪的股票列表。用于市场快速检查，参见skill:market-quick-check",
    annotations={"readOnlyHint": True},
)(tools_data.get_universe)

mcp.tool(
    name="get_market_overview",
    description="获取市场概况（指数行情 + 涨跌统计）。用于行业选股和每日研究，参见skill:sector-screening, skill:daily-workflow",
    annotations={"readOnlyHint": True},
)(tools_data.get_market_overview)

mcp.tool(
    name="search_tickers",
    description="搜索股票代码。用于行业选股备选，参见skill:sector-screening",
    annotations={"readOnlyHint": True},
)(tools_data.search_tickers)

mcp.tool(
    name="get_calendar",
    description="获取交易日历。用于市场快速检查，参见skill:market-quick-check",
    annotations={"readOnlyHint": True},
)(tools_data.get_calendar)

mcp.tool(
    name="run_factor_evaluation",
    description="运行因子评估（IC/ICIR/评分）。用于因子研究，参见skill:factor-research",
    annotations={"readOnlyHint": True},
)(tools_data.run_factor_evaluation)

# ── 行业/概念板块工具 ──

mcp.tool(
    name="get_sector_list",
    description="获取行业板块或概念板块列表（申万行业 / 东方财富概念板块）。用于行业选股，参见skill:sector-screening",
    annotations={"readOnlyHint": True},
)(tools_data.get_sector_list)

mcp.tool(
    name="get_sector_stocks",
    description="获取指定板块的成分股列表，如 get_sector_stocks('半导体') 返回半导体概念股。用于行业选股，参见skill:sector-screening",
    annotations={"readOnlyHint": True},
)(tools_data.get_sector_stocks)

mcp.tool(
    name="get_sector_index",
    description="构建并返回板块等权指数日线数据，从所有成分股日线构建。首次调用耗时 30s-2min。用于行业选股，参见skill:sector-screening",
    annotations={"readOnlyHint": True},
)(tools_data.get_sector_index)

mcp.tool(
    name="update_data",
    description="更新行情数据（从 AKShare/baostock 拉取最新数据并写入数据库）。注意：写操作，耗时 15-30 分钟。用于每日研究，参见skill:daily-workflow",
    annotations={"readOnlyHint": False},
)(tools_data.update_data)

mcp.tool(
    name="run_daily_research",
    description="运行每日研究流程（数据更新→因子计算→新闻采集→日报生成）。注意：写操作，耗时 5-15 分钟。用于每日研究，参见skill:daily-workflow",
    annotations={"readOnlyHint": False},
)(tools_data.run_daily_research)

# ============================================================
# Risk # Risk & Strategy Tools (10, read-only) Strategy Tools
# ============================================================

mcp.tool(
    name="run_stress_test",
    description="运行压力测试（4个历史危机场景，含2015/2018/2020/2024）。用于风险评估，参见skill:risk-assessment",
    annotations={"readOnlyHint": True},
)(tools_risk.run_stress_test)

mcp.tool(
    name="run_brinson_attribution",
    description="运行 Brinson 收益归因（配置效应 + 选股效应 + 交互效应）。用于风险评估，参见skill:risk-assessment",
    annotations={"readOnlyHint": True},
)(tools_risk.run_brinson_attribution)

mcp.tool(
    name="run_decay_detection",
    description="运行策略衰减检测（胜率/IC/衰减速度）。用于因子研究和风险评估，参见skill:factor-research, skill:risk-assessment",
    annotations={"readOnlyHint": True},
)(tools_risk.run_decay_detection)

mcp.tool(
    name="get_risk_report",
    description="综合风险报告（压力测试 + 衰减检测）。用于风险评估，参见skill:risk-assessment",
    annotations={"readOnlyHint": True},
)(tools_risk.get_risk_report)

mcp.tool(
    name="list_strategies",
    description="列出已注册的交易策略。用于回测工作流，参见skill:backtest-workflow",
    annotations={"readOnlyHint": True},
)(tools_risk.list_strategies)

mcp.tool(
    name="get_strategy_config",
    description="获取策略配置参数。用于回测工作流，参见skill:backtest-workflow",
    annotations={"readOnlyHint": True},
)(tools_risk.get_strategy_config)

mcp.tool(
    name="run_backtest",
    description="运行回测（指定策略、股票、日期范围）。注意：写操作。用于回测工作流，参见skill:backtest-workflow",
    annotations={"readOnlyHint": False},
)(tools_risk.run_backtest)

mcp.tool(
    name="compare_backtest_runs",
    description="对比最近多次回测结果。用于回测工作流，参见skill:backtest-workflow",
    annotations={"readOnlyHint": True},
)(tools_risk.compare_backtest_runs)

mcp.tool(
    name="run_health_check",
    description="运行系统健康检查。用于知识探索和每日研究，参见skill:knowledge-exploration, skill:daily-workflow",
    annotations={"readOnlyHint": True},
)(tools_risk.run_health_check)

mcp.tool(
    name="get_market_regime",
    description="获取当前市场状态识别结果。用于风险评估，参见skill:risk-assessment",
    annotations={"readOnlyHint": True},
)(tools_risk.get_market_regime)

# ============================================================
# Knowledge # Knowledge & Decision Tools (11, read-only) Decision Tools
# ============================================================

mcp.tool(
    name="get_daily_report",
    description="获取指定日期的研究报告。用于每日研究，参见skill:daily-workflow",
    annotations={"readOnlyHint": True},
)(tools_knowledge.get_daily_report)

mcp.tool(
    name="search_events",
    description="搜索结构化金融事件。用于知识探索，参见skill:knowledge-exploration",
    annotations={"readOnlyHint": True},
)(tools_knowledge.search_events)

mcp.tool(
    name="wiki_search",
    description="搜索交易方法论文档。用于知识探索，参见skill:knowledge-exploration",
    annotations={"readOnlyHint": True},
)(tools_knowledge.wiki_search)

mcp.tool(
    name="get_knowledge_stats",
    description="获取知识库统计信息。用于知识探索，参见skill:knowledge-exploration",
    annotations={"readOnlyHint": True},
)(tools_knowledge.get_knowledge_stats)

mcp.tool(
    name="get_recent_events",
    description="获取最近事件列表。用于知识探索，参见skill:knowledge-exploration",
    annotations={"readOnlyHint": True},
)(tools_knowledge.get_recent_events)

mcp.tool(
    name="get_decision_accuracy",
    description="查询决策记忆准确率。用于知识探索，参见skill:knowledge-exploration",
    annotations={"readOnlyHint": True},
)(tools_knowledge.get_decision_accuracy)

mcp.tool(
    name="get_recent_decisions",
    description="获取最近决策记录。用于知识探索，参见skill:knowledge-exploration",
    annotations={"readOnlyHint": True},
)(tools_knowledge.get_recent_decisions)

mcp.tool(
    name="get_prediction_accuracy",
    description="获取预测准确率统计。用于知识探索，参见skill:knowledge-exploration",
    annotations={"readOnlyHint": True},
)(tools_knowledge.get_prediction_accuracy)

mcp.tool(
    name="get_db_stats",
    description="获取数据库各表行数统计。用于知识探索，参见skill:knowledge-exploration",
    annotations={"readOnlyHint": True},
)(tools_knowledge.get_db_stats)

mcp.tool(
    name="get_social_sentiment",
    description="获取社交情绪分析结果。用于知识探索，参见skill:knowledge-exploration",
    annotations={"readOnlyHint": True},
)(tools_knowledge.get_social_sentiment)

mcp.tool(
    name="search_hypotheses",
    description="搜索投资假设库。用于知识探索，参见skill:knowledge-exploration",
    annotations={"readOnlyHint": True},
)(tools_knowledge.search_hypotheses)

# ============================================================
# Main
# ============================================================

def list_tools():
    """列出所有已注册的 MCP 工具，作为工具数量的事实来源。

    用法：python -m mcp_server.server --list-tools
    """
    if not hasattr(mcp, '_tool_manager'):
        print("ERROR: mcp._tool_manager 不可用（fastmcp 版本不兼容）")
        sys.exit(1)

    tools = mcp._tool_manager._tools
    print(f"# MCP 工具清单（共 {len(tools)} 个）")
    print()
    print(f"{'#':>3}  {'name':<28}  {'readonly':<8}  description")
    print("-" * 100)
    for i, (name, tool) in enumerate(sorted(tools.items()), 1):
        desc = (tool.description or "").replace("\n", " ")[:60]
        annotations = getattr(tool, 'annotations', None)
        # FastMCP annotations 是 ToolAnnotations pydantic 对象，用 model_dump() 转 dict
        if annotations is None:
            readonly = "no"
        elif isinstance(annotations, dict):
            readonly = "yes" if annotations.get("readOnlyHint") else "no"
        elif hasattr(annotations, 'model_dump'):
            readonly = "yes" if annotations.model_dump().get("readOnlyHint") else "no"
        else:
            readonly = "yes" if getattr(annotations, 'readOnlyHint', False) else "no"
        print(f"{i:>3}  {name:<28}  {readonly:<8}  {desc}")
    print()
    print(f"总计: {len(tools)} 个工具")


def main():
    if not HAS_FASTMCP:
        print("fastmcp 未安装: pip install fastmcp")
        sys.exit(1)

    import argparse
    parser = argparse.ArgumentParser(description="MCP Server for Quant System")
    parser.add_argument("--sse", action="store_true", help="Use SSE transport (default: stdio)")
    parser.add_argument("--port", type=int, default=8080, help="SSE port")
    parser.add_argument("--list-tools", action="store_true",
                        help="List all registered tools and exit (不启动 server)")
    args = parser.parse_args()

    if args.list_tools:
        list_tools()
        return

    tool_count = len(mcp._tool_manager._tools) if hasattr(mcp, '_tool_manager') else 0
    logger.info(f"MCP server ready: {tool_count} tools registered")

    if args.sse:
        logger.info(f"Starting SSE on :{args.port}")
        mcp.run(transport="sse", port=args.port)
    else:
        logger.info("Starting stdio server")
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
