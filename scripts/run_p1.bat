@echo off
REM ==============================================================================
REM P1 任务运行脚本 - Windows版
REM 
REM 功能：运行完整的 P1 闭环验证流程
REM 包含：数据更新 → 因子计算 → 因子评估 → 压力测试 → Brinson归因 → 日报
REM 
REM 使用方式：
REM   scripts\run_p1.bat                  # 运行全部任务
REM   scripts\run_p1.bat --update-only    # 仅更新数据
REM   scripts\run_p1.bat --date 2026-07-06 # 指定日期
REM ==============================================================================

setlocal enabledelayedexpansion

set "PROJECT_DIR=%~dp0.."
cd /d "%PROJECT_DIR%"

REM ========================================
REM 参数解析
REM ========================================
set "TARGET_DATE="
set "UPDATE_ONLY=false"

:parse_args
if "%1"=="" goto end_parse
if "%1"=="--date" (
    set "TARGET_DATE=%2"
    shift
    shift
    goto parse_args
)
if "%1"=="--update-only" (
    set "UPDATE_ONLY=true"
    shift
    goto parse_args
)
echo 未知参数: %1
exit /b 1
:end_parse

REM ========================================
REM 环境配置
REM ========================================
echo ==============================================
echo   P1 任务运行脚本
echo   项目目录: %PROJECT_DIR%
echo ==============================================

REM 清除代理（国内数据源）
set http_proxy=
set https_proxy=
set HTTP_PROXY=
set HTTPS_PROXY=

REM ========================================
REM 数据更新（国内数据源直连，不走代理）
REM ========================================
echo.
echo ==============================================
echo [1/6] 数据更新 (国内直连)
echo ==============================================

if defined TARGET_DATE (
    echo 日期: %TARGET_DATE%
    python -m scripts.update_data --all --date "%TARGET_DATE%"
) else (
    python -m scripts.update_data --all
)

if errorlevel 1 (
    echo ❌ 数据更新失败
    exit /b 1
)

REM ========================================
REM 因子批量计算
REM ========================================
if "%UPDATE_ONLY%"=="false" (
    echo.
    echo ==============================================
    echo [2/6] 因子批量计算
    echo ==============================================
    python -m scripts.compute_factors --universe csi300

    if errorlevel 1 (
        echo ❌ 因子计算失败
        exit /b 1
    )

    REM ========================================
    REM 因子评估 + 衰减检测
    REM ========================================
    echo.
    echo ==============================================
    echo [3/6] 因子评估 + 衰减检测
    echo ==============================================
    python -m scripts.evaluate_factors --all

    if errorlevel 1 (
        echo ❌ 因子评估失败
        exit /b 1
    )

    REM ========================================
    REM 压力测试
    REM ========================================
    echo.
    echo ==============================================
    echo [4/6] 压力测试
    echo ==============================================
    python -m scripts.run_stress_test --scenarios all

    if errorlevel 1 (
        echo ❌ 压力测试失败
        exit /b 1
    )

    REM ========================================
    REM Brinson 归因
    REM ========================================
    echo.
    echo ==============================================
    echo [5/6] Brinson 归因
    echo ==============================================
    python -m scripts.run_attribution

    if errorlevel 1 (
        echo ❌ Brinson归因失败
        exit /b 1
    )

    REM ========================================
    REM Daily Research（完整流程）
    REM ========================================
    echo.
    echo ==============================================
    echo [6/6] Daily Research（完整流程）
    echo ==============================================
    if defined TARGET_DATE (
        python -m scripts.daily_research --date "%TARGET_DATE%"
    ) else (
        python -m scripts.daily_research
    )

    if errorlevel 1 (
        echo ❌ Daily Research失败
        exit /b 1
    )
)

REM ========================================
REM 最终验证
REM ========================================
echo.
echo ==============================================
echo [验证] 数据库统计
echo ==============================================
python -m scripts.db_stats

if errorlevel 1 (
    echo ❌ 数据库统计失败
    exit /b 1
)

echo.
echo ==============================================
echo ✅ P1 任务完成!
echo ==============================================

endlocal