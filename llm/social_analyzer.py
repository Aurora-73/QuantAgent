"""
Social Analyzer — LLM-based sentiment analysis on group chat messages.

Pipeline:
    raw messages → dedup + cleaning → LLM analysis → structured sentiment
    → MarketFact(fact_type="social_sentiment")

Usage:
    analyzer = SocialAnalyzer()
    result = analyzer.analyze(messages)
    # {sentiment: bullish/bearish/neutral, confidence: 0.75, tickers: [...]}
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from loguru import logger

from configs.settings import settings

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


class SocialAnalyzer:
    """
    社交情绪分析器

    使用 LLM 对群聊消息进行情绪分类和热点提取。
    """

    def __init__(self, model: str = None, api_key: str = None):
        self.model = model or settings.llm_model or "gpt-4o-mini"
        api_key = api_key or settings.openai_api_key or ""
        self._client = None
        if HAS_OPENAI and api_key:
            self._client = OpenAI(api_key=api_key)

    def analyze(self, messages: list[dict]) -> dict:
        """
        分析一组消息，输出情绪和热点。

        Args:
            messages: [{group_id, user_id, message, time}, ...]

        Returns:
            {
                sentiment: "bullish" | "bearish" | "neutral",
                confidence: 0.0-1.0,
                bull_ratio: 0.0-1.0,
                bear_ratio: 0.0-1.0,
                neutral_ratio: 0.0-1.0,
                tickers: ["600519", ...],    # 提及的标的
                hot_topics: ["白酒", "AI"],   # 热门话题
                summary: "整体情绪偏乐观...",  # 一句话总结
                message_count: int,
                active_users: int,
            }
        """
        if not messages:
            return {
                "sentiment": "neutral",
                "confidence": 0.0,
                "bull_ratio": 0.0,
                "bear_ratio": 0.0,
                "neutral_ratio": 1.0,
                "tickers": [],
                "hot_topics": [],
                "summary": "无消息",
                "message_count": 0,
                "active_users": 0,
            }

        # 去重 + 统计
        unique_messages = list({m["message"] for m in messages if m.get("message")})
        active_users = len({m["user_id"] for m in messages})

        if self._client and len(unique_messages) > 0:
            return self._llm_analysis(unique_messages, active_users)

        return self._rule_analysis(unique_messages, active_users)

    def _llm_analysis(self, messages: list[str], active_users: int) -> dict:
        """LLM 分析"""
        try:
            text = "\n".join(f"- {m}" for m in messages[:50])
            prompt = f"""分析以下股票群聊消息的情绪和热点：

{text}

请输出 JSON:
{{
    "sentiment": "bullish/bearish/neutral",
    "confidence": 0.0-1.0,
    "bull_ratio": 0.0-1.0 (看多比例),
    "bear_ratio": 0.0-1.0 (看空比例),
    "tickers": ["可能的股票代码或名称"],
    "hot_topics": ["热门话题"],
    "summary": "一句话总结"
}}"""

            resp = self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            import json
            result = json.loads(resp.choices[0].message.content)
            result["message_count"] = len(messages)
            result["active_users"] = active_users
            return result

        except Exception as e:
            logger.warning(f"  LLM 分析失败: {e}, 回退到规则分析")
            return self._rule_analysis(messages, active_users)

    def _rule_analysis(self, messages: list[str], active_users: int) -> dict:
        """规则回退分析"""
        bullish_words = ["涨", "多", "牛", "突破", "利好", "新高", "加仓", "买入", "机会", "反弹"]
        bearish_words = ["跌", "空", "熊", "破位", "利空", "新低", "减仓", "卖出", "风险", "跑"]

        bull_count = 0
        bear_count = 0
        for m in messages:
            m_lower = m.lower()
            for w in bullish_words:
                if w in m_lower:
                    bull_count += 1
                    break
            for w in bearish_words:
                if w in m_lower:
                    bear_count += 1
                    break

        total = bull_count + bear_count
        if total == 0:
            return {
                "sentiment": "neutral",
                "confidence": 0.5,
                "bull_ratio": 0.0,
                "bear_ratio": 0.0,
                "neutral_ratio": 1.0,
                "tickers": [],
                "hot_topics": [],
                "summary": "消息无明显多空倾向",
                "message_count": len(messages),
                "active_users": active_users,
            }

        bull_ratio = bull_count / total
        bear_ratio = bear_count / total
        if bull_ratio > 0.6:
            sentiment = "bullish"
        elif bear_ratio > 0.6:
            sentiment = "bearish"
        else:
            sentiment = "neutral"

        return {
            "sentiment": sentiment,
            "confidence": abs(bull_ratio - bear_ratio),
            "bull_ratio": round(bull_ratio, 4),
            "bear_ratio": round(bear_ratio, 4),
            "neutral_ratio": round(1.0 - bull_ratio - bear_ratio, 4),
            "tickers": [],
            "hot_topics": [],
            "summary": f"看多 {bull_count}/{total}, 看空 {bear_count}/{total}",
            "message_count": len(messages),
            "active_users": active_users,
        }

    def to_market_fact(self, analysis: dict, source: str = "QQ群聊") -> "MarketFact":
        """将分析结果转换为 MarketFact 对象"""
        from data.market_fact import MarketFact
        fact = MarketFact(
            fact_id=f"social_{date.today().isoformat()}",
            timestamp=datetime.now(),
            fact_type="social_sentiment",
            ticker="",
            description=analysis.get("summary", ""),
            value=analysis.get("confidence", 0.0),
            confidence=analysis.get("confidence", 0.0),
            source=source,
            tags=["social", "sentiment", analysis.get("sentiment", "neutral")],
        )
        return fact
