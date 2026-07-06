# 命令行参考

> Quant System 命令行接口完整参考。

---

## 基础用法

```bash
python -m scripts <command> [options]
```

---

## 命令列表

### 1. update-data — 更新数据

**用途**：从 AKShare 下载股票日线数据、指数数据和基本面数据。

**语法**：
```bash
python -m scripts update-data [--universe <string>] [--tickers <string>] [--start <date>]
```

**参数**：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--universe` | string | csi300 | 股票池，可选值：csi300、csi500、all |
| `--tickers` | string | None | 逗号分隔的股票代码列表，如 "600519,300750" |
| `--start` | date | 2020-01-01 | 开始日期，格式 YYYY-MM-DD |

**示例**：

```bash
# 更新沪深300股票池数据（默认）
python -m scripts update-data

# 更新沪深500股票池数据，从2024年开始
python -m scripts update-data --universe csi500 --start 2024-01-01

# 更新单只股票数据
python -m scripts update-data --tickers 600519

# 更新多只股票数据
python -m scripts update-data --tickers 600519,300750,002475
```

**输出**：
```
[OK] 已更新 289 只股票的日线数据
[OK] 已更新 10 个指数的日线数据
[OK] 已更新基本面数据
```

---

### 2. daily-research — 运行每日研究

**用途**：执行完整的每日研究流程，包括数据更新、因子计算、策略信号生成、风控检查和日报生成。

**语法**：
```bash
python -m scripts daily-research [--date <date>] [--no-llm]
```

**参数**：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--date` | date | 今天 | 目标日期，格式 YYYY-MM-DD |
| `--no-llm` | flag | 无 | 不使用 LLM 生成报告 |

**示例**：

```bash
# 运行今日研究（使用LLM生成报告）
python -m scripts daily-research

# 运行今日研究（不使用LLM）
python -m scripts daily-research --no-llm

# 运行指定日期的研究
python -m scripts daily-research --date 2026-07-01
```

**输出**：
```
[OK] 数据更新完成
[OK] 因子计算完成
[OK] 策略信号生成完成
[OK] 风控检查通过
[OK] 日报已生成: knowledge/daily/2026-07-03.md
```

**研究流程**：
```
1. 更新当日数据 → 2. 计算因子 → 3. 生成策略信号 → 4. 风控检查 → 5. 生成日报
```

---

### 3. backtest — 运行回测

**用途**：使用指定策略回测单只或多只股票。

**语法**：
```bash
python -m scripts backtest [--strategy <string>] [--ticker <string>] [--start <date>] [--end <date>]
```

**参数**：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--strategy` | string | momentum | 策略名称 |
| `--ticker` | string | 600519 | 股票代码，支持逗号分隔多个 |
| `--start` | date | 2025-01-01 | 开始日期 |
| `--end` | date | None | 结束日期，默认为今天 |

**可用策略**：

| 策略名 | 说明 |
|--------|------|
| `momentum` | 动量策略 |
| `event_driven` | 事件驱动策略 |
| `sentiment` | 情绪策略 |
| `regime_switch` | 市场状态切换策略 |

**示例**：

```bash
# 默认回测（动量策略 + 贵州茅台）
python -m scripts backtest

# 指定策略和股票
python -m scripts backtest --strategy event_driven --ticker 300750

# 回测多只股票
python -m scripts backtest --strategy momentum --ticker 600519,300750

# 指定日期范围
python -m scripts backtest --strategy momentum --ticker 600519 --start 2024-01-01 --end 2024-12-31
```

**输出**：
```json
{
  "strategy": "momentum",
  "ticker": "600519",
  "total_return": 0.235,
  "sharpe_ratio": 1.28,
  "max_drawdown": -0.125,
  "win_rate": 0.58,
  "trades": 45
}
```

**回测指标说明**：

| 指标 | 说明 |
|------|------|
| `total_return` | 总收益率 |
| `sharpe_ratio` | 夏普比率（风险调整后收益） |
| `max_drawdown` | 最大回撤 |
| `win_rate` | 胜率（盈利交易数/总交易数） |
| `trades` | 交易次数 |

---

### 4. show-knowledge — 查看知识库

**用途**：查看知识库中的统计信息、日报、事件等内容。

**语法**：
```bash
python -m scripts show-knowledge [--type <string>] [--limit <int>] [--date <date>]
```

**参数**：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--type` | string | stats | 知识类型 |
| `--limit` | int | 10 | 返回数量限制 |
| `--date` | date | None | 指定日期 |

**知识类型**：

| 类型 | 说明 |
|------|------|
| `stats` | 知识库统计信息 |
| `daily` | 日报列表 |
| `weekly` | 周报列表 |
| `monthly` | 月报列表 |
| `events` | 事件列表 |
| `hypotheses` | 假设列表 |
| `failures` | 失败案例 |

**示例**：

```bash
# 查看知识库统计（默认）
python -m scripts show-knowledge

# 查看最近20篇日报
python -m scripts show-knowledge --type daily --limit 20

# 查看2026年7月的日报
python -m scripts show-knowledge --type daily --date 2026-07-01

# 查看事件库
python -m scripts show-knowledge --type events
```

**输出**：
```
知识库统计:
- 日报: 27 篇
- 周报: 5 篇
- 月报: 2 篇
- 事件: 0 条
- 假设: 15 条
- 失败案例: 3 条
```

---

### 5. batch_backtest — 批量策略回测

**用途**：对所有策略进行批量回测验证，结果写入数据库。

**语法**：
```bash
python -m scripts.batch_backtest [--strategy <name>] [--ticker <code>] [--limit <N>] [--output <file>]
```

**参数**：

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `--strategy` | string | 全部 | 策略名称：momentum/reversal/sentiment/regime_switch |
| `--ticker` | string | 20只 | 指定股票代码 |
| `--all-tickers` | flag | false | 回测全部标的 |
| `--limit` | int | 20 | 标的数量限制 |
| `--output` | string | 无 | 输出 JSON 文件路径 |

**示例**：
```bash
# 回测所有策略（默认 20 只股票）
python -m scripts.batch_backtest

# 回测单个策略
python -m scripts.batch_backtest --strategy momentum

# 输出 JSON
python -m scripts.batch_backtest --output results.json
```

### 6. evaluate_factors — 因子评估

**用途**：计算所有因子的 IC/ICIR/分组收益，写入 factor_evaluation 表。

```bash
python -m scripts.evaluate_factors
```

### 7. run_stress_test — 压力测试

**用途**：在 4 个历史危机场景下测试股票表现。

```bash
python -m scripts.run_stress_test --universe csi300
```

**场景**：2015 股灾 (-49%)、2018 熊市 (-32%)、2020 疫情 (-15%)、2024 流动性危机 (-11%)

### 8. run_brinson_attribution — Brinson 归因

**用途**：将超额收益分解为配置效应、选股效应和交互效应。

```bash
python -m scripts.run_brinson_attribution
```

### 9. health_check — 系统健康检查

**用途**：检查数据库连接、数据时效、因子覆盖、磁盘空间等。

```bash
python -m scripts.health_check            # 表格输出
python -m scripts.health_check --json     # JSON 输出
```

### 10. db_stats — 数据库统计

**用途**：查看所有表的行数统计。

```bash
python -m scripts.db_stats
```

### 11. scheduler — 定时调度器

**用途**：定时执行每日研究流程。

```bash
python -m scripts.scheduler              # 前台运行
python -m scripts.scheduler --dry-run     # 查看计划
python -m scripts.scheduler --run-now     # 立即执行一次
bash scripts/run_scheduler.sh             # 后台启动
bash scripts/stop_scheduler.sh            # 停止
```

### 12. test_p1 — P1 验证测试

**用途**：验证所有核心组件是否正常工作。

```bash
python -m scripts.test_p1
```

通过标准：10/10 全部通过。

### 13. MCP Server

**用途**：启动 MCP Server，暴露 32 个工具供外部 Agent 调用。

```bash
python -m mcp_server.server               # stdio 模式（默认）
python -m mcp_server.server --sse --port 8080  # SSE 模式
python -m mcp_server.server --list-tools   # 列出所有工具
```

---

## 快捷命令

### 验证环境
```bash
python examples/00_quick_start.py
```

### 运行测试
```bash
pytest tests/ -v
```

---

## 参数验证规则

回测命令 `backtest` 会进行以下参数验证：

| 验证项 | 规则 |
|--------|------|
| 策略名 | 不能为空，必须是已注册的策略 |
| 股票代码 | 不能为空，必须是有效的股票代码 |
| 日期格式 | 必须是 YYYY-MM-DD 格式 |
| 日期顺序 | 开始日期不能晚于结束日期 |
| 日期有效性 | 开始日期不能是未来日期 |

---

## 常见错误

### 参数错误
```log
Error: 策略名不能为空
Error: 开始日期不能晚于结束日期
```

### 数据错误
```log
Error: 未找到股票 600519 的数据
Error: 日期范围无数据
```

### 策略错误
```log
Error: 策略 xxx 未注册
```

---

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `OPENAI_API_KEY` | OpenAI API Key | 无 |
| `http_proxy` | HTTP 代理 | 无 |
| `https_proxy` | HTTPS 代理 | 无 |
| `NO_PROXY` | 跳过代理的域名 | 无 |

---

## 配置文件

命令行参数会读取以下配置文件：

| 文件 | 说明 |
|------|------|
| `configs/.env` | API Key 和环境变量 |
| `configs/app.yaml` | 应用配置 |

---

## 注意事项

1. **代理设置**：AKShare 连接国内服务器，通常不需要代理。如果设置了代理导致连接失败，取消代理即可。
2. **日期格式**：所有日期参数必须使用 `YYYY-MM-DD` 格式。
3. **多股票**：`--ticker` 参数支持逗号分隔多个股票代码，如 `600519,300750`。
4. **LLM 调用**：不带 `--no-llm` 参数时，会调用 OpenAI API 生成报告，需要配置 `OPENAI_API_KEY`。
