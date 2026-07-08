---
name: factor-research
description: 因子研究标准流程，从获取因子列表到评估因子有效性
requires_mcp: [get_factors, run_factor_evaluation, run_decay_detection, get_financials, get_latest_financials, update_financials]
workflow:
  - step: 1
    name: 获取因子列表
    mcp: get_factors
    next: 运行因子评估(run_factor_evaluation)
  - step: 2
    name: 运行因子评估
    mcp: run_factor_evaluation
    next: 运行衰减检测(run_decay_detection)
  - step: 3
    name: 运行衰减检测
    mcp: run_decay_detection
    next: 完成
---
# 因子研究工作流



## 🔄 工作流总览

```
get_factors → run_factor_evaluation → run_decay_detection
    (步骤1)          (步骤2)             (步骤3)
```

---

## 📋 步骤 1：获取因子列表

**目的**：了解系统支持的因子，选择研究目标

**MCP 工具**：`get_factors()`

**输出解读**：
- **OHLCV因子**（25个）：动量、波动率、成交量等技术因子
- **基本面因子**（4个）：市盈率、市净率、市销率、股息率
- 每个因子包含名称、描述和数据类型

**示例调用**：
```
get_factors()
```

**下一步指引**：
- ✅ 获取到因子列表：继续步骤2 → 调用 `run_factor_evaluation(factor_name, date_start, date_end)`

---

## 📊 步骤 2：运行因子评估

**目的**：评估因子有效性，判断是否值得使用

**MCP 工具**：`run_factor_evaluation(factor_name, date_start, date_end)`

**评估指标**：
- **IC值**：因子与收益的秩相关系数
- **ICIR**：IC值的年化信息比率
- **分组收益**：十分组回测收益

**示例调用**：
```
run_factor_evaluation(factor_name="momentum_20d", date_start="2024-01-01", date_end="2025-12-31")
```

**输出解读**：
- IC均值 > 0.03：因子有效
- ICIR > 0.5：因子稳定有效
- 分组收益单调递增：因子区分度好

**下一步指引**：
- ✅ 评估完成：继续步骤3 → 调用 `run_decay_detection(factor_name)` 检测因子是否衰减
- ❌ 因子不存在：返回步骤1，重新选择因子

---

## 🔍 步骤 3：运行衰减检测

**目的**：检测因子是否存在衰减，判断策略生命周期

**MCP 工具**：`run_decay_detection(factor_name)`

**示例调用**：
```
run_decay_detection(factor_name="momentum_20d")
```

**输出解读**：
- 胜率变化趋势
- IC衰减速度
- 因子半衰期

**下一步指引**：
- ✅ 检测完成：因子研究流程结束，根据结果决定是否使用该因子

---

## 📈 完整工作流示例

```
# 第1步：获取因子列表
result1 = get_factors()
# → 返回: ["momentum_20d", "rsi_14d", "volatility_20d", ...]

# 第2步：运行因子评估
result2 = run_factor_evaluation(factor_name="momentum_20d", date_start="2024-01-01", date_end="2025-12-31")
# → 返回: {"ic_mean": 0.05, "icir": 0.8, "group_returns": [...]}

# 第3步：运行衰减检测
result3 = run_decay_detection(factor_name="momentum_20d")
# → 返回: {"decay_rate": 0.15, "half_life": 120}

# 输出：因子评估报告 + 是否使用建议
```

---

## ❓ 常见问题

**Q**: 如何选择因子进行研究？
**A**: 优先选择IC均值高且ICIR稳定的因子，避开已衰减的因子。

**Q**: 因子评估结果不佳怎么办？
**A**: 尝试不同时间窗口（如调整lookback周期），或组合多个因子。

**Q**: 因子衰减了怎么办？
**A**: 考虑更换因子、调整参数，或增加因子更新频率。

**Q**: 基本面因子数据不足怎么办？
**A**: 调用 `update_financials(ticker)` 更新财务数据，或使用 `get_latest_financials(ticker)` 获取最新数据
