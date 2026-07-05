"""
新闻去重与事件归并

核心问题：
  同一条 NVIDIA 财报消息，被 Reuters、Bloomberg、Yahoo、CNBC 转发了 50 次。
  如果不做事件归并，LLM 会误以为出现了 50 个利好事件。

解决方案：
  1. 基于 dedup_key 做精确去重（同一事件多个报道合并）
  2. 基于 (symbol, event_type, time_window) 做模糊去重
  3. 多信源确认提高置信度
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta
from typing import Optional

from .schema import Event, NewsSource, SourceTier, EventType, Sentiment


class EventDeduplicator:
    """
    事件去重器

    设计原则：
      - 同一事件的多个报道合并为一个 Event
      - 多信源确认提高置信度
      - 不同事件（即使同一公司）不合并
    """

    def __init__(self, time_window_hours: int = 24):
        """
        Args:
            time_window_hours: 同一事件的时间窗口（小时）
        """
        self.time_window = timedelta(hours=time_window_hours)
        self._events: dict[str, Event] = {}  # dedup_key -> Event

    def process(self, event: Event) -> Event:
        """
        处理一个事件，自动去重归并

        Args:
            event: 新事件

        Returns:
            归并后的事件（如果是新事件则返回原事件）
        """
        dedup_key = event.dedup_key or self._generate_dedup_key(event)

        if dedup_key in self._events:
            existing = self._events[dedup_key]
            # 合并信源
            for source in event.sources:
                existing.add_source(source)
            return existing
        else:
            event.dedup_key = dedup_key
            self._events[dedup_key] = event
            return event

    def process_batch(self, events: list[Event]) -> list[Event]:
        """批量处理事件"""
        result = []
        for event in events:
            result.append(self.process(event))
        return self.get_all_events()

    def get_all_events(self) -> list[Event]:
        """获取所有去重后的事件"""
        return list(self._events.values())

    def get_by_symbol(self, symbol: str) -> list[Event]:
        """按股票代码筛选"""
        return [e for e in self._events.values() if e.symbol == symbol]

    def get_by_type(self, event_type: EventType) -> list[Event]:
        """按事件类型筛选"""
        return [e for e in self._events.values() if e.event_type == event_type]

    def get_high_confidence(self, min_confidence: float = 0.7) -> list[Event]:
        """获取高置信度事件"""
        return [
            e for e in self._events.values()
            if e.weighted_confidence >= min_confidence
        ]

    def get_multi_source_events(self, min_sources: int = 2) -> list[Event]:
        """获取多信源确认的事件"""
        return [
            e for e in self._events.values()
            if e.source_count >= min_sources
        ]

    def clear(self):
        """清空事件库"""
        self._events.clear()

    # ============================================================
    # 去重键生成
    # ============================================================

    def _generate_dedup_key(self, event: Event) -> str:
        """
        生成去重键

        策略：
          1. 同一公司 + 同一事件类型 + 同一天 → 同一事件
          2. 财报类事件用 (symbol, "earnings", quarter) 去重
          3. 其他事件用 (symbol, event_type, date) 去重
        """
        symbol = event.symbol.upper().strip()
        event_type = event.event_type
        date_str = event.timestamp.strftime("%Y-%m-%d")

        # 财报类事件特殊处理
        if event_type in ("earnings_beat", "earnings_miss", "earnings_in_line"):
            quarter = self._extract_quarter(event.detail)
            key = f"{symbol}:earnings:{quarter}"
        else:
            key = f"{symbol}:{event_type}:{date_str}"

        return hashlib.md5(key.encode()).hexdigest()[:16]

    @staticmethod
    def _extract_quarter(text: str) -> str:
        """从文本中提取季度信息"""
        # 匹配 Q1/Q2/Q3/Q4 或 第一季度 等
        patterns = [
            r"Q[1-4]",
            r"第[一二三四]季度",
            r"[1-4]季度",
            r"FY\d{4}Q[1-4]",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group()
        return "unknown"


class NewsDeduplicator:
    """
    新闻去重器（在事件抽取之前）

    处理原始新闻文本的去重：
      - 相似标题去重
      - 相同来源去重
      - 时间窗口内重复内容去重
    """

    def __init__(self, similarity_threshold: float = 0.8):
        self.similarity_threshold = similarity_threshold
        self._seen_titles: list[str] = []
        self._seen_hashes: set[str] = set()

    def is_duplicate(self, title: str, content: str = "",
                     source: str = "") -> bool:
        """
        检查是否重复

        Args:
            title: 新闻标题
            content: 新闻内容（可选）
            source: 来源

        Returns:
            是否重复
        """
        # 1. 精确哈希去重
        content_hash = hashlib.md5(
            (title + content).encode()
        ).hexdigest()[:16]
        if content_hash in self._seen_hashes:
            return True

        # 2. 标题相似度去重
        normalized = self._normalize_title(title)
        for seen in self._seen_titles:
            if self._similarity(normalized, seen) >= self.similarity_threshold:
                return True

        # 不重复，记录
        self._seen_hashes.add(content_hash)
        self._seen_titles.append(normalized)
        return False

    def clear(self):
        """清空"""
        self._seen_titles.clear()
        self._seen_hashes.clear()

    @staticmethod
    def _normalize_title(title: str) -> str:
        """标题标准化"""
        # 去除标点、空格、特殊字符
        title = re.sub(r"[^\w\s]", "", title)
        title = re.sub(r"\s+", " ", title).strip().lower()
        return title

    @staticmethod
    def _similarity(a: str, b: str) -> float:
        """简单相似度（Jaccard）"""
        set_a = set(a.split())
        set_b = set(b.split())
        if not set_a or not set_b:
            return 0.0
        intersection = set_a & set_b
        union = set_a | set_b
        return len(intersection) / len(union)
