#!/bin/bash
# ============================================================
# 快速验证脚本 — 测试完成后运行，检查所有验收指标
# ============================================================
# 用法: bash scripts/quick_verify.sh
# ============================================================
set -euo pipefail

QS_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$QS_ROOT"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

DB_PATH="${QS_ROOT}/data/quant.duckdb"

if [ ! -f "$DB_PATH" ]; then
    echo -e "${RED}[FATAL]${NC} 数据库不存在: $DB_PATH"
    exit 1
fi

echo "============================================================"
echo "  Quant System 验收检查"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================================"
echo ""

python -c "
import sys
sys.path.insert(0, '$QS_ROOT')
import duckdb
conn = duckdb.connect('$DB_PATH')

def check(name, sql, target, target_desc):
    try:
        r = conn.execute(sql).fetchone()
        val = r[0]
    except Exception as e:
        print(f'  {name:<20s}: ERROR - {e}')
        return False

    if isinstance(target, (int, float)):
        ok = val >= target
    elif target == 'non_empty':
        ok = val is not None and val != ''
    elif target == 'file_exists':
        import os
        ok = os.path.exists(val) if val else False
    else:
        ok = val == target

    flag = '✅' if ok else '❌'
    print(f'  {flag} {name:<18s} {str(val):>12s}  (目标: {target_desc})')
    return ok

print('--- 核心指标 ---')
all_ok = True

all_ok &= check('因子数量',
    'SELECT COUNT(DISTINCT factor_name) FROM research.factors',
    29, '>= 29')

all_ok &= check('因子总行数',
    'SELECT COUNT(*) FROM research.factors',
    1_000_000, '>= 1,000,000')

try:
    all_ok &= check('因子评估',
        'SELECT COUNT(*) FROM research.factor_evaluation',
        1, '> 0')
except:
    print('  ⚠️  因子评估         (表不存在)')
    all_ok = False

try:
    all_ok &= check('事件数量',
        'SELECT COUNT(*) FROM events',
        1, '> 0')
except:
    print('  ⚠️  事件数量         (表不存在)')
    all_ok = False

try:
    all_ok &= check('决策记忆',
        'SELECT COUNT(*) FROM decision_memory',
        1, '> 0')
except:
    print('  ⚠️  决策记忆         (表不存在)')
    all_ok = False

try:
    all_ok &= check('回测记录',
        'SELECT COUNT(*) FROM backtest_runs',
        1, '> 0')
except:
    print('  ⚠️  回测记录         (表不存在)')
    all_ok = False

print('')
print('--- 日报文件 ---')
import os
daily_dir = '$QS_ROOT/knowledge/daily'
if os.path.isdir(daily_dir):
    reports = sorted([f for f in os.listdir(daily_dir) if f.endswith('.md')])
    print(f'  日报数: {len(reports)}')
    if reports:
        print(f'  最新: {reports[-1]}')
    all_ok &= len(reports) > 0
else:
    print('  ⚠️  knowledge/daily/ 不存在')
    all_ok = False

print('')
print('--- 数据库统计 ---')
tables = conn.execute(\"\"\"
    SELECT table_schema || '.' || table_name, estimated_size
    FROM duckdb_tables()
    WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
    ORDER BY table_schema, table_name
\"\"\").fetchall()
for schema_table, size in tables:
    row_count = conn.execute(f'SELECT COUNT(*) FROM {schema_table}').fetchone()[0]
    size_mb = (size or 0) / (1024*1024)
    print(f'  {schema_table:<40s} {row_count:>10,d} 行  {size_mb:>8.1f} MB')

conn.close()

print('')
print('='*60)
if all_ok:
    print('  验收结果: ✅ 全部通过')
else:
    print('  验收结果: ❌ 部分未通过 (见上方 ❌ 标记)')
print('='*60)
"
