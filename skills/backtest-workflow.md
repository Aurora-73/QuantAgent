---
name: backtest-workflow
description: 策略回测标准流程，从选择策略到对比回测结果
requires_mcp: [list_strategies, get_strategy_config, run_backtest, compare_backtest_runs]
workflow:
  - step: 1
    name: 列出可用策略
    mcp: list_strategies
    next: 获取策略配置(get_strategy_config)
  - step: 2
    name: 获取策略配置
    mcp: get_strategy_config
    next: 运行回测(run_backtest)
  - step: 3
    name: 运行回测
    mcp: run_backtest
    next: 对比回测结果(compare_backtest_runs)
  - step: 4
    name: 对比回测结果
    mcp: compare_backtest_runs
    next: 完成
---
# 回测工作流



## 🔄 工作流总览

```
list_strategies → get_strategy_config → run_backtest → compare_backtest_runs
    (步骤1)           (步骤2)             (步骤3)            (步骤4)
```

---

## 📋 步骤 1：列出可用策略

**目的**：了解系统支持的策略，选择适合的回测策略

**MCP 工具**：`list_strategies()`

**示例调用**：
```
list_strategies()
```

**输出解读**：
- 策略名称和描述
- 策略类别（技术面、事件驱动、情绪等）
- 常用策略：momentum（动量突破）、event_driven（事件驱动）、sentiment（情绪策略）

**下一步指引**：
- ✅ 获取到策略列表：继续步骤2 → 调用 `get_strategy_config(策略名称)`

---

## ⚙️ 步骤 2：获取策略配置

**目的**：查看策略参数，确认回测配置

**MCP 工具**：`get_strategy_config(strategy_name)`

**示例调用**：
```
get_strategy_config("momentum")
```

**输出解读**：
- 参数列表和默认值
- `lookback`：回溯周期
- `entry_threshold`：入场阈值
- `exit_threshold`：出场阈值

**下一步指引**：
- ✅ 获取到配置：继续步骤3 → 调用 `run_backtest(strategy, ticker, date_start, date_end)`
- ❌ 策略不存在：返回步骤1，重新选择策略

---

## 🚀 步骤 3：运行回测

**目的**：执行策略回测，获取绩效指标

**MCP 工具**：`run_backtest(strategy, ticker, date_start, date_end, dry_run=False)`

**参数说明**：
- `strategy`：策略名称（从 `list_strategies` 获取）
- `ticker`：股票代码（单个或逗号分隔多个）
- `date_start`/`date_end`：回测时间段
- `dry_run`：预览模式，不执行实际写操作

**注意**：这是写操作，结果会存入 `backtest_runs` 表。

**示例调用**：
```
run_backtest(strategy="momentum", ticker="600519", date_start="2024-01-01", date_end="2025-12-31")
```

**下一步指引**：
- ✅ 回测成功：继续步骤4 → 调用 `compare_backtest_runs()`
- ❌ 回测失败：检查股票代码是否正确，或调用 `get_history(ticker)` 确认数据是否存在

---

## 📊 步骤 4：对比回测结果

**目的**：分析回测绩效，对比多次回测结果

**MCP 工具**：`compare_backtest_runs()`

**示例调用**：
```
compare_backtest_runs()
```

**输出解读**：
- `total_return`：总收益
- `sharpe_ratio`：夏普比率（>1.0 为优秀）
- `max_drawdown`：最大回撤（<20% 为优秀）
- `win_rate`：胜率

**下一步指引**：
- ✅ 完成：回测流程结束，根据绩效指标评估策略有效性

---

## 📈 完整工作流示例

```
# 第1步：列出可用策略
result1 = list_strategies()
# → 返回: ["momentum", "event_driven", "sentiment", "regime_switch"]

# 第2步：获取策略配置
result2 = get_strategy_config("momentum")
# → 返回: {"lookback": 20, "entry_threshold": 0.02, ...}

# 第3步：运行回测
result3 = run_backtest(strategy="momentum", ticker="600519", date_start="2024-01-01", date_end="2025-12-31")
# → 返回: {"total_return": 0.35, "sharpe_ratio": 1.8, "max_drawdown": 0.15}

# 第4步：对比回测结果
result4 = compare_backtest_runs()
# → 返回: 多次回测对比表

# 输出：策略评估报告
```

---

## ❓ 常见问题

**Q**: 如何选择回测时间段？
**A**: 建议至少包含一个完整牛熊市周期（2-3年），样本外验证用最近6个月。

**Q**: 回测结果太好（夏普>3）怎么办？
**A**: 检查是否有未来数据泄露（look-ahead bias），缩短回测周期验证稳定性。

**Q**: 多只股票如何回测？
**A**: 用逗号分隔多个股票代码，或分批回测后用 `compare_backtest_runs()` 对比。
