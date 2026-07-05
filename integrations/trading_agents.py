"""
TradingAgents 集成 — LLM 多Agent研究层

直接使用 TradingAgents 的：
  - 多Agent协作架构 (分析师→研究员→交易员→风控)
  - LangGraph 工作流编排
  - 多LLM支持 (OpenAI, Anthropic, Google, DeepSeek 等)
  - 结构化输出 (ResearchPlan, TraderProposal, PortfolioDecision)

不重复实现 TradingAgents 已有的功能。

适配器:
  TradingAgentsAdapter — 实现 AgentEngine 接口
  TradingAgentsEngine — 旧接口，保留向后兼容
"""
import warnings
import sys
from pathlib import Path
from typing import Optional

import pandas as pd

from loguru import logger

from integrations.base import AgentEngine

# 将 TradingAgents 源码加入 path
TA_ROOT = Path(__file__).parent.parent.parent / "_reference" / "TradingAgents"
if str(TA_ROOT) not in sys.path:
    sys.path.insert(0, str(TA_ROOT))

try:
    from tradingagents.graph.trading_graph import TradingAgentsGraph
    from tradingagents.default_config import DEFAULT_CONFIG
    HAS_TRADING_AGENTS = True
except ImportError as e:
    HAS_TRADING_AGENTS = False
    logger.warning(f"TradingAgents 导入失败: {e}")


class TradingAgentsAdapter(AgentEngine):
    """
    TradingAgents 适配器 — 实现统一的 AgentEngine 接口

    用法:
        adapter = TradingAgentsAdapter()
        result = adapter.analyze("600519", "2026-07-02")
    """

    def __init__(self, config: dict = None):
        self.available = HAS_TRADING_AGENTS
        self.config = config
        self._engine = TradingAgentsEngine(config) if HAS_TRADING_AGENTS else None

    def analyze(self, ticker: str, date: str, **kwargs) -> dict:
        if not self.available or self._engine is None:
            return {"signal": "Hold", "error": "TradingAgents 不可用"}
        return self._engine.analyze(ticker, date, **kwargs)

    def analyze_batch(self, tickers: list[str], date: str) -> list[dict]:
        if not self.available or self._engine is None:
            return [{"signal": "Hold", "error": "TradingAgents 不可用"} for _ in tickers]
        return self._engine.analyze_batch(tickers, date)


class TradingAgentsEngine:
    """
    TradingAgents 多Agent研究引擎

    提供：
    1. 多Agent分析 (技术面、基本面、情绪面、新闻)
    2. 多空辩论 (Bull vs Bear)
    3. 交易提案 (Trader Proposal)
    4. 风控辩论 (Aggressive vs Conservative vs Neutral)
    5. 最终决策 (Portfolio Decision)

    已弃用: 请使用 TradingAgentsAdapter 替代。

    用法：
        engine = TradingAgentsEngine()
        if engine.available:
            decision = engine.analyze("NVDA", "2026-06-03")
            print(decision)
        else:
            print("TradingAgents 未安装，降级运行")
    """

    def __init__(self, config: dict = None):
        warnings.warn(
            "TradingAgentsEngine 已弃用，请使用 TradingAgentsAdapter（实现统一的 AgentEngine 接口）",
            DeprecationWarning, stacklevel=2,
        )
        self.available = HAS_TRADING_AGENTS
        if not self.available:
            logger.warning("TradingAgents 未安装，TradingAgentsEngine 以降级模式运行")
            self.config = {}
            self._graph = None
            return
        self.config = config or DEFAULT_CONFIG.copy()
        self._graph = None

    def _get_graph(self) -> Optional["TradingAgentsGraph"]:
        """懒加载 TradingAgentsGraph"""
        if not self.available:
            return None
        if self._graph is None:
            self._graph = TradingAgentsGraph(
                debug=False,
                config=self.config,
            )
        return self._graph

    def analyze(self, ticker: str, date: str,
                asset_type: str = "stock") -> dict:
        """运行多Agent分析，不可用时返回降级结果。"""
        if not self.available:
            return {"signal": "Hold", "error": "TradingAgents 未安装"}

        graph = self._get_graph()
        if graph is None:
            return {"signal": "Hold", "error": "TradingAgents 不可用"}

        final_state, signal = graph.propagate(ticker, date, asset_type)

        result = {
            "signal": signal,
            "final_state": final_state,
        }

        messages = final_state.get("messages", [])
        for msg in messages:
            content = msg.content if hasattr(msg, "content") else str(msg)
            if "ResearchPlan" in content or "research_plan" in content:
                result["research_plan"] = content
            elif "TraderProposal" in content or "trader_proposal" in content:
                result["trader_proposal"] = content
            elif "PortfolioDecision" in content or "portfolio_decision" in content:
                result["portfolio_decision"] = content

        return result

    def analyze_batch(self, tickers: list[str], date: str) -> list[dict]:
        """批量分析多只股票"""
        if not self.available:
            return [{"signal": "Hold", "error": "TradingAgents 未安装"} for _ in tickers]

        results = []
        for ticker in tickers:
            try:
                result = self.analyze(ticker, date)
                results.append(result)
                logger.success(f"  {ticker}: {result['signal']}")
            except Exception as e:
                logger.error(f"  {ticker}: {e}")
                results.append({"signal": "Error", "error": str(e)})
        return results

    def get_signal_score(self, signal: str) -> float:
        """
        将信号转换为数值分数

        Buy = 1.0, Overweight = 0.5, Hold = 0.0, Underweight = -0.5, Sell = -1.0
        """
        score_map = {
            "Buy": 1.0,
            "Overweight": 0.5,
            "Hold": 0.0,
            "Underweight": -0.5,
            "Sell": -1.0,
        }
        return score_map.get(signal, 0.0)
