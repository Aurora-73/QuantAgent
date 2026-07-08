# 因子研究工作流

---
name: factor-research
description: 因子研究标准流程，从获取因子列表到评估因子有效性
requires_mcp: [get_factors, run_factor_evaluation, run_decay_detection]
---

## 步骤 1：获取因子列表

调用 `get_factors()` 获取已注册的29个因子列表：

- **OHLCV因子**（25个）：动量、波动率、成交量等技术因子
- **基本面因子**（4个）：市盈率、市净率、市销率、股息率

**输出解读**：每个因子包含名称、描述和数据类型。

---

## 步骤 2：运行因子评估

调用 `run_factor_evaluation(factor_name, date_start, date_end)` 评估因子有效性：

- **IC值**：因子与收益的秩相关系数
- **ICIR**：IC值的年化信息比率
- **分组收益**：十分组回测收益

**示例**：
```
run_factor_evaluation(factor_name="momentum_20d", date_start="2024-01-01", date_end="2025-12-31")
```

**输出解读**：
- IC均值 > 0.03：因子有效
- ICIR > 0.5：因子稳定有效
- 分组收益单调递增：因子区分度好

---

## 步骤 3：运行衰减检测

调用 `run_decay_detection(factor_name)` 检测因子是否存在衰减：

**示例**：
```
run_decay_detection(factor_name="momentum_20d")
```

**输出解读**：关注胜率变化趋势和IC衰减速度。

---

## 完整工作流

```
1. get_factors() → 查看因子列表
2. run_factor_evaluation(factor_name="momentum_20d", date_start="2024-01-01", date_end="2025-12-31") → 评估因子
3. run_decay_detection(factor_name="momentum_20d") → 检测衰减
```

---

## 常见问题

**Q**: 如何选择因子进行研究？
**A**: 优先选择IC均值高且ICIR稳定的因子，避开已衰减的因子。

**Q**: 因子评估结果不佳怎么办？
**A**: 尝试不同时间窗口（如调整lookback周期），或组合多个因子。

**Q**: 因子衰减了怎么办？
**A**: 考虑更换因子、调整参数，或增加因子更新频率。
