"""
示例3：回测策略

用法：python examples/03_backtest.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from data.provider import DataProvider
from research.factors import FactorEngine
from research.backtest import BacktestEngine

print("=" * 50)
print("  示例3：回测动量策略")
print("=" * 50)
print()

# 1. 获取数据
print("[1] 获取贵州茅台数据 (2023-2024)...")
df = DataProvider.get_stock_daily("600519", "2023-01-01", "2024-12-31")
print(f"    获取到 {len(df)} 条数据")

if df.empty:
    print("    ❌ 数据获取失败，请检查网络")
    sys.exit(1)

# 2. 计算因子
print("\n[2] 计算因子...")
engine = FactorEngine()
df_factors = engine.compute_all(df)

# 3. 生成信号
print("\n[3] 生成交易信号...")
momentum = df_factors["momentum_20d"].fillna(0)

# 买入条件：20日动量 > 5%（上涨趋势）
entries = momentum > 0.05
# 卖出条件：20日动量 < -2%（下跌趋势）
exits = momentum < -0.02

print(f"    买入信号: {entries.sum()} 次")
print(f"    卖出信号: {exits.sum()} 次")

# 4. 回测
print("\n[4] 运行回测...")
result = BacktestEngine.signal_backtest(
    close=df_factors["close"],
    entries=entries,
    exits=exits,
    init_cash=1_000_000,  # 初始资金100万
    fees=0.001,            # 手续费0.1%
    slippage=0.001,        # 滑点0.1%
)

# 5. 输出结果
print("\n[5] 回测结果：")
print(f"    {'='*40}")
print(f"    总收益:    {result['total_return']:.2%}")
print(f"    夏普比率:  {result['sharpe_ratio']:.2f}")
print(f"    最大回撤:  {result['max_drawdown']:.2%}")
print(f"    交易次数:  {result['trade_count']}")
print(f"    {'='*40}")

# 6. 结果解读
print("\n[6] 结果解读：")
sharpe = result['sharpe_ratio']
if sharpe > 1.5:
    print("    ✅ 夏普比率优秀 (>1.5)")
elif sharpe > 0.5:
    print("    ⚠️ 夏普比率一般 (0.5-1.5)")
else:
    print("    ❌ 夏普比率较差 (<0.5)")

dd = result['max_drawdown']
if dd > -0.10:
    print("    ✅ 最大回撤可控 (<10%)")
elif dd > -0.20:
    print("    ⚠️ 最大回撤偏大 (10%-20%)")
else:
    print("    ❌ 最大回撤过大 (>20%)")

# 7. 保存权益曲线
equity = result.get("equity_curve")
if equity is not None:
    equity.to_csv("examples/backtest_result.csv")
    print("\n    权益曲线已保存: examples/backtest_result.csv")

print("\n" + "=" * 50)
print("  完成！")
print("=" * 50)
