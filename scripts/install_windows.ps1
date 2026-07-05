$ErrorActionPreference = "Stop"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  QuantAgent Windows 一键安装脚本" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

Write-Host ""
Write-Host "[1/6] 检查环境..." -ForegroundColor Yellow

try {
    Get-Command python -ErrorAction Stop | Out-Null
    Write-Host "OK: Python: $(python --version 2>&1)" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Python 未安装或未添加到 PATH" -ForegroundColor Red
    Write-Host "请从 https://www.python.org/downloads/ 安装 Python 3.10+" -ForegroundColor Red
    exit 1
}

try {
    Get-Command git -ErrorAction Stop | Out-Null
    Write-Host "OK: Git: $(git --version)" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Git 未安装或未添加到 PATH" -ForegroundColor Red
    Write-Host "请从 https://git-scm.com/download/win 安装 Git" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[2/6] 创建虚拟环境..." -ForegroundColor Yellow

if (Test-Path ".venv") {
    Write-Host ".venv 已存在，跳过创建" -ForegroundColor Gray
} else {
    python -m venv .venv
    Write-Host "OK: 虚拟环境创建成功" -ForegroundColor Green
}

Write-Host ""
Write-Host "[3/6] 激活虚拟环境并安装依赖..." -ForegroundColor Yellow

$venvActivate = ".venv\Scripts\Activate.ps1"
if (-not (Test-Path $venvActivate)) {
    Write-Host "ERROR: 虚拟环境激活脚本不存在" -ForegroundColor Red
    exit 1
}

& $venvActivate

Write-Host "安装核心依赖..." -ForegroundColor Gray
pip install -r requirements.txt

Write-Host "OK: 核心依赖安装成功" -ForegroundColor Green

Write-Host ""
Write-Host "[4/6] 创建配置文件..." -ForegroundColor Yellow

if (-not (Test-Path "configs")) {
    New-Item -ItemType Directory -Path "configs" | Out-Null
}

if (-not (Test-Path "configs\.env")) {
    Copy-Item "configs\.env.example" "configs\.env" -Force
    Write-Host "OK: 配置文件创建成功 (configs/.env)" -ForegroundColor Green
} else {
    Write-Host "配置文件已存在，跳过创建" -ForegroundColor Gray
}

Write-Host ""
Write-Host "[5/6] 创建必要目录..." -ForegroundColor Yellow

$dirs = @("data", "logs", "knowledge/daily", "knowledge/weekly", "knowledge/monthly")
foreach ($dir in $dirs) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir | Out-Null
        Write-Host "创建目录: $dir" -ForegroundColor Gray
    }
}
Write-Host "OK: 目录创建成功" -ForegroundColor Green

Write-Host ""
Write-Host "[6/6] 验证安装..." -ForegroundColor Yellow

python verify_project.py

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "==========================================" -ForegroundColor Green
    Write-Host "  OK: 安装成功！" -ForegroundColor Green
    Write-Host "==========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "使用方法:" -ForegroundColor Yellow
    Write-Host "1. 激活虚拟环境: .venv\Scripts\Activate.ps1" -ForegroundColor Gray
    Write-Host "2. 运行测试: python -m pytest" -ForegroundColor Gray
    Write-Host "3. 运行示例: python examples/00_quick_start.py" -ForegroundColor Gray
    Write-Host "4. 修改配置: 编辑 configs/.env" -ForegroundColor Gray
    Write-Host ""
    Write-Host "可选安装:" -ForegroundColor Yellow
    Write-Host "Qlib: pip install qlib" -ForegroundColor Gray
    Write-Host "vnpy: pip install ta-lib vnpy vnpy-ctp" -ForegroundColor Gray
    Write-Host "OpenBB: pip install openbb" -ForegroundColor Gray
} else {
    Write-Host ""
    Write-Host "==========================================" -ForegroundColor Red
    Write-Host "  ERROR: 安装失败，请检查错误信息" -ForegroundColor Red
    Write-Host "==========================================" -ForegroundColor Red
    exit 1
}