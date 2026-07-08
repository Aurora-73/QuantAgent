# 回测工作流

---
name: backtest-workflow
description: 策略回测标准流程，从选择策略到对比回测结果
requires_mcp: [list_strategies, get_strategy_config, run_backtest, compare_backtest_runs]
---

## 步骤 1：列出可用策略

调用 `list_strategies()` 获取已注册的策略列表。

**输出**：策略名称和描述，如 momentum（动量突破）、event_driven（事件驱动）等。

---

## 步骤 2：获取策略配置

调用 `get_strategy_config(strategy_name)` 查看策略参数。

**示例**：
```
get_strategy_config("momentum")
```

**输出解读**：包含策略的参数列表和默认值（如 lookback 周期、entry_threshold 阈值等）。

---

## 步骤 3：运行回测

调用 `run_backtest(strategy, ticker, date_start, date_end)` 执行回测。

**示例**：
```
run_backtest(strategy="momentum", ticker="600519", date_start="2024-01-01", date_end="2025-12-31")
```

**关键参数**：
- `strategy`：策略名称（从 `list_strategies` 获取）
- `ticker`：股票代码（单个或逗号分隔多个）
- `date_start`/`date_end`：回测时间段

**注意**：这是写操作，结果会存入 `backtest_runs` 表。

---

## 步骤 4：对比回测结果

调用 `compare_backtest_runs()` 查看最近多次回测的对比结果。

**输出解读**：关注 `total_return`（总收益）、`sharpe_ratio`（夏普比率）、`max_drawdown`（最大回撤）。

---

## 完整工作流

```
1. list_strategies() → 选择策略
2. get_strategy_config("momentum") → 查看参数
3. run_backtest(strategy="momentum", ticker="600519", date_start="2024-01-01", date_end="2025-12-31") → 运行回测
4. compare_backtest_runs() → 对比结果
```

---

## 常见问题

**Q**: 如何选择回测时间段？
**A**: 建议至少包含一个完整牛熊市周期（2-3年），样本外验证用最近6个月。

**Q**: 回测结果太好（夏普>3）怎么办？
**A**: 检查是否有未来数据泄露（look-ahead bias），缩短回测周期验证稳定性。

**Q**: 多只股票如何回测？
**A**: 用逗号分隔多个股票代码，或分批回测后用 `compare_backtest_runs()` 对比。
