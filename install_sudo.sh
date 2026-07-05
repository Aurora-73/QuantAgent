#!/bin/bash
# ============================================================
# 需要 sudo 执行的依赖安装脚本
#
# 用法: sudo bash install_sudo.sh
# ============================================================

set -e

echo "=========================================="
echo "  安装系统依赖 (需要 sudo)"
echo "=========================================="
echo ""

# 1. 安装 TA-Lib C 库 (vnpy 需要)
echo "[1/3] 安装 TA-Lib C 库..."

if [ -f /usr/lib/libta_lib.so ] || [ -f /usr/local/lib/libta_lib.so ]; then
    echo "  TA-Lib 已安装，跳过"
else
    # 下载并编译 TA-Lib
    cd /tmp
    if [ ! -d ta-lib ]; then
        echo "  下载 TA-Lib..."
        wget -q http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
        tar -xzf ta-lib-0.4.0-src.tar.gz
    fi

    cd ta-lib
    echo "  编译 TA-Lib (可能需要几分钟)..."
    ./configure --prefix=/usr/local
    make -j$(nproc)
    make install
    ldconfig

    echo "  ✅ TA-Lib 安装完成"
fi

# 2. 安装 Python 开发文件 (qlib 编译需要)
echo ""
echo "[2/3] 安装 Python 开发文件..."
apt-get install -y python3-dev 2>/dev/null || echo "  python3-dev 已安装或不可用"

# 3. 安装 TA-Lib Python 绑定
echo ""
echo "[3/3] 安装 TA-Lib Python 绑定..."
pip3 install ta-lib 2>/dev/null || echo "  TA-Lib Python 绑定安装失败，尝试用 venv 安装"

echo ""
echo "=========================================="
echo "  sudo 依赖安装完成!"
echo "=========================================="
echo ""
echo "接下来请执行:"
echo "  cd $(dirname $0)"
echo "  bash install_venv.sh"
