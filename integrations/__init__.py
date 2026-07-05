"""
集成层 — 适配器模式

职责：
  - 将第三方开源项目封装为系统内部接口
  - 所有输入输出使用 data/schema.py 中定义的类型
  - 第三方依赖在适配器边界处隔离
  - 未安装时提供优雅降级

设计原则：
  - 业务代码只依赖 integrations/*.adapter，不直接 import 第三方
  - 每个适配器暴露 is_available() 检查可用性
  - 适配器返回内部类型，不返回第三方对象

统一接口:
  DataProvider     — 数据提供者 (行情、基本面、新闻)
  ResearchEngine   — 研究引擎 (因子、模型、回测)
  ExecutionEngine  — 执行引擎 (订单、持仓、账户)
  AgentEngine      — 多 Agent 分析引擎

快速获取:
  from integrations.registry import get_provider, get_engine
  provider = get_provider("akshare")
  engine = get_engine("qlib")
"""
from integrations.base import DataProvider, ResearchEngine, ExecutionEngine, AgentEngine
from integrations.registry import get_provider, get_engine, list_adapters

__all__ = [
    "DataProvider",
    "ResearchEngine",
    "ExecutionEngine",
    "AgentEngine",
    "get_provider",
    "get_engine",
    "list_adapters",
]
