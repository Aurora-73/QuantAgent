#!/bin/bash
# ============================================================
# Quant System — Linux 服务器全量测试脚本
# ============================================================
# 按推荐顺序执行测试计划中的所有耗 CPU 任务。
#
# 用法:
#   bash scripts/run_all_tests.sh              # 执行全部测试
#   bash scripts/run_all_tests.sh --skip-p2    # 跳过 P2 任务
#   bash scripts/run_all_tests.sh --only-p0    # 只执行 P0
#   bash scripts/run_all_tests.sh --resume     # 从断点继续 (暂未实现)
#
# 环境要求:
#   - 已运行 source scripts/setup_env.sh
#   - 或手动激活 .venv 并配置代理
# ============================================================

set -euo pipefail

# ---- 配置 ----
QS_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$QS_ROOT"

RUN_ID="${TEST_RUN_ID:-$(date +%Y%m%d_%H%M%S)}"
LOG_DIR="${TEST_LOG_DIR:-$QS_ROOT/logs/$RUN_ID}"
mkdir -p "$LOG_DIR"

SKIP_P2=false
ONLY_P0=false
RESUME=false

for arg in "$@"; do
    case "$arg" in
        --skip-p2) SKIP_P2=true ;;
        --only-p0) ONLY_P0=true ;;
        --resume)  RESUME=true ;;
    esac
done

# ---- 工具函数 ----
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_header() {
    echo ""
    echo -e "${BLUE}============================================================${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}============================================================${NC}"
    echo ""
}

log_step() {
    echo -e "${GREEN}[STEP]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_result() {
    local step="$1"
    local status="$2"
    local duration="$3"
    local logfile="$4"
    if [ "$status" == "OK" ]; then
        echo -e "  ${GREEN}[OK]${NC}   $step (${duration}s) → $logfile"
    else
        echo -e "  ${RED}[FAIL]${NC} $step (${duration}s) → $logfile"
    fi
}

run_with_log() {
    # 运行命令并记录日志，返回退出码
    # 用法: run_with_log <步骤名> <日志文件名> <命令...>
    local step_name="$1"
    local log_name="$2"
    shift 2
    local logfile="$LOG_DIR/${log_name}.log"

    echo "============================================================"  > "$logfile"
    echo "  $step_name"                                                   >> "$logfile"
    echo "  开始时间: $(date '+%Y-%m-%d %H:%M:%S')"                      >> "$logfile"
    echo "  命令: $*"                                                    >> "$logfile"
    echo "============================================================" >> "$logfile"
    echo ""                                                              >> "$logfile"

    local start_time=$(date +%s)

    set +e
    "$@" >> "$logfile" 2>&1
    local exit_code=$?
    set -e

    local end_time=$(date +%s)
    local duration=$((end_time - start_time))

    echo ""                                                              >> "$logfile"
    echo "============================================================" >> "$logfile"
    echo "  结束时间: $(date '+%Y-%m-%d %H:%M:%S')"                      >> "$logfile"
    echo "  耗时: ${duration}s"                                          >> "$logfile"
    echo "  退出码: $exit_code"                                          >> "$logfile"
    echo "============================================================" >> "$logfile"

    if [ $exit_code -eq 0 ]; then
        log_result "$step_name" "OK" "$duration" "$logfile"
    else
        log_result "$step_name" "FAIL" "$duration" "$logfile"
    fi

    return $exit_code
}

# ---- 主流程 ----
log_header "Quant System — Linux 服务器测试"
echo "运行 ID:   $RUN_ID"
echo "日志目录:  $LOG_DIR"
echo "开始时间:  $(date '+%Y-%m-%d %H:%M:%S')"
echo "Python:    $(python --version 2>&1)"
echo "项目目录:  $QS_ROOT"
echo ""
echo "测试范围:"
echo "  P0: 因子计算 + 因子评估 + daily_research 全流程"
if [ "$ONLY_P0" = false ]; then
    echo "  P1: 回测 + 压力测试 + Brinson 归因"
    if [ "$SKIP_P2" = false ]; then
        echo "  P2: Walk-Forward 优化"
    fi
fi

# ---- 测试前备份 ----
log_header "0. 数据库备份"
DB_PATH="${QS_ROOT}/data/quant.duckdb"
if [ -f "$DB_PATH" ]; then
    BACKUP_PATH="${QS_ROOT}/data/quant.duckdb.backup.${RUN_ID}"
    cp "$DB_PATH" "$BACKUP_PATH"
    echo "[OK] 数据库已备份: $BACKUP_PATH"
else
    log_warn "数据库文件不存在: $DB_PATH (将全新创建)"
fi

# ---- 健康检查 ----
log_header "0.5 系统健康检查"
run_with_log "健康检查" "00_health_check" python -m scripts health-check --json || true

# ============================================================
# P0 任务
# ============================================================

# ---- 因子批量计算 (P0) ----
log_header "1. 因子批量计算 [P0] — 预计 30-60 分钟"
log_step "计算全部 29 个因子 (CSI300)"
run_with_log "因子计算" "01_compute_factors" \
    python -m scripts.compute_factors --universe csi300

# ---- 因子评估 (P0) ----
log_header "2. 因子评估与衰减检测 [P0] — 预计 10 分钟"
log_step "IC/ICIR 评估"
run_with_log "因子评估" "02_evaluate_factors" \
    python -m scripts.evaluate_factors --universe csi300

log_step "衰减检测"
run_with_log "衰减检测" "03_detect_decay" \
    python -m scripts.detect_decay --universe csi300

# ---- daily_research 全流程 (P0) ----
log_header "3. daily_research 全流程 [P0] — 预计 10-30 分钟"
log_step "运行完整每日研究流程 (非 LLM 模式)"
run_with_log "daily_research" "04_daily_research" \
    python -m scripts.daily_research --no-llm

# ---- P0 验收检查 ----
log_header "P0 验收检查"
echo "--- P0 验收结果 ---" > "$LOG_DIR/p0_acceptance.txt"
python -c "
import sys
sys.path.insert(0, '$QS_ROOT')
import duckdb
conn = duckdb.connect('$DB_PATH')

checks = {}

# 因子数量
r = conn.execute('SELECT COUNT(DISTINCT factor_name) FROM research.factors').fetchone()
checks['因子数量'] = (r[0], '>= 29' if r[0] >= 29 else 'FAIL')

# 因子评估
try:
    r = conn.execute('SELECT COUNT(*) FROM research.factor_evaluation').fetchone()
    checks['因子评估'] = (r[0], 'OK' if r[0] > 0 else 'FAIL')
except:
    checks['因子评估'] = (0, 'FAIL (表不存在)')

# 事件
try:
    r = conn.execute('SELECT COUNT(*) FROM events').fetchone()
    checks['事件数量'] = (r[0], 'OK' if r[0] > 0 else 'WARN')
except:
    checks['事件数量'] = (0, 'WARN')

# 决策记忆
try:
    r = conn.execute('SELECT COUNT(*) FROM decision_memory').fetchone()
    checks['决策记忆'] = (r[0], 'OK' if r[0] > 0 else 'WARN')
except:
    checks['决策记忆'] = (0, 'WARN')

print('')
print('指标                实际值    状态')
print('-' * 50)
all_ok = True
for name, (val, status) in checks.items():
    flag = '✅' if 'FAIL' not in status and 'WARN' not in status else ('⚠️' if 'WARN' in status else '❌')
    print(f'{name:<20s} {str(val):<10s} {flag} {status}')
    if 'FAIL' in status:
        all_ok = False
print('-' * 50)
print(f'P0 验收: {\"✅ 通过\" if all_ok else \"❌ 未通过\"}')
" 2>&1 | tee -a "$LOG_DIR/p0_acceptance.txt"

if [ "$ONLY_P0" = true ]; then
    log_header "P0 测试完成 (--only-p0)"
    echo "日志目录: $LOG_DIR"
    exit 0
fi

# ============================================================
# P1 任务
# ============================================================

# ---- 回测验证 (P1) ----
log_header "4. 回测验证 [P1] — 预计 10-20 分钟"

log_step "单策略回测: momentum, 600519"
run_with_log "回测_momentum_600519" "05_backtest_600519" \
    python -m scripts backtest --strategy momentum --ticker 600519 \
    --start 2024-01-01 --end 2026-06-30

log_step "单策略回测: momentum, 300750"
run_with_log "回测_momentum_300750" "06_backtest_300750" \
    python -m scripts backtest --strategy momentum --ticker 300750 \
    --start 2024-01-01 --end 2026-06-30

log_step "参数扫描回测: momentum, 600519"
run_with_log "回测_scan_600519" "07_backtest_scan" \
    python -m scripts backtest --strategy momentum --ticker 600519 \
    --mode walk-forward --start 2024-01-01 --end 2026-06-30 \
    --scan "lookback=10,20,30,entry_threshold=0.03,0.05,0.08" || true

# 回测验收
python -c "
import sys
sys.path.insert(0, '$QS_ROOT')
import duckdb
conn = duckdb.connect('$DB_PATH')
r1 = conn.execute('SELECT COUNT(*) FROM backtest_runs').fetchone()
r2 = conn.execute('SELECT COUNT(*) FROM backtest_equity').fetchone()
print(f'回测记录: {r1[0]} 条')
print(f'权益曲线: {r2[0]} 点')
print(f'回测验收: {\"✅ 通过\" if r1[0] > 0 else \"❌ 失败\"}  ')
" 2>&1

# ---- 压力测试与 Brinson (P1) ----
log_header "5. 压力测试与 Brinson 归因 [P1] — 预计 5-10 分钟"

log_step "压力测试: 600519"
run_with_log "压力测试" "08_stress_test" \
    python -m scripts.run_stress_test --ticker 600519

log_step "Brinson 归因 (示例)"
run_with_log "Brinson归因" "09_brinson" \
    python -m scripts.run_brinson_attribution || true

if [ "$SKIP_P2" = true ]; then
    log_header "P0+P1 测试完成 (--skip-p2)"
    echo "日志目录: $LOG_DIR"
    exit 0
fi

# ============================================================
# P2 任务
# ============================================================

# ---- Walk-Forward 优化 (P2) ----
log_header "6. Walk-Forward 优化 [P2] — 预计 5-15 分钟"
log_step "滚动窗口优化: 600519, 2022-2026"
run_with_log "WalkForward" "10_walk_forward" \
    python -m scripts backtest --mode walk-forward --ticker 600519 \
    --start 2022-01-01 --end 2026-06-30 || true

# ============================================================
# 全部测试完成
# ============================================================
log_header "全部测试完成"
echo "运行 ID:   $RUN_ID"
echo "日志目录:  $LOG_DIR"
echo "完成时间:  $(date '+%Y-%m-%d %H:%M:%S')"

# 汇总所有步骤的结果
echo ""
echo "============================================================"
echo "  测试结果汇总"
echo "============================================================"
PASS=0
FAIL=0
for logfile in "$LOG_DIR"/*.log; do
    name=$(basename "$logfile" .log)
    # 跳过验收文件
    [[ "$name" == "p0_acceptance" ]] && continue

    # 检查日志末尾的退出码
    exit_code=$(tail -5 "$logfile" | grep "退出码:" | awk '{print $2}' || echo "?")
    if [ "$exit_code" = "0" ]; then
        echo -e "  ${GREEN}[PASS]${NC} $name"
        ((PASS++)) || true
    elif [ "$exit_code" = "?" ]; then
        echo -e "  ${YELLOW}[????]${NC} $name (未正常结束)"
    else
        echo -e "  ${RED}[FAIL]${NC} $name (exit=$exit_code)"
        ((FAIL++)) || true
    fi
done

echo ""
echo "通过: $PASS, 失败: $FAIL"
echo ""
echo "查看详细日志:"
echo "  ls -la $LOG_DIR/"
echo "  grep -E 'ERROR|FATAL|Traceback' $LOG_DIR/*.log"
echo ""
echo "如需回滚数据库:"
echo "  cp $QS_ROOT/data/quant.duckdb.backup.${RUN_ID} $QS_ROOT/data/quant.duckdb"
