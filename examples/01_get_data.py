"""
示例1：获取股票数据

用法：python examples/01_get_data.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data.provider import DataProvider
from data.storage import DataStorage

print("=" * 50)
print("  示例1：获取股票数据")
print("=" * 50)
print()

# 1. 从 AKShare 获取数据
print("[1] 获取贵州茅台(600519)日线数据...")
df = DataProvider.get_stock_daily("600519", "2024-01-01", "2024-12-31")
print(f"    获取到 {len(df)} 条数据")

if not df.empty:
    print("\n    最近5天数据：")
    print(df[["open", "high", "low", "close", "volume"]].tail().to_string())

# 2. 保存到本地数据库
print("\n[2] 保存到本地数据库...")
storage = DataStorage()
storage.save_stock_daily("600519", df)
print("    ✅ 保存完成")

# 3. 从本地数据库加载
print("\n[3] 从本地数据库加载...")
df_loaded = storage.load_stock_daily("600519", "2024-01-01", "2024-12-31")
print(f"    加载到 {len(df_loaded)} 条数据")

# 4. 查看数据库统计
print("\n[4] 数据库统计：")
stats = storage.get_table_stats()
for table, count in stats.items():
    print(f"    {table}: {count} 条")

print("\n" + "=" * 50)
print("  完成！")
print("=" * 50)
