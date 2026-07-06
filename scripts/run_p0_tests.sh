#!/bin/bash
# ============================================================
# P0 任务快速执行脚本
# ============================================================
# 用法: bash scripts/run_p0_tests.sh
#
# 包含: 健康检查 → 因子计算 → 因子评估 → daily_research
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo ">>> P0 测试 (因子计算 + 评估 + daily_research)"
echo ">>> 预计总耗时: 50-100 分钟"
echo ""

bash "$SCRIPT_DIR/run_all_tests.sh" --only-p0
