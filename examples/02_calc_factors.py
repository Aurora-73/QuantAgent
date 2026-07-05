"""
示例2：计算因子

用法：python examples/02_calc_factors.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data.provider import DataProvider
from research.factors import FactorEngine

print("=" * 50)
print("  示例2：计算因子")
print("=" * 50)
print()

# 1. 获取数据
print("[1] 获取贵州茅台数据...")
df = DataProvider.get_stock_daily("600519", "2024-01-01", "2024-12-31")
print(f"    获取到 {len(df)} 条数据")

# 2. 计算所有因子
print("\n[2] 计算因子...")
engine = FactorEngine()
df_factors = engine.compute_all(df)

# 3. 列出所有因子
print("\n[3] 内置因子列表（共 {} 个）：".format(len(engine.list_factors())))
for name, desc in engine.list_factors().items():
    print(f"    {name}: {desc}")

# 4. 查看最新因子值
print("\n[4] 最新因子值：")
latest = df_factors.iloc[-1]
for col in ["momentum_5d", "momentum_20d", "rsi_14", "volatility_20d",
            "volume_ratio_5d", "bollinger_position"]:
    val = latest.get(col)
    if val is not None and str(val) != "nan":
        print(f"    {col}: {val:.4f}")

# 5. 因子统计
print("\n[5] 因子统计：")
for col in ["momentum_20d", "rsi_14", "volatility_20d"]:
    series = df_factors[col].dropna()
    if not series.empty:
        print(f"    {col}:")
        print(f"      均值: {series.mean():.4f}")
        print(f"      标准差: {series.std():.4f}")
        print(f"      最小值: {series.min():.4f}")
        print(f"      最大值: {series.max():.4f}")

print("\n" + "=" * 50)
print("  完成！")
print("=" * 50)
