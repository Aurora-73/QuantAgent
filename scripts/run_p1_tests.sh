#!/bin/bash
# ============================================================
# P1 任务快速执行脚本
# ============================================================
# 用法: bash scripts/run_p1_tests.sh
#
# 前置条件: P0 任务已完成（因子表有数据）
# 包含: 回测 → 压力测试 → Brinson 归因
# ============================================================
set -euo pipefail

QS_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$QS_ROOT"

RUN_ID="${TEST_RUN_ID:-$(date +%Y%m%d_%H%M%S)}"
LOG_DIR="${TEST_LOG_DIR:-$QS_ROOT/logs/$RUN_ID}"
mkdir -p "$LOG_DIR"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

run_cmd() {
    local step="$1"
    local log="$2"
    shift 2
    echo -e "${GREEN}[RUN]${NC} $step"
    "$@" > "$LOG_DIR/${log}.log" 2>&1
    local rc=$?
    if [ $rc -eq 0 ]; then
        echo -e "  ${GREEN}[OK]${NC}  $step → $LOG_DIR/${log}.log"
    else
        echo -e "  ${RED}[FAIL]${NC} $step (exit=$rc) → $LOG_DIR/${log}.log"
    fi
    return $rc
}

echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}  P1 测试 — 回测 + 风控${NC}"
echo -e "${BLUE}============================================================${NC}"
echo ""
echo "前置检查: 因子数据..."
FACTOR_COUNT=$(python -c "
import sys; sys.path.insert(0, '$QS_ROOT')
import duckdb
conn = duckdb.connect('$QS_ROOT/data/quant.duckdb')
print(conn.execute('SELECT COUNT(DISTINCT factor_name) FROM research.factors').fetchone()[0])
" 2>/dev/null || echo "0")

if [ "$FACTOR_COUNT" -lt 10 ]; then
    echo -e "${RED}[ERROR]${NC} 因子数据不足 ($FACTOR_COUNT < 10), 请先运行 P0 测试"
    exit 1
fi
echo -e "${GREEN}[OK]${NC} 因子数: $FACTOR_COUNT"
echo ""

# 回测
echo -e "${BLUE}--- 4. 回测验证 [P1] ---${NC}"
run_cmd "回测: momentum, 600519" "p1_backtest_600519" \
    python -m scripts backtest --strategy momentum --ticker 600519 \
    --start 2024-01-01 --end 2026-06-30

run_cmd "回测: momentum, 300750" "p1_backtest_300750" \
    python -m scripts backtest --strategy momentum --ticker 300750 \
    --start 2024-01-01 --end 2026-06-30

# 压力测试
echo -e "${BLUE}--- 5. 压力测试与 Brinson 归因 [P1] ---${NC}"
run_cmd "压力测试: 600519" "p1_stress_test" \
    python -m scripts.run_stress_test --ticker 600519

run_cmd "Brinson 归因" "p1_brinson" \
    python -m scripts.run_brinson_attribution || true

echo ""
echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}  P1 测试完成${NC}"
echo -e "${BLUE}  日志目录: $LOG_DIR${NC}"
echo -e "${BLUE}============================================================${NC}"
