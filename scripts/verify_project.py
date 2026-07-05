"""
项目验证脚本 - 确保 QuantAgent 可以正常运行
"""
import sys
import os

def test_imports():
    print("🔍 测试模块导入...")
    try:
        from data.provider import DataProvider
        from data.cleaner import DataCleaner
        from strategies.base.strategy_base import StrategyBase
        from strategies.momentum.strategy import MomentumStrategy
        from research.backtest import BacktestEngine
        from risk.risk_engine import RiskEngine
        from knowledge.knowledge_base import KnowledgeBase
        print("✅ 所有核心模块导入成功")
        return True
    except Exception as e:
        print(f"❌ 导入失败: {e}")
        return False

def test_strategy_init():
    print("\n🔍 测试策略初始化...")
    try:
        from strategies.registry import create_strategy
        strategy = create_strategy("momentum")
        print(f"✅ 策略初始化成功: {strategy.name}")
        print(f"   配置: {strategy.config}")
        return True
    except Exception as e:
        print(f"❌ 策略初始化失败: {e}")
        return False

def test_risk_engine():
    print("\n🔍 测试风控引擎...")
    try:
        from risk.risk_engine import RiskEngine
        engine = RiskEngine()
        print(f"✅ 风控引擎初始化成功")
        print(f"   单票限制: {engine.config.max_single_position}")
        print(f"   行业限制: {engine.config.max_sector_exposure}")
        return True
    except Exception as e:
        print(f"❌ 风控引擎初始化失败: {e}")
        return False

def test_knowledge_base():
    print("\n🔍 测试知识库...")
    try:
        from knowledge.knowledge_base import KnowledgeBase
        kb = KnowledgeBase()
        print(f"✅ 知识库初始化成功")
        return True
    except Exception as e:
        print(f"❌ 知识库初始化失败: {e}")
        return False

def test_backtest_engine():
    print("\n🔍 测试回测引擎...")
    try:
        from research.backtest import BacktestEngine
        engine = BacktestEngine()
        print(f"✅ 回测引擎初始化成功")
        return True
    except Exception as e:
        print(f"❌ 回测引擎初始化失败: {e}")
        return False

def test_configs():
    print("\n🔍 测试配置加载...")
    try:
        from configs.settings import Settings
        settings = Settings()
        print(f"✅ 配置加载成功")
        print(f"   数据库路径: {settings.db_path}")
        print(f"   日志级别: {settings.log_level}")
        return True
    except Exception as e:
        print(f"❌ 配置加载失败: {e}")
        return False

def main():
    print("=" * 60)
    print("  QuantAgent 项目验证")
    print("=" * 60)
    
    results = []
    results.append(test_imports())
    results.append(test_strategy_init())
    results.append(test_risk_engine())
    results.append(test_knowledge_base())
    results.append(test_backtest_engine())
    results.append(test_configs())
    
    print("\n" + "=" * 60)
    if all(results):
        print("✅ 所有验证通过！项目可以正常运行")
        print("\n📌 下一步：推送到 GitHub")
        print("1. 在 GitHub 创建仓库")
        print("2. 运行以下命令：")
        print("   git init")
        print("   git add .")
        print("   git commit -m 'Initial commit'")
        print("   git remote add origin https://github.com/你的用户名/quant-system.git")
        print("   git push -u origin main")
        return 0
    else:
        print("❌ 部分验证失败，请检查错误信息")
        return 1

if __name__ == "__main__":
    sys.exit(main())