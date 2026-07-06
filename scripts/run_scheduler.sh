#!/bin/bash
# scheduler 后台启动脚本
# 使用方式: bash scripts/run_scheduler.sh

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

mkdir -p logs

if [ -f logs/scheduler.pid ] && kill -0 "$(cat logs/scheduler.pid)" 2>/dev/null; then
    echo "scheduler 已在运行中, PID: $(cat logs/scheduler.pid)"
    exit 1
fi

source .venv/bin/activate
nohup python -m scripts.scheduler > logs/scheduler.log 2>&1 &
echo $! > logs/scheduler.pid
echo "scheduler 已启动, PID: $(cat logs/scheduler.pid)"
echo "日志: logs/scheduler.log"
echo "查看: tail -f logs/scheduler.log"
