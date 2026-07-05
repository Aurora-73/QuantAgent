"""
文档摘要器 — LLM 在研究层的正确用法

职责：
  - 研报摘要
  - 财报要点提取
  - 政策文件解读
  - 电话会议纪要

不做：
  - 直接推荐买卖
  - 预测价格
  - 生成仓位

设计原则：
  - 所有输出都是 LLMSummary 结构化类型
  - LLM 输出解析失败时返回 parse_success=False
  - 不返回裸 dict，返回有类型的 dataclass
"""
from __future__ import annotations

import json
from typing import Optional

from openai import OpenAI

from configs.settings import settings
from data.schema import LLMSummary, Sentiment


class DocumentSummarizer:
    """金融文档摘要器 — 输出结构化 LLMSummary"""

    SYSTEM_PROMPT = """你是一位专业的金融研究助理。

你的职责是帮助研究员快速理解文档内容，提取关键信息。

你的原则：
1. 只提取事实，不做价格预测
2. 区分确定性信息和推测
3. 标注数据来源和可信度
4. 输出结构化 JSON 格式

你不做：
1. 不推荐买卖
2. 不预测涨跌
3. 不给出仓位建议"""

    def __init__(self, api_key: str = None, model: str = None):
        self.llm = OpenAI(
            api_key=api_key or settings.openai_api_key,
            base_url=settings.openai_base_url,
        )
        self.model = model or settings.llm_model

    def summarize_report(self, text: str, report_type: str = "research") -> LLMSummary:
        """
        摘要研报

        Args:
            text: 研报全文
            report_type: 类型 (research / earnings / policy / conference)

        Returns:
            LLMSummary 结构化类型
        """
        prompt = f"""请对以下{self._type_name(report_type)}进行结构化摘要。

文档内容：
{text[:8000]}

请严格输出以下 JSON 格式，不要包含其他文字：
{{
  "title": "文档标题",
  "summary": "200字以内的核心摘要",
  "key_points": ["要点1", "要点2", "要点3"],
  "sentiment": "positive/negative/neutral",
  "confidence": 0.0-1.0,
  "risk_flags": ["风险因素1", "风险因素2"],
  "industry_impact": ["影响的行业/板块"]
}}"""
        return self._call_llm(prompt)

    def extract_earnings_highlights(self, text: str) -> LLMSummary:
        """
        提取财报要点

        Returns:
            LLMSummary 结构化类型
        """
        prompt = f"""请从以下财报中提取关键财务指标和经营亮点。

财报内容：
{text[:8000]}

请严格输出以下 JSON 格式，不要包含其他文字：
{{
  "title": "公司名称 + 报告期",
  "summary": "200字以内的核心摘要",
  "key_points": ["营收增长X%", "净利润增长X%", "亮点1"],
  "sentiment": "positive/negative/neutral",
  "confidence": 0.0-1.0,
  "risk_flags": ["风险点1", "风险点2"],
  "industry_impact": []
}}"""
        return self._call_llm(prompt)

    def interpret_policy(self, text: str) -> LLMSummary:
        """
        解读政策文件

        Returns:
            LLMSummary 结构化类型
        """
        prompt = f"""请解读以下政策文件，分析其对资本市场的影响。

政策内容：
{text[:8000]}

请严格输出以下 JSON 格式，不要包含其他文字：
{{
  "title": "政策名称",
  "summary": "200字以内的核心摘要",
  "key_points": ["核心内容1", "核心内容2"],
  "sentiment": "positive/negative/neutral",
  "confidence": 0.0-1.0,
  "risk_flags": ["风险因素1"],
  "industry_impact": ["受益板块1", "受损板块1"]
}}"""
        return self._call_llm(prompt)

    def _type_name(self, report_type: str) -> str:
        names = {
            "research": "研究报告",
            "earnings": "财务报告",
            "policy": "政策文件",
            "conference": "电话会议纪要",
        }
        return names.get(report_type, "金融文档")

    def _call_llm(self, prompt: str) -> LLMSummary:
        try:
            response = self.llm.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens,
            )
            result_text = response.choices[0].message.content

            # 解析 JSON
            json_str = self._extract_json(result_text)
            data = json.loads(json_str)

            # 转换 sentiment
            sentiment_map = {
                "positive": Sentiment.POSITIVE,
                "negative": Sentiment.NEGATIVE,
                "neutral": Sentiment.NEUTRAL,
            }

            return LLMSummary(
                title=data.get("title", ""),
                summary=data.get("summary", ""),
                key_points=data.get("key_points", []),
                sentiment=sentiment_map.get(data.get("sentiment", "neutral"), Sentiment.NEUTRAL),
                confidence=float(data.get("confidence", 0.5)),
                risk_flags=data.get("risk_flags", []),
                industry_impact=data.get("industry_impact", []),
                parse_success=True,
            )
        except Exception as e:
            return LLMSummary(
                parse_success=False,
                error=str(e),
            )

    @staticmethod
    def _extract_json(text: str) -> str:
        if "```json" in text:
            return text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            return text.split("```")[1].split("```")[0].strip()
        return text.strip()
