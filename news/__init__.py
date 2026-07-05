"""
新闻与事件模块

设计原则：
  - 存事件，不存新闻全文
  - 同一事件多个报道合并（事件归并）
  - 多信源确认提高置信度
  - 可靠性 > 时效性 > 结构化程度 > 数量

信源分级：
  Tier 1: SEC EDGAR、巨潮资讯、公司IR
  Tier 2: Reuters、Bloomberg、FT
  Tier 3: OpenBB、Yahoo Finance、Benzinga
  Tier 4: Reddit、Twitter/X、Hacker News
"""
from .schema import (
    Event, NewsSource, EventType, Sentiment, SourceTier,
    TIER_WEIGHT,
)
from .deduplicator import EventDeduplicator, NewsDeduplicator
from .collector import (
    NewsCollector, OpenBBCollector, YFinanceCollector,
    AKShareCollector, CNInfoCollector, SECEdgarCollector,
    get_collector, get_all_collectors, COLLECTORS,
)
from .event_extractor import EventExtractor
from .pipeline import NewsPipeline
