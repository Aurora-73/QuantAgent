"""
MCP Server — MCP tools for Claude Code integration.

Tool organization (loveMentor pattern):
  tools_data.py      → market data, quotes, history, factors, indices
  tools_risk.py      → risk, stress test, Brinson, decay, backtest
  tools_knowledge.py → reports, events, wiki, decisions, sentiment

工具注册机制：
  使用 @register_mcp_tool 装饰器自动发现，无需手动注册。
  参见 mcp_server/registry.py。

Usage:
    python -m mcp_server.server           # stdio transport
    python -m mcp_server.server --sse     # SSE transport on :8080
    python -m mcp_server.server --list-tools  # 列出所有工具
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
from mcp_server.registry import discover_tools_from_module, register_to_mcp

# Resolve relative paths against project root (not CWD),
# because MCP clients may not honour cwd in config.
_project_root = Path(__file__).parent.parent
if settings.db_path and not Path(settings.db_path).is_absolute():
    settings.db_path = str((_project_root / settings.db_path).resolve())
if settings.knowledge_dir and not Path(settings.knowledge_dir).is_absolute():
    settings.knowledge_dir = str((_project_root / settings.knowledge_dir).resolve())
if settings.log_dir and not Path(settings.log_dir).is_absolute():
    settings.log_dir = str((_project_root / settings.log_dir).resolve())

# 自动发现所有工具模块（导入触发装饰器执行）
discover_tools_from_module("mcp_server.tools_data")
discover_tools_from_module("mcp_server.tools_risk")
discover_tools_from_module("mcp_server.tools_knowledge")
discover_tools_from_module("mcp_server.tools_committee")

# Import strategies to trigger @register_strategy decorators
import strategies.momentum.strategy  # noqa: F401
import strategies.event_driven.strategy  # noqa: F401
import strategies.sentiment.strategy  # noqa: F401
import strategies.regime_switch.strategy  # noqa: F401

mcp = FastMCP("quant-system", log_level="WARNING")

# ============================================================
# 自动注册所有已发现的工具
# ============================================================
tool_count = register_to_mcp(mcp)


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

    logger.info(f"MCP server ready: {tool_count} tools registered")

    if args.sse:
        logger.info(f"Starting SSE on :{args.port}")
        mcp.run(transport="sse", port=args.port)
    else:
        logger.info("Starting stdio server")
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
