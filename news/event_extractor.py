"""
事件抽取器

将新闻文本转化为结构化 Event。

设计原则：
  - LLM 负责理解文本、分类事件
  - 输出是结构化数据，供传统量化模型消费
  - LLM 不直接做交易决策
  - 存事件，不存新闻全文
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Optional

from openai import OpenAI

from .schema import (
    Event, NewsSource, EventType, Sentiment, SourceTier,
)


logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一位专业的金融事件分析师。

你的职责是从新闻文本中抽取结构化的金融事件。

事件类型（必须从以下选择）：
- earnings_beat: 财报超预期
- earnings_miss: 财报不及预期
- earnings_in_line: 财报符合预期
- revenue_guidance: 营收指引
- profit_warning: 盈利预警
- buyback: 回购
- insider_buy: 内部人增持
- insider_sell: 内部人减持
- merger: 并购
- acquisition: 收购
- ceo_change: 高管变动
- dividend: 分红
- policy_ease: 政策宽松
- policy_tighten: 政策收紧
- regulation: 监管
- subsidy: 补贴
- rate_cut: 降息
- rate_hike: 加息
- cpi_data: CPI数据
- gdp_data: GDP数据
- employment: 就业数据
- tech_breakthrough: 技术突破
- supply_change: 供需变化
- price_change: 价格变动
- index_rebalance: 指数调仓
- short_sell: 做空报告
- analyst_upgrade: 评级上调
- analyst_downgrade: 评级下调
- other: 其他

输出要求：
- 每条新闻一个事件
- symbol: 股票代码（如 NVDA, 600519.SS）
- company: 公司名称
- event_type: 必须从上面的列表选择
- sentiment: positive / negative / neutral
- confidence: 0.0-1.0
- detail: 50字以内的事件摘要
- impact_horizon: short(1-3天) / medium(1-2周) / long(1月+)
- tags: 相关标签"""


class EventExtractor:
    """
    事件抽取器

    输入: NewsSource 列表
    输出: Event 列表（结构化）

    核心逻辑：
      1. LLM 理解新闻文本
      2. 输出结构化事件
      3. 为每个事件生成去重键
      4. 不存储新闻全文
    """

    def __init__(self, api_key: str = None, model: str = "gpt-4o"):
        self.llm = OpenAI(api_key=api_key)
        self.model = model

    def extract_from_sources(self, sources: list[NewsSource]) -> list[Event]:
        """
        从新闻源列表中抽取事件

        Args:
            sources: NewsSource 列表

        Returns:
            Event 列表
        """
        if not sources:
            return []

        # 按来源分组（避免一次发太多）
        events = []
        for source in sources:
            extracted = self._extract_single(source)
            events.extend(extracted)

        return events

    def _extract_single(self, source: NewsSource) -> list[Event]:
        """从单条新闻中抽取事件"""
        text = f"标题: {source.title}"
        if source.content_snippet:
            text += f"\n摘要: {source.content_snippet}"

        prompt = f"""请从以下新闻中抽取金融事件。

来源: {source.source_name} (Tier {source.tier.value})
时间: {source.published_at.isoformat()}

{text}

请严格输出 JSON 数组，不要包含其他文字：
[
  {{
    "symbol": "股票代码",
    "company": "公司名称",
    "event_type": "事件类型",
    "sentiment": "positive/negative/neutral",
    "confidence": 0.0-1.0,
    "detail": "50字以内摘要",
    "impact_horizon": "short/medium/long",
    "tags": ["标签1"]
  }}
]

如果新闻不包含可抽取的金融事件，请输出空数组 []。"""

        try:
            response = self.llm.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=2048,
            )
            result_text = response.choices[0].message.content
            data = self._parse_json(result_text)

            events = []
            for item in data:
                if not isinstance(item, dict):
                    continue

                event_type_str = item.get("event_type", "other")
                try:
                    event_type = EventType(event_type_str)
                except ValueError:
                    event_type = EventType.OTHER

                sentiment_str = item.get("sentiment", "neutral")
                sentiment = {
                    "positive": Sentiment.POSITIVE,
                    "negative": Sentiment.NEGATIVE,
                }.get(sentiment_str, Sentiment.NEUTRAL)

                event = Event(
                    event_id=f"evt_{uuid.uuid4().hex[:8]}",
                    event_type=event_type.value,
                    symbol=item.get("symbol", ""),
                    company=item.get("company", ""),
                    timestamp=source.published_at,
                    detail=item.get("detail", "")[:50],
                    sentiment=sentiment,
                    confidence=float(item.get("confidence", 0.5)),
                    impact_horizon=item.get("impact_horizon", "short"),
                    sources=[source],
                    tags=item.get("tags", []),
                )
                events.append(event)

            return events

        except Exception as e:
            logger.warning(f"事件抽取失败: {source.title[:30]} - {e}")
            return []

    @staticmethod
    def _parse_json(text: str) -> list:
        """解析 JSON"""
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            return []
