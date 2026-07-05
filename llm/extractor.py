"""
事件结构化抽取器

将非结构化文本 (新闻、公告、研报) 转化为结构化事件数据，
供下游因子计算和信号生成使用。

输出格式统一为 LLMEventExtraction，包含 Event 列表。
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Optional

from openai import OpenAI

from configs.settings import settings
from data.schema import Event, LLMEventExtraction, Sentiment


class EventExtractor:
    """
    事件结构化抽取器

    输入: 非结构化文本 (新闻/公告/研报)
    输出: LLMEventExtraction — 包含 Event 列表的结构化类型

    这是 LLM 在量化系统中最正确的用法之一：
    - LLM 负责理解文本、分类事件
    - 输出是结构化数据，供传统量化模型消费
    - LLM 不直接做交易决策
    """

    SYSTEM_PROMPT = """你是一位专业的金融事件分析师。

你的职责是从文本中抽取结构化的金融事件。

事件类型包括：
- 业绩类：业绩预增/预减/超预期/不及预期
- 政策类：政策利好/利空/行业扶持/监管收紧
- 公司类：增减持/回购/并购/重组/高管变动
- 行业类：技术突破/供需变化/价格变动
- 宏观类：利率变动/汇率波动/经济数据
- 市场类：资金流向/大宗交易/融资融券

输出要求：
- 每个事件一条记录
- sentiment: positive/negative/neutral
- confidence: 0.0-1.0
- tags: 相关标签"""

    def __init__(self, api_key: str = None, model: str = None):
        self.llm = OpenAI(
            api_key=api_key or settings.openai_api_key,
            base_url=settings.openai_base_url,
        )
        self.model = model or settings.llm_model

    def extract_from_news(self, news_items: list[str],
                          date_str: str = None) -> LLMEventExtraction:
        """
        从新闻列表中抽取事件

        Returns:
            LLMEventExtraction 结构化类型
        """
        if not news_items:
            return LLMEventExtraction(events=[], parse_success=True)

        news_text = "\n".join([f"[{i+1}] {n}" for i, n in enumerate(news_items)])

        prompt = f"""请从以下新闻中抽取结构化金融事件。

日期: {date_str or '未知'}

新闻列表：
{news_text}

请严格输出 JSON 数组，不要包含其他文字：
[
  {{
    "event_type": "事件类型",
    "symbol": "股票代码(如有，格式如 600519.SS)",
    "detail": "事件详情摘要(50字以内)",
    "sentiment": "positive/negative/neutral",
    "confidence": 0.0-1.0,
    "tags": ["标签1", "标签2"]
  }}
]

如果新闻不包含可抽取的金融事件，请输出空数组 []。"""

        return self._call_llm(prompt, source="news", date_str=date_str)

    def extract_from_announcement(self, text: str, symbol: str = "",
                                  date_str: str = None) -> LLMEventExtraction:
        """
        从公告中抽取事件

        Returns:
            LLMEventExtraction 结构化类型
        """
        prompt = f"""请从以下公告中抽取结构化金融事件。

股票代码: {symbol or '未知'}
日期: {date_str or '未知'}

公告内容：
{text[:6000]}

请严格输出 JSON 数组，不要包含其他文字。格式同上。"""

        return self._call_llm(prompt, source="announcement", date_str=date_str)

    def extract_from_research(self, text: str,
                              date_str: str = None) -> LLMEventExtraction:
        """
        从研报中抽取事件

        Returns:
            LLMEventExtraction 结构化类型
        """
        prompt = f"""请从以下研报中抽取关键事件和观点。

日期: {date_str or '未知'}

研报内容：
{text[:6000]}

请严格输出 JSON 数组，不要包含其他文字。格式同上。"""

        return self._call_llm(prompt, source="report", date_str=date_str)

    def _call_llm(self, prompt: str, source: str = "",
                  date_str: str = None) -> LLMEventExtraction:
        try:
            response = self.llm.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=settings.llm_extraction_temperature,
                max_tokens=settings.llm_extraction_max_tokens,
            )
            result_text = response.choices[0].message.content

            json_str = self._extract_json(result_text)
            data = json.loads(json_str)

            if not isinstance(data, list):
                return LLMEventExtraction(events=[], parse_success=False,
                                          error="LLM 返回非数组格式")

            sentiment_map = {
                "positive": Sentiment.POSITIVE,
                "negative": Sentiment.NEGATIVE,
                "neutral": Sentiment.NEUTRAL,
            }

            events = []
            for item in data:
                if not isinstance(item, dict):
                    continue
                events.append(Event(
                    event_id=f"evt_{uuid.uuid4().hex[:8]}",
                    event_type=item.get("event_type", "unknown"),
                    symbol=item.get("symbol", item.get("ticker", "")),
                    timestamp=datetime.fromisoformat(date_str) if date_str else datetime.now(),
                    detail=item.get("detail", ""),
                    sentiment=sentiment_map.get(item.get("sentiment", "neutral"), Sentiment.NEUTRAL),
                    confidence=float(item.get("confidence", 0.5)),
                    source=source,
                    tags=item.get("tags", []),
                ))

            return LLMEventExtraction(events=events, parse_success=True)

        except Exception as e:
            return LLMEventExtraction(events=[], parse_success=False, error=str(e))

    @staticmethod
    def _extract_json(text: str) -> str:
        if "```json" in text:
            return text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            return text.split("```")[1].split("```")[0].strip()
        return text.strip()
