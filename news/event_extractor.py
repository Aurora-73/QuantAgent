"""
事件抽取器（已废弃）

注意：本模块原依赖 LLM 进行事件抽取，项目定位调整为 MCP Server 后，
LLM 调用由外部 Agent 提供，不再在系统内部执行。

当前保留空壳仅为向后兼容，避免 import 报错。
实际事件采集走 daily_research.py 中的非 LLM 冷启动路径，
直接通过 news.aggregator 采集后写入 storage.events。
"""
from __future__ import annotations

import logging
from typing import Optional

from .schema import Event, NewsSource

logger = logging.getLogger(__name__)


class EventExtractor:
    """
    事件抽取器（已废弃 - 空壳实现）

    原功能：通过 LLM 从新闻文本抽取结构化 Event
    现状态：保留接口向后兼容，所有方法返回空列表

    替代方案：
      - 冷启动：daily_research.py 中直接从 aggregator 采集后写入 storage
      - 高质量抽取：由外部 Agent 通过 MCP 工具调用后回写
    """

    def __init__(self, api_key: str = None, model: str = "gpt-4o"):
        logger.warning(
            "EventExtractor 已废弃（内部 LLM 调用已移除）。"
            "事件冷启动请使用 daily_research.py 中的非 LLM 路径。"
        )

    def extract_from_sources(self, sources: list[NewsSource]) -> list[Event]:
        """空实现：返回空列表"""
        if sources:
            logger.info(
                f"EventExtractor 跳过 {len(sources)} 条新闻的事件抽取"
                "（LLM 模块已移除）"
            )
        return []
