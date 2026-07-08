#!/bin/bash
# ============================================================
# venv 内依赖安装脚本 (不需要 sudo)
#
# 用法: bash install_venv.sh
# 前提: 已执行 sudo bash install_sudo.sh
# ============================================================

set -e

VENV_DIR=".venv"

# 确保 venv 存在
if [ ! -d "$VENV_DIR" ]; then
    echo "创建虚拟环境..."
    python3 -m venv $VENV_DIR
fi

PIP="$VENV_DIR/bin/pip"
PYTHON="$VENV_DIR/bin/python"

echo "=========================================="
echo "  安装 venv 依赖"
echo "=========================================="
echo ""

# 1. 升级 pip
echo "[1/5] 升级 pip..."
$PIP install --upgrade pip setuptools wheel 2>&1 | tail -1

# 2. 安装核心依赖
echo ""
echo "[2/5] 安装核心依赖..."
$PIP install -r requirements.txt 2>&1 | tail -3

# 3. 安装 TA-Lib Python 绑定
echo ""
echo "[3/5] 安装 TA-Lib Python 绑定..."
$PIP install ta-lib 2>&1 | tail -2 || echo "  ⚠️ TA-Lib 安装失败，请先执行 sudo bash install_sudo.sh"

# 4. 安装 vnpy
echo ""
echo "[4/5] 安装 vnpy..."
$PIP install vnpy 2>&1 | tail -2 || echo "  ⚠️ vnpy 安装失败"

# 5. 安装 qlib
echo ""
echo "[5/5] 安装 qlib..."
$PIP install pyqlib 2>&1 | tail -2 || {
    echo "  pyqlib 安装失败，尝试从源码编译..."
    cd ../../_reference/qlib
    $PIP install -e . 2>&1 | tail -3
    cd ../../QuantAgent
}

# 6. 安装 OpenBB
echo ""
echo "[6/6] 安装 OpenBB..."
$PIP install openbb 2>&1 | tail -3 || echo "  ⚠️ OpenBB 安装失败，依赖较多，可后续手动安装"

echo ""
echo "=========================================="
echo "  安装完成! 验证中..."
echo "=========================================="
echo ""

$PYTHON -c "
print('=== 集成验证 ===')

try:
    import talib
    print('✅ TA-Lib')
except:
    print('❌ TA-Lib')

try:
    import vnpy
    print(f'✅ vnpy {vnpy.__version__}')
except:
    print('❌ vnpy')

try:
    import qlib
    print('✅ qlib')
except:
    print('❌ qlib')

try:
    from tradingagents.graph.trading_graph import TradingAgentsGraph
    print('✅ TradingAgents')
except:
    print('❌ TradingAgents')

try:
    import riskfolio
    print('✅ Riskfolio-Lib')
except:
    print('❌ Riskfolio-Lib')

try:
    import vectorbt
    print(f'✅ VectorBT {vectorbt.__version__}')
except:
    print('❌ VectorBT')

try:
    from openbb import obb
    print('✅ OpenBB')
except:
    print('❌ OpenBB')

print()
print('验证完成!')
"
