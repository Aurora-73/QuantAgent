"""
新闻与事件数据结构

设计原则：
  - 只存事件，不存新闻全文
  - 每个事件可追溯多个信源
  - 信源按可信度分级
  - 支持事件归并（同一事件多个报道合并）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from data.schema import Event as BaseEvent, Sentiment


class SourceTier(Enum):
    """信源分级"""
    TIER_1 = 1  # 一级信源：SEC EDGAR、巨潮资讯、公司IR
    TIER_2 = 2  # 二级信源：Reuters、Bloomberg、FT
    TIER_3 = 3  # 三级信源：OpenBB、Yahoo Finance、Benzinga
    TIER_4 = 4  # 四级信源：Reddit、Twitter/X、Hacker News


# 信源可信度权重（Tier 1 最高）
TIER_WEIGHT = {
    SourceTier.TIER_1: 1.0,
    SourceTier.TIER_2: 0.8,
    SourceTier.TIER_3: 0.6,
    SourceTier.TIER_4: 0.4,
}


class EventType(Enum):
    """事件类型"""
    # 财务类
    EARNINGS_BEAT = "earnings_beat"        # 财报超预期
    EARNINGS_MISS = "earnings_miss"        # 财报不及预期
    EARNINGS_IN_LINE = "earnings_in_line"  # 财报符合预期
    REVENUE_GUIDANCE = "revenue_guidance"  # 营收指引
    PROFIT_WARNING = "profit_warning"      # 盈利预警

    # 公司类
    BUYBACK = "buyback"                    # 回购
    INSIDER_BUY = "insider_buy"            # 内部人增持
    INSIDER_SELL = "insider_sell"          # 内部人减持
    MERGER = "merger"                      # 并购
    ACQUISITION = "acquisition"            # 收购
    CEO_CHANGE = "ceo_change"             # 高管变动
    DIVIDEND = "dividend"                  # 分红

    # 政策类
    POLICY_EASE = "policy_ease"            # 政策宽松
    POLICY_TIGHTEN = "policy_tighten"      # 政策收紧
    REGULATION = "regulation"              # 监管
    SUBSIDY = "subsidy"                    # 补贴

    # 宏观类
    RATE_CUT = "rate_cut"                  # 降息
    RATE_HIKE = "rate_hike"                # 加息
    CPI_DATA = "cpi_data"                  # CPI数据
    GDP_DATA = "gdp_data"                  # GDP数据
    EMPLOYMENT = "employment"              # 就业数据

    # 行业类
    TECH_BREAKTHROUGH = "tech_breakthrough"  # 技术突破
    SUPPLY_CHANGE = "supply_change"          # 供需变化
    PRICE_CHANGE = "price_change"            # 价格变动

    # 市场类
    INDEX_REBALANCE = "index_rebalance"    # 指数调仓
    SHORT_SELL = "short_sell"              # 做空报告
    ANALYST_UPGRADE = "analyst_upgrade"    # 评级上调
    ANALYST_DOWNGRADE = "analyst_downgrade"  # 评级下调

    # 其他
    OTHER = "other"


@dataclass
class NewsSource:
    """单条新闻来源"""
    url: str
    source_name: str           # Reuters / Bloomberg / Yahoo / ...
    tier: SourceTier
    title: str
    published_at: datetime
    content_snippet: str = ""  # 摘要（不是全文）
    raw_id: str = ""           # 原始 ID（用于去重）


@dataclass
class Event(BaseEvent):
    """
    结构化新闻事件 — 继承 data.schema.Event

    核心设计：一个事件可以有多个信源。
    例如同一条 NVIDIA 财报，Reuters、Bloomberg、Yahoo 都报道了，
    但只存为一个 Event，sources 列表包含所有报道。
    """
    sources: list[NewsSource] = field(default_factory=list)  # 所有信源
    dedup_key: str = ""            # 去重键（用于事件归并）

    @property
    def source_count(self) -> int:
        """信源数量"""
        return len(self.sources)

    @property
    def max_tier(self) -> Optional[SourceTier]:
        """最高可信度信源"""
        if not self.sources:
            return None
        return min((s.tier for s in self.sources), key=lambda t: t.value)

    @property
    def weighted_confidence(self) -> float:
        """加权置信度（考虑信源可信度）"""
        if not self.sources:
            return self.confidence
        total_weight = sum(TIER_WEIGHT[s.tier] for s in self.sources)
        weighted = sum(
            self.confidence * TIER_WEIGHT[s.tier] for s in self.sources
        )
        return weighted / total_weight if total_weight > 0 else self.confidence

    def add_source(self, source: NewsSource):
        """添加信源（自动更新置信度）"""
        # 检查是否重复
        existing_ids = {s.raw_id for s in self.sources if s.raw_id}
        if source.raw_id and source.raw_id in existing_ids:
            return

        self.sources.append(source)

        # 多信源确认提高置信度
        if self.source_count > 1:
            boost = min(0.1 * (self.source_count - 1), 0.3)
            self.confidence = min(self.confidence + boost, 1.0)
