"""
集成适配器 — 统一接口定义

所有外部引擎（数据、研究、执行、Agent）均通过此处的抽象接口访问。
集成模块内部实现具体适配器，外部代码只依赖这些接口。

用法:
    from integrations.base import DataProvider, ResearchEngine, ExecutionEngine, AgentEngine
    from integrations.registry import get_provider

    provider = get_provider("openbb")
    df = provider.get_historical("AAPL", "2024-01-01", "2024-12-31")
"""
from abc import ABC, abstractmethod
from typing import Optional

import pandas as pd


class DataProvider(ABC):
    """统一数据提供者接口 — 行情、基本面、新闻"""

    @abstractmethod
    def get_historical(self, symbol: str,
                       start_date: Optional[str] = None,
                       end_date: Optional[str] = None,
                       interval: str = "1d") -> pd.DataFrame:
        """获取历史行情"""
        ...

    @abstractmethod
    def get_quote(self, symbol: str) -> dict:
        """获取最新报价"""
        ...

    def get_company_news(self, symbol: str, limit: int = 20) -> pd.DataFrame:
        """获取公司新闻（可选实现）"""
        raise NotImplementedError

    def search(self, query: str) -> pd.DataFrame:
        """搜索股票（可选实现）"""
        raise NotImplementedError


class ResearchEngine(ABC):
    """统一研究引擎接口 — 因子、模型、回测"""

    @abstractmethod
    def get_features(self, instruments, fields=None,
                     start_time: str = None, end_time: str = None) -> pd.DataFrame:
        """获取特征数据"""
        ...

    @abstractmethod
    def backtest(self, model, dataset, **kwargs) -> dict:
        """运行回测"""
        ...


class ExecutionEngine(ABC):
    """统一执行引擎接口 — 订单、持仓、账户"""

    @abstractmethod
    def send_order(self, symbol: str, direction: str,
                   price: float, volume: float,
                   order_type: str = "LIMIT") -> str:
        """发送订单"""
        ...

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """撤单"""
        ...

    @abstractmethod
    def get_positions(self) -> list[dict]:
        """获取持仓"""
        ...

    def get_accounts(self) -> list[dict]:
        """获取账户信息（可选实现）"""
        raise NotImplementedError


class AgentEngine(ABC):
    """统一 Agent 引擎接口 — 多 Agent 分析"""

    @abstractmethod
    def analyze(self, ticker: str, date: str, **kwargs) -> dict:
        """运行多 Agent 分析"""
        ...

    def analyze_batch(self, tickers: list[str], date: str) -> list[dict]:
        """批量分析（默认逐个调用）"""
        return [self.analyze(t, date) for t in tickers]
