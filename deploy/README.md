# 部署指南：systemd 定时数据更新

## 安装步骤

### 1. 复制 unit 文件到 systemd 目录

```bash
# 用户级 service（无需 sudo）
mkdir -p ~/.config/systemd/user
cp deploy/quantagent-scheduler.service ~/.config/systemd/user/
cp deploy/quantagent-scheduler.timer ~/.config/systemd/user/
```

### 2. 重新加载 systemd

```bash
systemctl --user daemon-reload
```

### 3. 启用并启动 timer

```bash
systemctl --user enable quantagent-scheduler.timer
systemctl --user start quantagent-scheduler.timer
```

### 4. 验证

```bash
# 查看 timer 状态
systemctl --user status quantagent-scheduler.timer

# 查看下次触发时间
systemctl --user list-timers quantagent-scheduler.timer

# 手动触发一次（测试）
systemctl --user start quantagent-scheduler.service

# 查看日志
journalctl --user -u quantagent-scheduler.service -f
```

## 运行机制

- **触发时间**：周一至周五 15:30（systemd timer）
- **交易日检查**：脚本内部用 `TradingCalendar` 检查，非交易日自动跳过
- **增量更新**：只拉取 `max(date)+1` 到今天的缺失数据
- **失败告警**：通过 `AlertManager` → `SendChanNotifier` 推送 Server酱通知
- **成功通知**：推送任务完成通知

## 手动操作

```bash
# 手动运行（强制，忽略非交易日）
python -m scripts.run_scheduled_update --force

# 预览模式
python -m scripts.run_scheduled_update --dry-run

# 停止 timer
systemctl --user stop quantagent-scheduler.timer

# 禁用 timer
systemctl --user disable quantagent-scheduler.timer
```

## 回滚

```bash
systemctl --user stop quantagent-scheduler.timer
systemctl --user disable quantagent-scheduler.timer
rm ~/.config/systemd/user/quantagent-scheduler.{service,timer}
systemctl --user daemon-reload
```
