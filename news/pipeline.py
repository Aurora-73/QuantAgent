"""
新闻处理流水线

完整流程：
  新闻采集 → 去重 → 事件抽取 → 事件归并 → 知识库

设计原则：
  - 存事件，不存新闻全文
  - 同一事件多个报道合并
  - 多信源确认提高置信度
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from .collector import NewsCollector, get_collector, get_all_collectors
from .deduplicator import EventDeduplicator, NewsDeduplicator
from .event_extractor import EventExtractor
from .schema import Event, NewsSource, SourceTier

logger = logging.getLogger(__name__)


class NewsPipeline:
    """
    新闻处理流水线

    用法：
        pipeline = NewsPipeline()

        # 指定采集器
        events = pipeline.run(symbol="NVDA", collectors=["yahoo", "openbb"])

        # 使用所有可用采集器
        events = pipeline.run(symbol="600519.SS")

        # 查看结果
        for event in events:
            print(f"{event.event_type.value}: {event.detail} (置信度: {event.weighted_confidence:.2f}, 信源: {event.source_count})")
    """

    def __init__(self, api_key: str = None, model: str = "gpt-4o",
                 knowledge_dir: str = "knowledge",
                 time_window_hours: int = 24):
        self.extractor = EventExtractor(api_key=api_key, model=model)
        self.event_dedup = EventDeduplicator(time_window_hours=time_window_hours)
        self.news_dedup = NewsDeduplicator()
        self.knowledge_dir = Path(knowledge_dir)
        self.events_dir = self.knowledge_dir / "events"
        self.events_dir.mkdir(parents=True, exist_ok=True)

    def run(self, symbol: str = None,
            collectors: list[str] = None,
            limit_per_source: int = 20,
            save: bool = True) -> list[Event]:
        """
        运行完整流水线

        Args:
            symbol: 股票代码
            collectors: 采集器名称列表（None 则用所有可用的）
            limit_per_source: 每个采集器最大条数
            save: 是否保存到知识库

        Returns:
            去重归并后的 Event 列表
        """
        # 1. 采集
        logger.info(f"开始采集: symbol={symbol}, collectors={collectors}")
        sources = self._collect(symbol, collectors, limit_per_source)
        logger.info(f"采集到 {len(sources)} 条新闻")

        # 2. 新闻去重
        unique_sources = []
        for source in sources:
            if not self.news_dedup.is_duplicate(
                source.title, source.content_snippet, source.source_name
            ):
                unique_sources.append(source)
        logger.info(f"新闻去重后: {len(unique_sources)} 条")

        # 3. 事件抽取
        logger.info("开始事件抽取...")
        events = self.extractor.extract_from_sources(unique_sources)
        logger.info(f"抽取到 {len(events)} 个事件")

        # 4. 事件归并
        merged = self.event_dedup.process_batch(events)
        logger.info(f"事件归并后: {len(merged)} 个事件")

        # 5. 保存
        if save:
            self._save_events(merged)
            logger.info(f"已保存到 {self.events_dir}")

        return merged

    def _collect(self, symbol: str = None,
                 collectors: list[str] = None,
                 limit: int = 20) -> list[NewsSource]:
        """采集新闻"""
        all_sources = []

        if collectors is None:
            collector_map = get_all_collectors()
        else:
            collector_map = {name: get_collector(name) for name in collectors}

        for name, collector in collector_map.items():
            try:
                sources = collector.collect(symbol=symbol, limit=limit)
                logger.info(f"  {name}: {len(sources)} 条")
                all_sources.extend(sources)
            except Exception as e:
                logger.warning(f"  {name}: 采集失败 - {e}")

        return all_sources

    def _save_events(self, events: list[Event]):
        """保存事件到知识库"""
        for event in events:
            date_str = event.timestamp.strftime("%Y-%m-%d")
            filepath = self.events_dir / f"{date_str}.jsonl"

            record = {
                "event_id": event.event_id,
                "event_type": event.event_type.value,
                "symbol": event.symbol,
                "company": event.company,
                "timestamp": event.timestamp.isoformat(),
                "detail": event.detail,
                "sentiment": event.sentiment.value,
                "confidence": event.confidence,
                "weighted_confidence": event.weighted_confidence,
                "impact_horizon": event.impact_horizon,
                "source_count": event.source_count,
                "max_tier": event.max_tier.value if event.max_tier else None,
                "sources": [
                    {
                        "source_name": s.source_name,
                        "tier": s.tier.value,
                        "title": s.title,
                        "url": s.url,
                    }
                    for s in event.sources
                ],
                "tags": event.tags,
                "dedup_key": event.dedup_key,
            }

            with open(filepath, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

    def get_stats(self) -> dict:
        """获取事件库统计"""
        total = 0
        by_type = {}
        by_symbol = {}

        for filepath in self.events_dir.glob("*.jsonl"):
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        event = json.loads(line)
                        total += 1

                        etype = event.get("event_type", "unknown")
                        by_type[etype] = by_type.get(etype, 0) + 1

                        symbol = event.get("symbol", "unknown")
                        by_symbol[symbol] = by_symbol.get(symbol, 0) + 1
                    except json.JSONDecodeError:
                        continue

        return {
            "total_events": total,
            "by_type": by_type,
            "by_symbol": by_symbol,
        }
