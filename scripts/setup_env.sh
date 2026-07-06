#!/bin/bash
# ============================================================
# Quant System — Linux 环境初始化脚本
# ============================================================
# 用法: source scripts/setup_env.sh
# 或:   . scripts/setup_env.sh
#
# 功能:
#   - 激活 Python 虚拟环境
#   - 配置 HTTP 代理（7890 端口，用于访问 GitHub/OpenAI/PyPI 等外网）
#   - 设置 PYTHONPATH
#   - 创建必要的运行时目录
#   - 配置 AKShare 不走代理（eastmoney.com 国内站点）
# ============================================================

set -a  # 自动导出所有变量

# ---- 项目根目录 ----
export QS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$QS_ROOT" || { echo "[ERROR] 无法进入项目目录: $QS_ROOT"; return 1; }

# ---- Python 虚拟环境 ----
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
    echo "[OK] 虚拟环境已激活: $(which python)"
elif command -v python3 &>/dev/null; then
    echo "[WARN] .venv 不存在，使用系统 Python: $(which python3)"
else
    echo "[ERROR] 未找到 Python3，请先安装"
    return 1
fi

# ---- PYTHONPATH ----
export PYTHONPATH="$QS_ROOT:$PYTHONPATH"

# ---- HTTP 代理配置 ----
# 外网站点 (GitHub, OpenAI, PyPI, Google) 走代理
# 国内站点 (eastmoney.com, baostock, AKShare) 不走代理
PROXY_HOST="127.0.0.1"
PROXY_PORT="${PROXY_PORT:-7890}"

# 如果代理可用则启用
if nc -z "$PROXY_HOST" "$PROXY_PORT" 2>/dev/null; then
    export http_proxy="http://${PROXY_HOST}:${PROXY_PORT}"
    export https_proxy="http://${PROXY_HOST}:${PROXY_PORT}"
    export HTTP_PROXY="http://${PROXY_HOST}:${PROXY_PORT}"
    export HTTPS_PROXY="http://${PROXY_HOST}:${PROXY_PORT}"
    # 国内站点不走代理
    export no_proxy="localhost,127.0.0.1,eastmoney.com,baostock.com,10.*,192.168.*,*.cn"
    export NO_PROXY="$no_proxy"
    echo "[OK] 代理已配置: http://${PROXY_HOST}:${PROXY_PORT}"
else
    echo "[WARN] 代理 ${PROXY_HOST}:${PROXY_PORT} 不可用，直连模式"
    unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY
fi

# ---- 创建运行时目录 ----
mkdir -p "$QS_ROOT/logs"
mkdir -p "$QS_ROOT/data"
mkdir -p "$QS_ROOT/knowledge/daily"
mkdir -p "$QS_ROOT/knowledge/weekly"
mkdir -p "$QS_ROOT/knowledge/monthly"

# ---- 日志时间戳 ----
export TEST_RUN_ID="$(date +%Y%m%d_%H%M%S)"
export TEST_LOG_DIR="$QS_ROOT/logs/$TEST_RUN_ID"
mkdir -p "$TEST_LOG_DIR"

echo "[OK] 运行 ID: $TEST_RUN_ID"
echo "[OK] 日志目录: $TEST_LOG_DIR"
echo "[OK] Python: $(python --version 2>&1)"
echo "[OK] 项目目录: $QS_ROOT"
echo ""
echo "环境就绪。可用命令:"
echo "  python -m scripts health-check"
echo "  python -m scripts daily-research --no-llm"
echo "  python -m scripts compute_factors --universe csi300"
echo "  python -m scripts evaluate_factors"
echo "  bash scripts/run_all_tests.sh"
echo ""

set +a
