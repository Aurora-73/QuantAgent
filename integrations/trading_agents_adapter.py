"""
TradingAgents 适配器 — LLM 多Agent研究层

职责：
  - 将 TradingAgents 的输出转换为内部 LLMResearchDecision 类型
  - 只暴露研究分析方法，不暴露交易执行能力
  - 处理 TradingAgents 未安装时的降级

设计原则：
  - TradingAgents 只用于研究辅助，不进入交易决策主链路
  - 输出是结构化数据，不是自然语言
  - 业务代码不直接依赖 TradingAgents 的对象
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from data.schema import LLMResearchDecision

# 将 TradingAgents 源码加入 path
_TA_ROOT = Path(__file__).parent.parent.parent / "_reference" / "TradingAgents"
if str(_TA_ROOT) not in sys.path:
    sys.path.insert(0, str(_TA_ROOT))

try:
    from tradingagents.graph.trading_graph import TradingAgentsGraph
    from tradingagents.default_config import DEFAULT_CONFIG
    _HAS_TRADING_AGENTS = True
except ImportError:
    _HAS_TRADING_AGENTS = False


def is_available() -> bool:
    """TradingAgents 是否可用"""
    return _HAS_TRADING_AGENTS


# 信号到分数的映射
_SIGNAL_SCORE_MAP = {
    "Buy": 1.0,
    "Overweight": 0.5,
    "Hold": 0.0,
    "Underweight": -0.5,
    "Sell": -1.0,
}


class TradingAgentsAdapter:
    """
    TradingAgents 多Agent研究适配器

    所有方法返回内部类型 LLMResearchDecision。
    TradingAgents 的内部对象不暴露给业务代码。
    """

    def __init__(self, config: dict = None):
        if not _HAS_TRADING_AGENTS:
            raise ImportError("TradingAgents 未正确安装")
        self.config = config or DEFAULT_CONFIG.copy()
        self._graph = None

    def _get_graph(self) -> TradingAgentsGraph:
        if self._graph is None:
            self._graph = TradingAgentsGraph(debug=False, config=self.config)
        return self._graph

    def analyze(self, symbol: str, date: str,
                asset_type: str = "stock") -> LLMResearchDecision:
        """
        运行多Agent分析

        Args:
            symbol: 股票代码 (如 "NVDA", "600519.SS")
            date: 分析日期
            asset_type: 资产类型 ("stock", "crypto")

        Returns:
            LLMResearchDecision — 内部结构化类型
        """
        graph = self._get_graph()
        final_state, signal = graph.propagate(symbol, date, asset_type)

        # 提取关键信息
        messages = final_state.get("messages", [])
        reasoning_parts = []
        key_factors = []
        risk_flags = []

        for msg in messages:
            content = msg.content if hasattr(msg, "content") else str(msg)
            if content:
                reasoning_parts.append(content[:200])
                # 简单提取风险标志
                if "risk" in content.lower() or "风险" in content:
                    risk_flags.append(content[:100])

        return LLMResearchDecision(
            signal=signal,
            signal_score=_SIGNAL_SCORE_MAP.get(signal, 0.0),
            reasoning="\n".join(reasoning_parts[:3]),
            key_factors=key_factors,
            risk_flags=risk_flags[:5],
            confidence=0.7 if signal in ("Buy", "Sell") else 0.5,
            parse_success=True,
        )

    def analyze_batch(self, symbols: list[str], date: str) -> list[LLMResearchDecision]:
        """批量分析多只股票"""
        results = []
        for symbol in symbols:
            try:
                result = self.analyze(symbol, date)
                results.append(result)
            except Exception as e:
                results.append(LLMResearchDecision(
                    signal="Hold",
                    parse_success=False,
                    error=str(e),
                ))
        return results
