# Phase 2 实施计划

> 生成日期：2026-07-06 | 最后更新：2026-07-06
> 基线版本：P1 已验证通过（组件测试通过，全流程可运行）
> 前置条件：数据/因子/事件已入库（行数以 db_stats 为准）、4 策略全部注册

---

## 一、总览

### 1.1 目标

从"可运行"推进到"自动化 + 可验证"：

1. **数据源稳定** — baostock 替换 AKShare 间歇性失败
2. **定时自动化** — scheduler.py 跑通，日终自动研究
3. **策略可验证** — 4 个策略样本外回测，结果入库
4. **MCP 可写** — 外部 Agent 能通过 MCP 触发回测和改配置
5. **Walk-Forward CLI** — 参数扫描命令行接入

### 1.2 当前基线（P1 验收后快照，行数以 `python -m scripts.db_stats` 实时输出为准）

| 指标 | 说明 |
|------|------|
| stock_daily | 日线数据（行数以 db_stats 为准） |
| factors | 因子值（注册 29 个，实际计算数以 db_stats 为准） |
| index_daily | 指数日线数据 |
| events | 结构化新闻事件 |
| decision_memory | 决策记忆 |
| backtest_runs | 回测记录（4 策略 × 多标的） |
| 单元测试 | 全部通过（以 `pytest tests/` 输出为准） |
| 健康检查 | 通过（以 `python -m scripts.health_check` 输出为准） |

### 1.3 依赖关系

```
baostock 数据源 ──→ scheduler 定时调度 ──→ 自动日报
      │                                       │
      └──→ 策略回测验证 ←── MCP 写工具 ←─────┘
              │
              └──→ Walk-Forward CLI
```

---

## 二、任务详情

---

### 任务 P2.1：安装 baostock 稳定数据源

**目的**：解决 AKShare 直连 eastmoney.com 间歇性失败（RemoteDisconnected），建立稳定的主力数据源。

**背景**：当前 baostock 未安装，所有数据通过 AKShare 获取。AKShare 连接 eastmoney.com 时有偶发 TCP 断连。

**实施步骤**：

```bash
# Step 1: 安装 baostock
pip install baostock

# Step 2: 验证连接
python -c "
import baostock as bs
lg = bs.login()
print(f'login: {lg.error_code} {lg.error_msg}')
rs = bs.query_stock_basic()
print(f'query: {rs.error_code} {rs.error_msg}')
bs.logout()
"

# Step 3: 对比 baostock vs AKShare 数据一致性
python -m scripts.test_data_sources

# Step 4: 更新数据确认 baostock 生效
python -m scripts.update_data
```

**验证标准**：
- [ ] `pip install baostock` 成功
- [ ] `bs.login()` 返回 error_code=0
- [ ] `test_data_sources.py` 通过（数据一致性检查）
- [ ] 数据更新后 stock_daily 行数增长

**预计耗时**：15 分钟

---

### 任务 P2.2：定时调度器跑通

**目的**：设置 scheduler.py 每日收盘后自动执行数据更新 + 因子计算 + 日报生成。

**背景**：scheduler.py 已实现（137 行），但有 3 个问题：
1. `configs/settings.py` 中缺少 `schedule_*` 配置项（当前走默认值）
2. `monitoring/alerts.py` 的 `_send_notification` 是空函数 `pass`
3. 从未实际跑通过

**实施步骤**：

#### Step 1：补齐配置项

编辑 `configs/settings.py`，新增：

```python
# 调度配置
schedule_research_time: str = "16:00"
schedule_data_update_time: str = "15:30"
schedule_enabled: bool = False
```

#### Step 2：对接告警通知

编辑 `monitoring/alerts.py` 的 `_send_notification`：

```python
def _send_notification(self, alert):
    """对接 SendChanNotifier 发送告警"""
    from monitoring.notifier import MultiUserNotifier
    try:
        notifier = MultiUserNotifier()
        notifier.broadcast(f"[{alert.level.value}] {alert.category}", alert.message)
    except Exception as e:
        logger.warning(f"告警通知发送失败: {e}")
```

#### Step 3：创建 nohup 启动脚本

编辑 `scripts/run_scheduler.sh`：

```bash
#!/bin/bash
# scheduler 后台启动脚本
source .venv/bin/activate
nohup python -m scripts.scheduler > logs/scheduler.log 2>&1 &
echo $! > logs/scheduler.pid
echo "scheduler started, PID: $(cat logs/scheduler.pid)"
```

#### Step 4：验证调度器

```bash
# 测试模式
python -m scripts.scheduler --dry-run

# 立即运行一次
python -m scripts.scheduler --run-now

# 后台启动
bash scripts/run_scheduler.sh
```

**验证标准**：
- [ ] `scheduler.py --dry-run` 显示正确的日程表
- [ ] `scheduler.py --run-now` 成功完成一次研究流程
- [ ] 告警通知能正常发送到 SendChan
- [ ] scheduler 后台进程稳定运行 24h+

**预计耗时**：2 小时

---

### 任务 P2.3：4 策略样本外回测验证

**目的**：验证 4 个已注册策略的样本外表现，结果入库以便 MCP 工具查询。

**背景**：策略全部实现但未做系统的样本外回测验证。当前 `backtest_runs` 表有 32 条记录，但多为单标的单策略测试。

**实施步骤**：

#### Step 1：创建批量回测脚本

在 `scripts/batch_backtest.py` 中实现：

```python
"""
批量策略回测脚本

用法：
    python -m scripts.batch_backtest                          # 回测所有策略所有标的
    python -m scripts.batch_backtest --strategy momentum      # 指定策略
    python -m scripts.batch_backtest --ticker 600519          # 指定标的
    python -m scripts.batch_backtest --compare                # 对比买入持有

输出：
    - 写入 backtest_runs + backtest_equity 表
    - 可选输出 JSON 到文件
"""
```

#### Step 2：回测参数

| 策略 | 参数范围 | 数据区间 |
|------|---------|---------|
| momentum | lookback=[10,20,30], threshold=[0.03,0.05,0.08] | 2020-2024 train, 2025-2026 test |
| event_driven | decay=[3,5,10], confidence_threshold=[0.3,0.5,0.7] | 同上 |
| sentiment | sentiment_threshold=[0.3,0.5,0.7], lookback=[5,10,20] | 同上 |
| regime_switch | switching_threshold=[0.5,0.7], cooldown=[3,5,10] | 同上 |

#### Step 3：结果入库

每个回测记录包含：
```json
{
  "strategy": "momentum",
  "ticker": "600519",
  "params": {"lookback": 20, "threshold": 0.05},
  "train_period": "2020-01-01~2024-12-31",
  "test_period": "2025-01-01~2026-07-06",
  "total_return": 0.15,
  "sharpe_ratio": 0.8,
  "max_drawdown": -0.12,
  "win_rate": 0.55,
  "trade_count": 45
}
```

#### Step 4：对比分析

```bash
python -m scripts.batch_backtest --compare --output results.json
```

输出包含：
- 各策略 vs 买入持有对比
- 收益/夏普/回撤/胜率 4 维排名
- 最佳参数组合

**验证标准**：
- [ ] 4 个策略均完成 300 只股票的样本外回测
- [ ] 结果正确写入 backtest_runs + backtest_equity 表
- [ ] `--compare` 输出有效对比数据
- [ ] `--output json` 输出有效 JSON

**预计耗时**：3-4 小时（全量 300 只）

---

### 任务 P2.4：MCP 写工具

**目的**：给 MCP Server 添加写操作工具，让外部 Agent 能触发回测和修改配置。

**背景**：MCP 工具中大部分为只读（`readOnlyHint: True`）。外部 Agent 只能查看数据，不能执行操作。

**实施步骤**：

#### Step 1：添加 run_backtest 工具

在 `mcp_server/tools_risk.py` 中新增：

```python
# 移除 readOnlyHint，允许 Agent 触发回测
mcp.tool(
    name="run_backtest",
    description="运行策略回测，结果写入数据库",
)(tools_risk.run_backtest)
```

#### Step 2：添加 update_data 工具

在 `mcp_server/tools_data.py` 中新增：

```python
mcp.tool(
    name="update_data",
    description="更新指定股票池的行情数据",
)(tools_data.update_data)
```

#### Step 3：添加 run_daily_research 工具

```python
mcp.tool(
    name="run_daily_research",
    description="触发一次完整的每日研究流程",
)(tools_data.run_daily_research)
```

#### Step 4：权限控制

写操作工具需要确认机制：

```python
def run_backtest(strategy: str, ticker: str, **kwargs) -> dict:
    """触发回测。注意：此操作会写入数据库并消耗计算资源。"""
    logger.warning(f"MCP 写操作: run_backtest(strategy={strategy}, ticker={ticker})")
    # ... 执行逻辑
```

**验证标准**：
- [ ] Agent 能通过 MCP 调用 `run_backtest` 触发回测
- [ ] Agent 能通过 MCP 调用 `update_data` 更新数据
- [ ] 写操作日志正确记录
- [ ] 权限控制生效

**预计耗时**：2 小时

---

### 任务 P2.5：Walk-Forward CLI

**目的**：将 Walk-Forward 引擎接入命令行，支持参数扫描和结果输出。

**背景**：`research/walk_forward.py` 已实现（221 行），但只有 Python API，没有命令行入口。

**实施步骤**：

#### Step 1：创建 CLI 入口

在 `scripts/__main__.py` 中新增子命令：

```python
# walkforward 子命令
wf_parser = subparsers.add_parser("walkforward", help="Walk-Forward 优化")
wf_parser.add_argument("--strategy", default="momentum")
wf_parser.add_argument("--ticker", default="600519")
wf_parser.add_argument("--train-window", type=int, default=252)
wf_parser.add_argument("--test-window", type=int, default=63)
wf_parser.add_argument("--step", type=int, default=63)
wf_parser.add_argument("--param-scan", action="store_true")
wf_parser.add_argument("--output", default=None)
```

#### Step 2：实现参数扫描

```bash
python -m scripts walkforward \
  --strategy momentum \
  --ticker 600519 \
  --param-scan \
  --output results.json
```

输出格式：
```json
{
  "best_params": {"lookback": 20, "threshold": 0.05},
  "periods": [
    {"train": "2020-01~2021-01", "test": "2021-01~2021-03", "sharpe": 1.2},
    ...
  ],
  "avg_sharpe": 0.85,
  "avg_return": 0.12,
  "stability": 0.7
}
```

#### Step 3：结果可视化

```bash
python -m scripts walkforward --strategy momentum --param-scan --output chart.png
```

生成 equity_curve 对比图（各窗口叠加）。

**验证标准**：
- [ ] `walkforward` CLI 命令可用
- [ ] 参数扫描返回有效结果
- [ ] `--output json` 输出正确格式
- [ ] 结果可复现（相同参数运行两次结果一致）

**预计耗时**：3 小时

---

## 三、验收标准总表

### P2 验收清单

- [ ] P2.1: baostock 安装并验证通过
- [ ] P2.1: 数据一致性检查通过
- [ ] P2.2: scheduler --dry-run 输出正确
- [ ] P2.2: scheduler --run-now 完成一次研究流程
- [ ] P2.2: 告警对接 SendChan 成功
- [ ] P2.2: scheduler 后台守护进程稳定运行
- [ ] P2.3: 4 策略批量回测脚本可用
- [ ] P2.3: 结果写入 backtest_runs 表
- [ ] P2.3: --compare 输出有效对比
- [ ] P2.4: MCP run_backtest 工具可用
- [ ] P2.4: MCP update_data 工具可用
- [ ] P2.4: 写操作日志记录正常
- [ ] P2.5: walkforward CLI 命令可用
- [ ] P2.5: 参数扫描输出有效
- [ ] P2.5: --output json 格式正确
- [ ] **整体**：健康检查 8 pass, 0 warn, 0 fail

---

## 四、时间估算

| 任务 | 估计耗时 | 并行？ |
|------|---------|--------|
| P2.1 baostock 安装 | 15 分钟 | 可并行 |
| P2.2 scheduler 跑通 | 2 小时 | 依赖 P2.1 |
| P2.3 批量回测 | 3-4 小时 | 可并行 |
| P2.4 MCP 写工具 | 2 小时 | 可独立 |
| P2.5 Walk-Forward CLI | 3 小时 | 依赖 P2.1 |
| **总计** | **~10 小时** | |

---

## 五、风险

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|---------|
| baostock 服务器不可达 | 低 | 高（数据源切换失败） | 保留 AKShare 降级路径 |
| scheduler 长时间运行 OOM | 低 | 中 | 设置 max_turn_time 限制 |
| 批量回测耗时过长 | 中 | 中 | 支持分批运行 --limit |
| MCP 写操作误触 | 低 | 高 | 日志审计 + 确认机制 |
