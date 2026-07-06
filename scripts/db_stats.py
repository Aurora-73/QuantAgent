"""
数据库统计 — 输出各表行数、关键指标

用法：
    python -m scripts.db_stats
    python scripts/db_stats.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data.storage import DataStorage
from configs.settings import settings


def main():
    storage = DataStorage(settings.db_path)
    conn = storage.conn

    print("=== 数据库表统计 ===")
    print(f"数据库路径: {settings.db_path}")

    tables = conn.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'main'
        ORDER BY table_name
    """).fetchall()

    print(f"表数量: {len(tables)}")
    print()

    total_rows = 0
    for (table_name,) in tables:
        try:
            count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            total_rows += count
            print(f"  {table_name:30s}  {count:>10,} 行")
        except Exception as e:
            print(f"  {table_name:30s}  ERROR: {e}")

    print()
    print(f"总行数: {total_rows:,}")

    schemas = conn.execute("""
        SELECT schema_name
        FROM information_schema.schemata
        WHERE schema_name NOT IN ('main', 'information_schema', 'pg_catalog')
        ORDER BY schema_name
    """).fetchall()

    if schemas:
        print()
        print("=== 分层 Schema ===")
        for (schema_name,) in schemas:
            schema_tables = conn.execute(f"""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = '{schema_name}'
            """).fetchall()
            print(f"  {schema_name}: {len(schema_tables)} 张表")
            for (tbl,) in schema_tables[:10]:
                print(f"    - {tbl}")

    print()
    print("=== 关键指标 ===")

    # 股票数量
    try:
        tickers = conn.execute("SELECT COUNT(DISTINCT ticker) FROM stock_daily").fetchone()[0]
        print(f"  股票数量 (stock_daily): {tickers}")
    except Exception as e:
        print(f"  股票数量: ERROR {e}")

    # 最新日期
    try:
        latest = conn.execute("SELECT MAX(date) FROM stock_daily").fetchone()[0]
        print(f"  最新行情日期: {latest}")
    except Exception as e:
        print(f"  最新行情日期: ERROR {e}")

    # 因子数
    try:
        factors = conn.execute("SELECT COUNT(DISTINCT factor_name) FROM factors").fetchone()[0]
        print(f"  因子数量 (factors 表): {factors}")
    except Exception as e:
        print(f"  因子数量: ERROR {e}")

    # 回测次数
    try:
        backtests = conn.execute("SELECT COUNT(*) FROM backtest_runs").fetchone()[0]
        print(f"  回测次数: {backtests}")
    except Exception as e:
        print(f"  回测次数: ERROR {e}")

    # 事件数
    try:
        events = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        print(f"  事件数: {events}")
    except Exception as e:
        print(f"  事件数: ERROR {e}")

    # 预测数
    try:
        preds = conn.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
        print(f"  预测数: {preds}")
    except Exception as e:
        print(f"  预测数: ERROR {e}")

    # 决策记忆
    try:
        decs = conn.execute("SELECT COUNT(*) FROM decision_memory").fetchone()[0]
        print(f"  决策记忆: {decs}")
    except Exception as e:
        print(f"  决策记忆: ERROR {e}")

    if hasattr(storage, 'close'):
        storage.close()


if __name__ == "__main__":
    main()
