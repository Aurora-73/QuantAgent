#!/bin/bash
# scheduler 停止脚本
# 使用方式: bash scripts/stop_scheduler.sh

PID_FILE="logs/scheduler.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "scheduler 未运行 (PID 文件不存在)"
    exit 0
fi

PID=$(cat "$PID_FILE")
if kill -0 "$PID" 2>/dev/null; then
    echo "正在停止 scheduler (PID: $PID)..."
    kill "$PID"
    sleep 2
    if kill -0 "$PID" 2>/dev/null; then
        echo "强制终止..."
        kill -9 "$PID" 2>/dev/null
    fi
    echo "scheduler 已停止"
else
    echo "scheduler 未运行 (PID $PID 不存在)"
fi

rm -f "$PID_FILE"
