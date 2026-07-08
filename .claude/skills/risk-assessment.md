# 风险评估工作流

---
name: risk-assessment
description: 策略风险评估标准流程，包含压力测试、归因分析和风险报告
requires_mcp: [run_stress_test, run_brinson_attribution, get_risk_report]
---

## 步骤 1：运行压力测试

调用 `run_stress_test(strategy, ticker)` 在4个历史危机场景下测试策略表现：

1. **2015年股灾**（2015-06-15 至 2015-09-30）
2. **2018年贸易战**（2018-06-01 至 2018-12-31）
3. **2020年疫情**（2020-02-01 至 2020-03-31）
4. **2024年市场调整**（2024-01-01 至 2024-06-30）

**示例**：
```
run_stress_test(strategy="momentum", ticker="600519")
```

**输出解读**：关注每个场景的 `max_drawdown` 和 `total_return`，评估策略的抗风险能力。

---

## 步骤 2：运行收益归因

调用 `run_brinson_attribution(ticker, date_start, date_end)` 分析收益来源：

- **配置效应**：行业配置贡献
- **选股效应**：个股选择贡献
- **交互效应**：配置与选股的交互贡献

**示例**：
```
run_brinson_attribution(ticker="600519", date_start="2024-01-01", date_end="2025-12-31")
```

**输出解读**：判断收益主要来自行业配置还是个股选择能力。

---

## 步骤 3：获取综合风险报告

调用 `get_risk_report(strategy, ticker)` 获取包含压力测试和衰减检测的综合报告。

**示例**：
```
get_risk_report(strategy="momentum", ticker="600519")
```

---

## 完整工作流

```
1. run_stress_test(strategy="momentum", ticker="600519") → 压力测试
2. run_brinson_attribution(ticker="600519", date_start="2024-01-01", date_end="2025-12-31") → 归因分析
3. get_risk_report(strategy="momentum", ticker="600519") → 综合风险报告
```

---

## 常见问题

**Q**: 压力测试结果不理想怎么办？
**A**: 调整策略参数（`get_strategy_config`），或增加风控规则（如仓位限制）。

**Q**: 归因分析显示配置效应为主怎么办？
**A**: 说明策略收益主要依赖行业轮动，而非个股选择能力。

**Q**: 如何判断策略是否衰减？
**A**: 关注 `run_decay_detection` 的输出，胜率下降或IC衰减加速表明策略可能失效。
