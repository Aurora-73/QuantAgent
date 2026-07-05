"""
快速开始：验证系统是否正常工作

用法：python examples/00_quick_start.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

print("=" * 60)
print("  Quant System 快速验证")
print("=" * 60)
print()

errors = []

# 1. 检查核心依赖
print("[1/6] 检查核心依赖...")
try:
    import pandas as pd
    print(f"    ✅ pandas {pd.__version__}")
except:
    print("    ❌ pandas")
    errors.append("pandas")

try:
    import numpy as np
    print(f"    ✅ numpy {np.__version__}")
except:
    print("    ❌ numpy")
    errors.append("numpy")

try:
    import duckdb
    print(f"    ✅ duckdb {duckdb.__version__}")
except:
    print("    ❌ duckdb")
    errors.append("duckdb")

# 2. 检查量化依赖
print("\n[2/6] 检查量化依赖...")
try:
    import talib
    print(f"    ✅ TA-Lib {talib.__version__}")
except:
    print("    ❌ TA-Lib")
    errors.append("TA-Lib")

try:
    import vnpy
    print(f"    ✅ vnpy {vnpy.__version__}")
except:
    print("    ❌ vnpy")
    errors.append("vnpy")

try:
    import qlib
    print(f"    ✅ qlib {qlib.__version__}")
except:
    print("    ❌ qlib")
    errors.append("qlib")

try:
    import torch
    print(f"    ✅ PyTorch {torch.__version__}")
except:
    print("    ❌ PyTorch")
    errors.append("PyTorch")

try:
    import lightgbm
    print(f"    ✅ LightGBM {lightgbm.__version__}")
except:
    print("    ❌ LightGBM")
    errors.append("LightGBM")

# 3. 检查集成模块
print("\n[3/6] 检查集成模块...")
try:
    from integrations.qlib_engine import QlibEngine, HAS_QLIB
    status = "✅" if HAS_QLIB else "⚠️"
    print(f"    {status} QlibEngine (HAS_QLIB={HAS_QLIB})")
except Exception as e:
    print(f"    ❌ QlibEngine: {e}")

try:
    from integrations.vnpy_engine import VnpyEngine, HAS_VNPY
    status = "✅" if HAS_VNPY else "⚠️"
    print(f"    {status} VnpyEngine (HAS_VNPY={HAS_VNPY})")
except Exception as e:
    print(f"    ❌ VnpyEngine: {e}")

try:
    from integrations.trading_agents import TradingAgentsEngine, HAS_TRADING_AGENTS
    status = "✅" if HAS_TRADING_AGENTS else "⚠️"
    print(f"    {status} TradingAgentsEngine (HAS_TRADING_AGENTS={HAS_TRADING_AGENTS})")
except Exception as e:
    print(f"    ❌ TradingAgentsEngine: {e}")

# 4. 检查自研模块
print("\n[4/6] 检查自研模块...")
modules = [
    ("data.provider", "DataProvider"),
    ("data.storage", "DataStorage"),
    ("research.factors", "FactorEngine"),
    ("research.backtest", "BacktestEngine"),
    ("risk.risk_engine", "RiskEngine"),
    ("risk.portfolio", "PortfolioOptimizer"),
    ("knowledge.knowledge_base", "KnowledgeBase"),
    ("monitoring.metrics", "MetricsTracker"),
    ("strategies.base", "StrategyBase"),
]
for module_name, class_name in modules:
    try:
        module = __import__(module_name, fromlist=[class_name])
        getattr(module, class_name)
        print(f"    ✅ {class_name}")
    except Exception as e:
        print(f"    ❌ {class_name}: {e}")

# 5. 测试数据获取
print("\n[5/6] 测试数据获取...")
try:
    from data.provider import DataProvider
    df = DataProvider.get_stock_daily("600519", "2024-01-01", "2024-01-10")
    if not df.empty:
        print(f"    ✅ 获取到 {len(df)} 条数据")
    else:
        print("    ⚠️ 数据为空（可能是网络问题）")
except Exception as e:
    print(f"    ❌ 数据获取失败: {e}")

# 6. 测试因子计算
print("\n[6/6] 测试因子计算...")
try:
    import pandas as pd
    import numpy as np
    dates = pd.date_range("2024-01-01", periods=100, freq="B")
    np.random.seed(42)
    df = pd.DataFrame({
        "open": 1800 + np.cumsum(np.random.randn(100) * 10),
        "high": 1800 + np.cumsum(np.random.randn(100) * 10) + 20,
        "low": 1800 + np.cumsum(np.random.randn(100) * 10) - 20,
        "close": 1800 + np.cumsum(np.random.randn(100) * 10),
        "volume": np.random.randint(10000, 100000, 100),
        "amount": np.random.uniform(1e8, 5e8, 100),
        "pct_change": np.random.randn(100) * 2,
        "turnover": np.random.uniform(0.5, 3.0, 100),
    }, index=dates)

    from research.factors import FactorEngine
    engine = FactorEngine()
    df_factors = engine.compute_all(df)
    factors = engine.list_factors()
    print(f"    ✅ 计算了 {len(factors)} 个因子")
except Exception as e:
    print(f"    ❌ 因子计算失败: {e}")

# 总结
print("\n" + "=" * 60)
if errors:
    print(f"  验证完成！有 {len(errors)} 个问题需要解决：")
    for e in errors:
        print(f"    - {e}")
else:
    print("  验证完成！所有模块正常工作！")
print("=" * 60)

print("\n下一步：")
print("  1. 运行 examples/01_get_data.py 获取数据")
print("  2. 运行 examples/02_calc_factors.py 计算因子")
print("  3. 运行 examples/03_backtest.py 回测策略")
print("  4. 运行 examples/04_knowledge.py 使用知识库")
print("  5. 运行 examples/05_llm_analysis.py LLM分析（需要API Key）")
