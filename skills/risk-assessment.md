# 风险评估工作流

---
name: risk-assessment
description: 策略风险评估标准流程，包含压力测试、归因分析和风险报告
requires_mcp: [run_stress_test, run_brinson_attribution, get_risk_report, get_market_regime]
workflow:
  - step: 1
    name: 运行压力测试
    mcp: run_stress_test
    next: 运行收益归因(run_brinson_attribution)
  - step: 2
    name: 运行收益归因
    mcp: run_brinson_attribution
    next: 获取综合风险报告(get_risk_report)
  - step: 3
    name: 获取综合风险报告
    mcp: get_risk_report
    next: 完成
---

## 🔄 工作流总览

```
run_stress_test → run_brinson_attribution → get_risk_report
    (步骤1)           (步骤2)                 (步骤3)
```

---

## 🧪 步骤 1：运行压力测试

**目的**：在历史危机场景下测试策略抗风险能力

**MCP 工具**：`run_stress_test(strategy, ticker)`

**测试场景**：
1. **2015年股灾**（2015-06-15 至 2015-09-30）
2. **2018年贸易战**（2018-06-01 至 2018-12-31）
3. **2020年疫情**（2020-02-01 至 2020-03-31）
4. **2024年市场调整**（2024-01-01 至 2024-06-30）

**示例调用**：
```
run_stress_test(strategy="momentum", ticker="600519")
```

**输出解读**：
- 关注每个场景的 `max_drawdown` 和 `total_return`
- 优秀策略：各场景最大回撤 < 25%

**下一步指引**：
- ✅ 压力测试完成：继续步骤2 → 调用 `run_brinson_attribution(ticker, date_start, date_end)`
- ❌ 无数据：检查股票代码是否正确，或调用 `get_history(ticker)` 确认数据

---

## 🔍 步骤 2：运行收益归因

**目的**：分析收益来源，判断策略能力构成

**MCP 工具**：`run_brinson_attribution(ticker, date_start, date_end)`

**归因维度**：
- **配置效应**：行业配置贡献
- **选股效应**：个股选择贡献
- **交互效应**：配置与选股的交互贡献

**示例调用**：
```
run_brinson_attribution(ticker="600519", date_start="2024-01-01", date_end="2025-12-31")
```

**输出解读**：
- 选股效应 > 配置效应：策略具备个股选择能力
- 配置效应 > 选股效应：策略收益主要依赖行业轮动

**下一步指引**：
- ✅ 归因分析完成：继续步骤3 → 调用 `get_risk_report(strategy, ticker)`

---

## 📊 步骤 3：获取综合风险报告

**目的**：获取包含压力测试、归因分析和衰减检测的综合报告

**MCP 工具**：`get_risk_report(strategy, ticker)`

**示例调用**：
```
get_risk_report(strategy="momentum", ticker="600519")
```

**输出解读**：
- 压力测试结果汇总
- 收益归因分析
- 策略衰减检测
- 综合风险评级

**下一步指引**：
- ✅ 完成：风险评估流程结束，根据报告制定风控措施

---

## 📈 完整工作流示例

```
# 第1步：运行压力测试
result1 = run_stress_test(strategy="momentum", ticker="600519")
# → 返回: {"scenarios": [...], "worst_drawdown": 0.18}

# 第2步：运行收益归因
result2 = run_brinson_attribution(ticker="600519", date_start="2024-01-01", date_end="2025-12-31")
# → 返回: {"allocation_effect": 0.05, "selection_effect": 0.12, "interaction_effect": 0.02}

# 第3步：获取综合风险报告
result3 = get_risk_report(strategy="momentum", ticker="600519")
# → 返回: 综合风险报告

# 输出：风险评估报告 + 风控建议
```

---

## ❓ 常见问题

**Q**: 压力测试结果不理想怎么办？
**A**: 调整策略参数（`get_strategy_config`），或增加风控规则（如仓位限制）。

**Q**: 归因分析显示配置效应为主怎么办？
**A**: 说明策略收益主要依赖行业轮动，而非个股选择能力。

**Q**: 如何判断策略是否衰减？
**A**: 关注 `run_decay_detection` 的输出，胜率下降或IC衰减加速表明策略可能失效。
