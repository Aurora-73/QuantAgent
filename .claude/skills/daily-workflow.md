# 每日研究工作流

---
name: daily-workflow
description: 每日收盘后的标准研究流程，从数据更新到日报生成
requires_mcp: [update_data, run_daily_research, get_daily_report, get_market_overview, run_health_check]
---

## 步骤 1：更新行情数据

调用 `update_data(universe="csi300")` 拉取最新日线数据。

- **耗时**：15-30 分钟
- **参数**：`universe` 可选 "csi300"、"csi500" 或具体股票代码

**示例**：
```
update_data(universe="csi300")
```

**注意**：这是写操作，会修改数据库。建议在收盘后（15:30后）执行。

---

## 步骤 2：运行每日研究

调用 `run_daily_research()` 执行完整研究流程：

1. 市场快照
2. 因子计算（29个因子）
3. 新闻采集 + 事件入库
4. 日报生成
5. 预测追踪 + 决策记忆

- **耗时**：5-15 分钟
- **输出**：`knowledge/daily/YYYY-MM-DD.md`

**示例**：
```
run_daily_research()
```

---

## 步骤 3：获取日报

调用 `get_daily_report(date="YYYY-MM-DD")` 获取生成的研究报告。

**示例**：
```
get_daily_report(date="2026-07-08")
```

**输出解读**：报告包含市场概况、因子分析、策略信号、风险提示。

---

## 步骤 4：获取市场概况

调用 `get_market_overview()` 获取当日大盘指数最新数据，与日报交叉验证。

---

## 完整工作流

```
# 收盘后（15:30）
update_data(universe="csi300")

# 数据更新完成后
run_daily_research()

# 次日查看
get_daily_report()
get_market_overview()
```

---

## 常见问题

**Q**: update_data 耗时太长怎么办？
**A**: 这是正常的，AKShare 需要逐只拉取数据。建议后台运行。

**Q**: run_daily_research 失败怎么办？
**A**: 检查错误信息，通常是数据缺失。先运行 `update_data` 再重试。

**Q**: 日报没有生成怎么办？
**A**: 检查 `knowledge/daily/` 目录是否存在，运行 `run_health_check()` 检查系统状态。
