"""
示例5：LLM 多Agent分析

用法：python examples/05_llm_analysis.py
前提：需要配置 OPENAI_API_KEY
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

print("=" * 50)
print("  示例5：LLM 多Agent分析")
print("=" * 50)
print()

# 检查 API Key
import os
if not os.getenv("OPENAI_API_KEY"):
    print("⚠️  未配置 OPENAI_API_KEY")
    print("请按以下步骤操作：")
    print("  1. cp configs/.env.example configs/.env")
    print("  2. 编辑 configs/.env，填入 OPENAI_API_KEY=sk-xxx")
    print("  3. 重新运行本脚本")
    sys.exit(1)

from integrations.trading_agents import TradingAgentsEngine

# 1. 创建引擎
print("[1] 创建 TradingAgents 引擎...")
engine = TradingAgentsEngine()

# 2. 分析股票
ticker = "NVDA"
date = "2026-06-03"
print(f"\n[2] 分析 {ticker}...")
print("    这需要 2-5 分钟，请等待...\n")

try:
    result = engine.analyze(ticker, date)

    # 3. 输出结果
    print("\n" + "=" * 50)
    print(f"  分析结果：{result['signal']}")
    print("=" * 50)

    score = engine.get_signal_score(result['signal'])
    print(f"\n  信号分数: {score:.1f}")
    print()
    print("  信号含义：")
    print("    Buy         = 买入   (分数 1.0)")
    print("    Overweight  = 增持   (分数 0.5)")
    print("    Hold        = 持有   (分数 0.0)")
    print("    Underweight = 减持   (分数 -0.5)")
    print("    Sell        = 卖出   (分数 -1.0)")

except Exception as e:
    print(f"\n❌ 分析失败: {e}")
    print("\n可能的原因：")
    print("  1. API Key 无效或余额不足")
    print("  2. 网络连接问题")
    print("  3. 股票代码格式错误")

print("\n" + "=" * 50)
print("  完成！")
print("=" * 50)
