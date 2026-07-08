"""
MCP Tool Registry — 自动发现与注册机制

使用装饰器 @register_mcp_tool 标记工具函数，server.py 自动扫描并注册所有工具。

示例：
    @register_mcp_tool(
        name="get_quote",
        description="获取股票最新行情",
        read_only=True,
        skill="market-quick-check",
    )
    def get_quote(ticker: str) -> str:
        ...
"""
from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Callable, Any


@dataclass
class MCPToolMetadata:
    name: str
    func: Callable[..., str]
    description: str
    read_only: bool = True
    skill: str | None = None
    annotations: dict[str, Any] = field(default_factory=dict)


_tools_registry: list[MCPToolMetadata] = []


def register_mcp_tool(
    name: str,
    description: str,
    read_only: bool = True,
    skill: str | None = None,
    **annotations: Any,
) -> Callable[[Callable[..., str]], Callable[..., str]]:
    """
    装饰器：注册 MCP 工具

    Args:
        name: 工具名称
        description: 工具描述（会自动添加 skill 引用）
        read_only: 是否只读操作（默认为 True）
        skill: 关联的 skill 名称（用于自动生成 skill 引用）
        **annotations: 额外的 MCP 注解

    Returns:
        装饰后的函数
    """
    def decorator(func: Callable[..., str]) -> Callable[..., str]:
        final_description = description
        if skill:
            final_description += f" 参见skill:{skill}"

        final_annotations = {"readOnlyHint": read_only}
        if annotations:
            final_annotations.update(annotations)

        _tools_registry.append(MCPToolMetadata(
            name=name,
            func=func,
            description=final_description,
            read_only=read_only,
            skill=skill,
            annotations=final_annotations,
        ))

        setattr(func, '_mcp_metadata', _tools_registry[-1])
        return func

    return decorator


def get_registered_tools() -> list[MCPToolMetadata]:
    """获取所有已注册的工具"""
    return _tools_registry


def register_to_mcp(mcp: Any) -> int:
    """
    将所有已注册的工具注册到 MCP Server

    Args:
        mcp: FastMCP 实例

    Returns:
        注册的工具数量
    """
    count = 0
    for tool_meta in _tools_registry:
        mcp.tool(
            name=tool_meta.name,
            description=tool_meta.description,
            annotations=tool_meta.annotations,
        )(tool_meta.func)
        count += 1
    return count


def discover_tools_from_module(module_name: str) -> None:
    """
    从指定模块发现并注册工具（通过导入模块触发装饰器执行）

    Args:
        module_name: 模块完整路径，如 "mcp_server.tools_data"
    """
    import importlib
    importlib.import_module(module_name)