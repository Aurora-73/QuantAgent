# 每日研究工作流

---
name: daily-workflow
description: 每日收盘后的标准研究流程，从数据更新到日报生成
requires_mcp: [update_data, run_daily_research, get_daily_report, get_market_overview, run_health_check]
workflow:
  - step: 1
    name: 更新行情数据
    mcp: update_data
    next: 运行每日研究(run_daily_research)
  - step: 2
    name: 运行每日研究
    mcp: run_daily_research
    next: 获取日报(get_daily_report)
  - step: 3
    name: 获取日报
    mcp: get_daily_report
    next: 获取市场概况(get_market_overview)
  - step: 4
    name: 获取市场概况
    mcp: get_market_overview
    next: 完成
---

## 🔄 工作流总览

```
update_data → run_daily_research → get_daily_report → get_market_overview
    (步骤1)           (步骤2)              (步骤3)            (步骤4)
```

## 📥 步骤 1：更新行情数据

**目的**：拉取最新日线数据，保证研究数据的时效性

**MCP 工具**：`update_data(universe="csi300", dry_run=False)`

**参数说明**：
- `universe`：可选 "csi300"、"csi500" 或具体股票代码
- `dry_run`：预览模式，不执行实际写操作

**耗时**：15-30 分钟

**示例调用**：
```
update_data(universe="csi300")
```

**注意**：这是写操作，会修改数据库。建议在收盘后（15:30后）执行。

**下一步指引**：
- ✅ 数据更新成功：继续步骤2 → 调用 `run_daily_research()`
- ❌ 更新失败：检查网络连接，或先调用 `run_health_check()` 检查系统状态

---

## 🧠 步骤 2：运行每日研究

**目的**：执行完整研究流程，生成日报

**MCP 工具**：`run_daily_research(target_date="", dry_run=False)`

**流程说明**：
1. 市场快照
2. 因子计算（29个因子）
3. 新闻采集 + 事件入库
4. 日报生成
5. 预测追踪 + 决策记忆

**耗时**：5-15 分钟

**输出**：`knowledge/daily/YYYY-MM-DD.md`

**示例调用**：
```
run_daily_research()
```

**下一步指引**：
- ✅ 研究完成：继续步骤3 → 调用 `get_daily_report(date="YYYY-MM-DD")`
- ❌ 研究失败：检查错误信息，通常是数据缺失。先运行 `update_data` 再重试

---

## 📝 步骤 3：获取日报

**目的**：查看生成的研究报告

**MCP 工具**：`get_daily_report(date="YYYY-MM-DD")`

**示例调用**：
```
get_daily_report(date="2026-07-08")
```

**输出解读**：报告包含市场概况、因子分析、策略信号、风险提示。

**下一步指引**：
- ✅ 获取到日报：继续步骤4 → 调用 `get_market_overview()` 交叉验证
- ❌ 日报未生成：检查 `knowledge/daily/` 目录，运行 `run_health_check()` 检查系统状态

---

## 🌐 步骤 4：获取市场概况

**目的**：与日报交叉验证，确认市场环境

**MCP 工具**：`get_market_overview()`

**示例调用**：
```
get_market_overview()
```

**下一步指引**：
- ✅ 完成：每日研究流程结束，根据日报和市场概况制定投资决策

---

## 📊 完整工作流示例

```
# 收盘后（15:30）
update_data(universe="csi300")
# → 等待 15-30 分钟

# 数据更新完成后
run_daily_research()
# → 等待 5-15 分钟

# 次日查看
get_daily_report(date="2026-07-08")
# → 查看研究报告

get_market_overview()
# → 交叉验证市场环境

# 输出：投资决策建议
```

---

## ❓ 常见问题

**Q**: update_data 耗时太长怎么办？
**A**: 这是正常的，AKShare 需要逐只拉取数据。建议后台运行。

**Q**: run_daily_research 失败怎么办？
**A**: 检查错误信息，通常是数据缺失。先运行 `update_data` 再重试。

**Q**: 日报没有生成怎么办？
**A**: 检查 `knowledge/daily/` 目录是否存在，运行 `run_health_check()` 检查系统状态。
