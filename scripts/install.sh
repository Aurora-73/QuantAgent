#!/bin/bash
# QuantAgent - Linux/Mac 一键安装脚本
#
# 用法:
#   bash scripts/install.sh

set -e

echo "=========================================="
echo "  QuantAgent Linux/Mac 一键安装脚本"
echo "=========================================="

echo ""
echo "[1/6] 检查环境..."

if ! command -v python3 &> /dev/null; then
    echo "❌ Python 未安装"
    echo "   请安装 Python 3.10+: sudo apt install python3 python3-venv python3-pip (Ubuntu)"
    exit 1
fi

if ! command -v git &> /dev/null; then
    echo "❌ Git 未安装"
    echo "   请安装 Git: sudo apt install git (Ubuntu)"
    exit 1
fi

echo "✅ Python: $(python3 --version)"
echo "✅ Git: $(git --version)"

echo ""
echo "[2/6] 创建虚拟环境..."

if [ -d ".venv" ]; then
    echo "   .venv 已存在，跳过创建"
else
    python3 -m venv .venv
    echo "✅ 虚拟环境创建成功"
fi

echo ""
echo "[3/6] 激活虚拟环境并安装依赖..."

source .venv/bin/activate

echo "   安装核心依赖..."
pip install -r requirements.txt

echo "✅ 核心依赖安装成功"

echo ""
echo "[4/6] 创建配置文件..."

if [ ! -d "configs" ]; then
    mkdir -p configs
fi

if [ ! -f "configs/.env" ]; then
    cp configs/.env.example configs/.env
    echo "✅ 配置文件创建成功 (configs/.env)"
else
    echo "   配置文件已存在，跳过创建"
fi

echo ""
echo "[5/6] 创建必要目录..."

dirs=("data" "logs" "knowledge/daily" "knowledge/weekly" "knowledge/monthly")
for dir in "${dirs[@]}"; do
    if [ ! -d "$dir" ]; then
        mkdir -p "$dir"
        echo "   创建目录: $dir"
    fi
done
echo "✅ 目录创建成功"

echo ""
echo "[6/6] 验证安装..."

python verify_project.py

if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "  ✅ 安装成功！"
    echo "=========================================="
    echo ""
    echo "使用方法:"
    echo "  1. 激活虚拟环境: source .venv/bin/activate"
    echo "  2. 运行测试: python -m pytest"
    echo "  3. 运行示例: python examples/00_quick_start.py"
    echo "  4. 修改配置: 编辑 configs/.env"
    echo ""
    echo "可选安装:"
    echo "  Qlib: pip install qlib"
    echo "  vnpy: pip install ta-lib vnpy vnpy-ctp"
    echo "  OpenBB: pip install openbb"
else
    echo ""
    echo "=========================================="
    echo "  ❌ 安装失败，请检查错误信息"
    echo "=========================================="
    exit 1
fi