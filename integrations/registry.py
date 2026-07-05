"""
集成适配器注册表 — 工厂方法 + 全局注册

用法:
    from integrations.registry import get_provider, get_engine, list_adapters

    # 获取数据提供者
    provider = get_provider("openbb")
    df = provider.get_historical("AAPL")

    # 获取执行引擎
    engine = get_engine("vnpy")

    # 列出所有已注册适配器
    for name, info in list_adapters().items():
        print(f"{name}: {info['description']}")
"""
from typing import Optional


class AdapterInfo:
    """适配器元信息"""

    def __init__(self, name: str, adapter_cls: type,
                 category: str, description: str,
                 available: bool = True):
        self.name = name
        self.adapter_cls = adapter_cls
        self.category = category  # "data" | "research" | "execution" | "agent"
        self.description = description
        self.available = available


_registry: dict[str, AdapterInfo] = {}


def register(name: str, adapter_cls: type, category: str,
             description: str = "", available: bool = True):
    """注册一个适配器"""
    _registry[name] = AdapterInfo(
        name=name,
        adapter_cls=adapter_cls,
        category=category,
        description=description,
        available=available,
    )


def get_provider(name: str = "akshare", **kwargs) -> Optional[object]:
    """获取数据提供者实例"""
    info = _registry.get(name)
    if info is None or info.category != "data":
        return None
    return info.adapter_cls(**kwargs)


def get_engine(name: str, **kwargs) -> Optional[object]:
    """
    获取执行或研究引擎实例

    按名称查找，自动匹配 execution / research / agent 类别。
    """
    info = _registry.get(name)
    if info is None:
        return None
    return info.adapter_cls(**kwargs)


def list_adapters(category: str = None) -> dict:
    """列出已注册的适配器"""
    if category:
        return {
            k: v for k, v in _registry.items()
            if v.category == category
        }
    return dict(_registry)


# ============================================================
# 内置默认注册：采用懒加载，避免导入时触发 HAS_* 检查
# ============================================================

def _register_defaults():
    """注册内置适配器"""

    # openbb
    try:
        from integrations.openbb_data import HAS_OPENBB, OpenBBDataAdapter
        if HAS_OPENBB:
            register("openbb", OpenBBDataAdapter, "data",
                     "OpenBB Platform — 50+ 数据源统一入口")
    except Exception:
        pass

    # akshare
    try:
        from data.provider import DataProvider as AkShareDataProvider
        register("akshare", AkShareDataProvider, "data",
                 "AKShare — A股免费数据源")
    except Exception:
        pass

    # qlib
    try:
        from integrations.qlib_engine import HAS_QLIB, QlibResearchAdapter
        if HAS_QLIB:
            register("qlib", QlibResearchAdapter, "research",
                     "Qlib — AI 量化研究框架")
    except Exception:
        pass

    # vnpy
    try:
        from integrations.vnpy_engine import HAS_VNPY, VnpyExecutionAdapter
        if HAS_VNPY:
            register("vnpy", VnpyExecutionAdapter, "execution",
                     "vnpy — 量化交易执行引擎")
    except Exception:
        pass

    # trading_agents
    try:
        from integrations.trading_agents import HAS_TRADING_AGENTS, TradingAgentsAdapter
        if HAS_TRADING_AGENTS:
            register("trading_agents", TradingAgentsAdapter, "agent",
                     "TradingAgents — 多 Agent 分析框架")
    except Exception:
        pass


# 模块导入时自动注册默认适配器
_register_defaults()
