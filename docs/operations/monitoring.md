# 监控指南

> 生成日期：2026-07-06 | 最后更新：2026-07-07 | 适用场景：监控与告警体系

---

## 监控架构

### 监控层次

```
基础设施层 → 数据层 → 业务层 → 应用层
     ↓          ↓          ↓          ↓
  CPU/内存    数据质量    策略绩效    系统状态
```

### 监控引擎

```python
from monitoring.metrics import MetricsEngine
from monitoring.alerts import AlertManager

metrics = MetricsEngine()
alerts = AlertManager()

# 收集指标
metrics.collect()

# 检查告警
alert_list = alerts.check()
```

---

## 核心监控指标

### 基础设施指标

| 指标 | 说明 | 阈值 |
|------|------|------|
| **CPU使用率** | 系统CPU占用 | >80% 警告 |
| **内存使用率** | 系统内存占用 | >85% 警告 |
| **磁盘使用率** | 磁盘空间占用 | >90% 警告 |
| **网络延迟** | 网络响应时间 | >500ms 警告 |

### 数据层指标

| 指标 | 说明 | 阈值 |
|------|------|------|
| **数据新鲜度** | 最新数据日期 | >2天 警告 |
| **因子覆盖率** | 因子值非NaN比例 | <90% 警告 |
| **数据完整性** | 数据记录数 | <预期 警告 |
| **数据库大小** | DuckDB文件大小 | >10GB 警告 |

### 业务层指标

| 指标 | 说明 | 阈值 |
|------|------|------|
| **策略收益** | 累计收益率 | <基准 警告 |
| **最大回撤** | 从高点到低点的跌幅 | >-15% 警告 |
| **夏普比率** | 风险调整后收益 | <0.5 警告 |
| **胜率** | 盈利交易比例 | <50% 警告 |
| **换手率** | 日均换手率 | >20% 警告 |
| **因子IC** | 信息系数 | <0.03 警告 |

### 应用层指标

| 指标 | 说明 | 阈值 |
|------|------|------|
| **每日研究耗时** | daily-research执行时间 | >30分钟 警告 |
| **数据更新耗时** | update-data执行时间 | >10分钟 警告 |
| **API调用成功率** | LLM API调用成功比例 | <90% 警告 |
| **告警确认率** | 告警被确认的比例 | <80% 警告 |

---

## 告警管理

### 告警级别

| 级别 | 说明 | 处理方式 |
|------|------|---------|
| **INFO** | 信息通知 | 记录日志 |
| **WARNING** | 警告信息 | 发送通知 |
| **CRITICAL** | 严重问题 | 发送通知 + 触发熔断 |

### 告警类型

| 类型 | 说明 | 级别 |
|------|------|------|
| **DATA_STALE** | 数据过时 | WARNING |
| **FACTOR_COVERAGE** | 因子覆盖率低 | WARNING |
| **DRAWDOWN_BREACH** | 回撤超限 | CRITICAL |
| **DAILY_LOSS** | 日亏损超限 | CRITICAL |
| **VOLATILITY_SPIKE** | 波动率突增 | WARNING |
| **API_FAILURE** | API调用失败 | WARNING |
| **SYSTEM_RESOURCE** | 系统资源不足 | WARNING |
| **STRATEGY_DECAY** | 策略衰减 | WARNING |

### 告警渠道

| 渠道 | 说明 | 配置 |
|------|------|------|
| **ServerChan** | 微信推送 | 需要配置SENDCHAN_SENDKEY |
| **日志文件** | 本地日志 | 默认开启 |
| **控制台** | 终端输出 | 默认开启 |

### 告警配置

```yaml
# configs/app.yaml
alerts:
  serverchan:
    enabled: true
    sendkey: "your_sendkey"
  
  thresholds:
    drawdown: -0.05
    daily_loss: -0.02
    factor_coverage: 0.90
    data_stale_days: 2
  
  silence:
    - type: VOLATILITY_SPIKE
      duration: 30  # 静默30分钟
```

---

## 日志系统

### 日志级别

| 级别 | 说明 | 使用场景 |
|------|------|---------|
| **DEBUG** | 详细调试信息 | 开发阶段 |
| **INFO** | 普通信息 | 运行状态 |
| **WARNING** | 警告信息 | 潜在问题 |
| **ERROR** | 错误信息 | 错误发生 |
| **CRITICAL** | 严重错误 | 系统崩溃 |

### 日志配置

```python
from loguru import logger

# 配置日志
logger.remove()
logger.add(
    "logs/app_{time:YYYY-MM-DD}.log",
    rotation="00:00",
    retention="30 days",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
)

# 使用日志
logger.info("每日研究开始")
logger.warning("因子覆盖率低于阈值")
logger.error("数据更新失败")
logger.critical("系统熔断触发")
```

### 日志分析

```bash
# 查看今日日志
tail -f logs/app_$(date +%Y-%m-%d).log

# 搜索错误
grep "ERROR" logs/app_*.log

# 搜索告警
grep "CRITICAL" logs/app_*.log

# 统计错误次数
grep -c "ERROR" logs/app_*.log
```

---

## 健康检查

### 执行命令

```bash
python -m scripts health_check
```

### 检查内容

| 检查项 | 说明 | 预期结果 |
|--------|------|---------|
| **数据库连接** | DuckDB连接是否正常 | ✅ |
| **数据时效** | 最新数据日期 | ✅ 今天 |
| **数据完整性** | 股票数量 | ✅ 数量以 db_stats 为准 |
| **因子覆盖** | 因子注册数量 | ✅ 29个 |
| **数据源** | AKShare连接 | ✅ |
| **回测持久化** | 回测表是否就绪 | ✅ |

### 检查结果

```json
{
  "status": "healthy",
  "checks": [
    {"name": "database", "status": "pass", "detail": "DuckDB连接正常"},
    {"name": "data_freshness", "status": "pass", "detail": "最新数据2026-07-02"},
    {"name": "data_completeness", "status": "pass", "detail": "股票数量以 db_stats 为准"},
    {"name": "factor_coverage", "status": "pass", "detail": "29个因子"},
    {"name": "data_source", "status": "pass", "detail": "AKShare正常"},
    {"name": "backtest_persistence", "status": "pass", "detail": "表就绪"}
  ]
}
```

---

## 性能监控

### 性能指标

| 指标 | 说明 | 目标值 |
|------|------|--------|
| **每日研究耗时** | daily-research执行时间 | <15分钟 |
| **因子计算耗时** | 29个因子计算时间 | <5分钟 |
| **数据更新耗时** | update-data执行时间 | <5分钟 |
| **回测耗时** | 单股票回测时间 | <1分钟 |
| **API响应时间** | MCP工具调用时间 | <3秒 |

### 性能优化

```python
# 使用多进程加速因子计算
from concurrent.futures import ProcessPoolExecutor

def compute_factor(factor_name, df):
    engine = FactorEngine()
    return engine.compute(df, [factor_name])

with ProcessPoolExecutor() as executor:
    results = executor.map(compute_factor, factor_names, [df] * len(factor_names))
```

---

## 仪表盘

### 实时仪表盘

```
┌─────────────────────────────────────────────────────────────┐
│                    Quant System Dashboard                   │
├─────────────────────────────────────────────────────────────┤
│  [OK] 系统状态: healthy                                     │
│  [OK] 数据日期: 2026-07-02                                  │
│  [OK] 股票数量: (见 db_stats)                               │
│  [OK] 因子数量: 29                                          │
├─────────────────────────────────────────────────────────────┤
│  策略绩效                                                   │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 总收益: 15.2% | 夏普: 1.3 | 回撤: -8.5%          │    │
│  └─────────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────────┤
│  最近告警                                                   │
│  - [WARNING] 波动率突增 (2026-07-02 14:30)                 │
└─────────────────────────────────────────────────────────────┘
```

### 历史趋势

```
收益趋势 (最近30天)
  20% │        ╭───────────╮
  15% │    ╭───╯           ╰───╮
  10% │  ╭─╯                    ╰───╮
   5% │╭─╯                           ╰─
   0% ╰─────────────────────────────────────→
       6/2  6/7  6/12  6/17  6/22  6/27  7/2
```

---

## 最佳实践

### 1. 定期健康检查

每天运行健康检查，确保系统状态正常。

### 2. 告警分级

根据严重程度分级处理告警，避免告警疲劳。

### 3. 日志保留

保留至少30天的日志，便于问题追溯。

### 4. 性能监控

定期检查性能指标，及时发现性能瓶颈。

### 5. 告警确认

及时确认告警，避免遗漏重要问题。

---

## 参考

- [指标引擎](file:///home/edalab/Desktop/cme_code/quant-system/QuantAgent/monitoring/metrics.py)
- [告警管理](file:///home/edalab/Desktop/cme_code/quant-system/QuantAgent/monitoring/alerts.py)
- [健康检查](file:///home/edalab/Desktop/cme_code/quant-system/QuantAgent/scripts/health_check.py)
