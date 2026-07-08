# 定时任务文档

> 生成日期：2026-07-06 | 最后更新：2026-07-07 | 适用场景：定时任务配置与管理

---

## 调度架构

### 调度引擎

系统使用 `APScheduler` 作为定时任务调度引擎：

```python
from apscheduler.schedulers.background import BackgroundScheduler
from scripts.daily_research import run_daily_research

scheduler = BackgroundScheduler()

# 添加每日研究任务
scheduler.add_job(
    run_daily_research,
    trigger="cron",
    hour=16,
    minute=0,
    id="daily_research",
    name="每日研究",
    args=[date.today(), False]
)

scheduler.start()
```

### 任务流程

```
数据更新 → 因子计算 → 信号生成 → 风控检查 → 日报生成 → 告警通知
```

---

## 定时任务配置

### 任务定义

| 任务名 | 执行时间 | 说明 |
|--------|---------|------|
| **update-data** | 15:30 | 更新当日行情数据 |
| **daily-research** | 16:00 | 执行每日研究流程 |
| **factor-eval** | 每周一 10:00 | 评估因子表现 |
| **backtest** | 每月初 | 运行月度回测 |
| **health-check** | 每日 08:00 | 健康检查 |

### 配置文件

```yaml
# configs/app.yaml
scheduler:
  enabled: true
  
  jobs:
    - name: update-data
      type: cron
      hour: 15
      minute: 30
      function: scripts.update_data.update_data
      args:
        universe: csi300
    
    - name: daily-research
      type: cron
      hour: 16
      minute: 0
      function: scripts.daily_research.run_daily_research
      args:
        use_llm: false
    
    - name: factor-eval
      type: cron
      day_of_week: mon
      hour: 10
      minute: 0
      function: scripts.factor_eval.run_factor_eval
      args:
        all: true
    
    - name: health-check
      type: cron
      hour: 8
      minute: 0
      function: scripts.health_check.run_health_check
```

---

## 任务管理

### 启动调度器

```bash
# 启动调度器
python -m scripts scheduler start

# 查看任务列表
python -m scripts scheduler list

# 手动触发任务
python -m scripts scheduler trigger daily-research

# 暂停任务
python -m scripts scheduler pause daily-research

# 恢复任务
python -m scripts scheduler resume daily-research

# 停止调度器
python -m scripts scheduler stop
```

### 任务状态

| 状态 | 说明 |
|------|------|
| **running** | 任务正在运行 |
| **paused** | 任务已暂停 |
| **waiting** | 任务等待执行 |
| **error** | 任务执行失败 |
| **completed** | 任务执行完成 |

---

## 每日研究流程

### 流程步骤

```python
def run_daily_research(target_date, use_llm=False):
    # 1. 更新数据
    logger.info("[1/5] 更新数据")
    update_data(universe="csi300")
    
    # 2. 计算因子
    logger.info("[2/5] 计算因子")
    compute_factors()
    
    # 3. 生成信号
    logger.info("[3/5] 生成信号")
    generate_signals()
    
    # 4. 风控检查
    logger.info("[4/5] 风控检查")
    risk_check()
    
    # 5. 生成日报
    logger.info("[5/5] 生成日报")
    generate_report(use_llm=use_llm)
    
    logger.info("每日研究完成")
```

### 流程配置

| 步骤 | 可配置项 | 默认值 |
|------|---------|--------|
| 数据更新 | universe | csi300 |
| 因子计算 | factors | all |
| 信号生成 | strategies | all |
| 风控检查 | strictness | normal |
| 日报生成 | use_llm | false |

---

## 错误处理

### 任务失败处理

```python
def run_with_retry(func, max_retries=3, delay=60):
    """带重试的任务执行"""
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            logger.error(f"任务执行失败 (尝试 {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(delay)
    
    logger.critical("任务执行失败，已达到最大重试次数")
    send_alert("TASK_FAILURE", f"任务失败: {func.__name__}")
```

### 错误类型

| 错误类型 | 处理方式 | 重试次数 |
|----------|---------|---------|
| **网络错误** | 等待后重试 | 3次 |
| **数据错误** | 记录日志，继续 | 0次 |
| **计算错误** | 记录日志，继续 | 0次 |
| **API错误** | 等待后重试 | 3次 |
| **系统错误** | 发送告警，停止 | 0次 |

---

## 日志与监控

### 任务日志

```bash
# 查看任务日志
tail -f logs/scheduler_$(date +%Y-%m-%d).log

# 搜索任务执行记录
grep "daily-research" logs/scheduler_*.log

# 统计任务执行时间
grep "duration" logs/scheduler_*.log
```

### 任务监控

```json
{
  "task": "daily-research",
  "last_run": "2026-07-02 16:00:00",
  "last_status": "success",
  "last_duration": "8m32s",
  "next_run": "2026-07-03 16:00:00",
  "run_count": 27,
  "success_count": 25,
  "failure_count": 2,
  "avg_duration": "7m45s"
}
```

---

## 部署方案

### Linux 部署

```bash
# 使用 systemd 服务
# /etc/systemd/system/quant-scheduler.service

[Unit]
Description=Quant System Scheduler
After=network.target

[Service]
Type=simple
User=quant
WorkingDirectory=/opt/quant-system/QuantAgent
ExecStart=/opt/quant-system/QuantAgent/.venv/bin/python -m scripts scheduler start
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
```

```bash
# 启动服务
systemctl daemon-reload
systemctl start quant-scheduler
systemctl enable quant-scheduler

# 查看状态
systemctl status quant-scheduler

# 查看日志
journalctl -u quant-scheduler -f
```

### crontab 部署（简化方案）

```bash
# crontab 定时任务（收盘后执行）
# 每个交易日 16:00 运行每日研究
0 16 * * 1-5 cd /home/edalab/Desktop/cme_code/quant-system/QuantAgent && .venv/bin/python -m scripts daily-research
```

---

## 最佳实践

### 1. 时间窗口

确保任务在收盘后执行（15:30后），避免使用未完成的数据。

### 2. 错误处理

所有任务都应包含错误处理和重试机制。

### 3. 日志记录

记录任务执行时间、状态和结果，便于问题追溯。

### 4. 监控告警

为关键任务配置告警，及时发现任务失败。

### 5. 资源管理

避免任务同时执行导致资源竞争。

---

## 参考

- [调度器源码](file:///home/edalab/Desktop/cme_code/quant-system/QuantAgent/scripts/scheduler.py)
- [每日研究](file:///home/edalab/Desktop/cme_code/quant-system/QuantAgent/scripts/daily_research.py)
- [数据更新](file:///home/edalab/Desktop/cme_code/quant-system/QuantAgent/scripts/update_data.py)
