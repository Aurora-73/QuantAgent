# 行业板块选股工作流

---
name: sector-screening
description: 行业/概念板块选股四步筛选法，从获取板块成分股到构建指数再到逐股分析
requires_mcp: [get_sector_stocks, get_sector_index, get_history, search_tickers, get_market_overview, get_sector_list]
workflow:
  - step: 1
    name: 获取板块成分股
    mcp: get_sector_stocks
    next: 构建板块指数(get_sector_index)
  - step: 2
    name: 构建板块指数
    mcp: get_sector_index
    next: 逐股分析(get_history)
  - step: 3
    name: 逐股分析
    mcp: get_history
    next: 获取市场概况(get_market_overview)
  - step: 4
    name: 获取市场概况
    mcp: get_market_overview
    next: 完成
---

## 🔄 工作流总览

```
get_sector_stocks → get_sector_index → get_history → get_market_overview
    (步骤1)              (步骤2)           (步骤3)          (步骤4)
```

---

## 📋 步骤 1：获取板块成分股

**目的**：确定板块范围，获取成分股列表

**MCP 工具**：`get_sector_stocks(板块名称, sector_type="concept")`

**参数说明**：
- `sector_type="concept"`：东方财富概念板块（默认）
- `sector_type="industry"`：申万行业板块

**示例调用**：
```
get_sector_stocks("半导体", sector_type="concept")
```

**输出解读**：
- 返回成分股列表，关注 `count` 字段确认股票数量
- 正常数量：10-50只
- 异常情况：<5只或空列表

**下一步指引**：
- ✅ 正常：继续步骤2 → 调用 `get_sector_index(板块名称)`
- ❌ 成分股过少：先用 `get_sector_list(sector_type="concept")` 获取准确板块名称，或用 `search_tickers(关键词)` 搜索备选股票

**Fallback 流程**：
```
get_sector_stocks → 空/过少 → get_sector_list → 确认名称 → get_sector_stocks(重试)
                                            → search_tickers → 获取备选
```

---

## 📈 步骤 2：构建板块指数

**目的**：了解板块整体走势，计算板块平均收益

**MCP 工具**：`get_sector_index(板块名称, sector_type="concept", days=60)`

**参数说明**：
- `days`：回溯天数，建议 60-120 天

**示例调用**：
```
get_sector_index("半导体", days=120)
```

**输出解读**：
- `close`：板块指数收盘价
- `pct_change`：板块指数日涨跌幅
- `stock_count`：有效成分股数量
- **关键指标**：计算近20日板块平均涨幅 `sector_avg_return`

**下一步指引**：
- ✅ 获取到板块指数：继续步骤3 → 调用 `get_history(ticker, days=60)` 逐股分析
- ❌ 获取失败：检查板块名称是否正确，或使用 `get_index_data("000300")` 用大盘指数代替

---

## 🔍 步骤 3：逐股分析

**目的**：筛选优质个股，计算综合评分

**MCP 工具**：`get_history(ticker, days=60)`

**参数说明**：
- `ticker`：股票代码（从步骤1获取的成分股列表中选取）
- `days`：回溯天数，建议 60 天

**分析框架**：对每只股票执行以下分析

### 3.1 近期走势（30分）
```python
avg_return = df["pct_change"].rolling(window=20).mean().iloc[-1]
```

### 3.2 成交量变化（25分）
```python
vol_ratio = df["volume"].iloc[-1] / df["volume"].rolling(window=20).mean().iloc[-1]
```

### 3.3 与板块指数相关性（25分）
```python
combined = pd.concat([sector_df["pct_change"], stock_df["pct_change"]], axis=1)
combined.columns = ["sector_return", "stock_return"]
correlation = combined.dropna()["sector_return"].corr(combined.dropna()["stock_return"])
```

### 3.4 综合评分（100分）
```python
def score_stock(df, sector_corr, sector_avg_return):
    score = 0
    # 涨幅得分
    stock_avg_return = df["pct_change"].rolling(window=20).mean().iloc[-1]
    score += 30 if stock_avg_return > sector_avg_return else max(0, int(30 * stock_avg_return / sector_avg_return))
    # 成交量得分
    vol_ratio = df["volume"].iloc[-1] / df["volume"].rolling(window=20).mean().iloc[-1]
    score += 25 if vol_ratio > 2 else 20 if vol_ratio > 1.5 else 15 if vol_ratio > 1 else 10
    # 相关性得分
    score += 25 if 0.3 < sector_corr <= 0.7 else 20 if sector_corr > 0.7 else 15 if sector_corr > 0 else 10
    # 流动性得分
    avg_amount = (df["close"] * df["volume"]).rolling(window=20).mean().iloc[-1]
    score += 20 if avg_amount > 50_000_000 else 15 if avg_amount > 20_000_000 else 10
    return score
```

**筛选条件**：
- 综合评分 > 60 分
- 近20日涨幅 > 板块平均涨幅
- vol_ratio > 1.5
- 0.3 < correlation <= 0.7
- 日均成交额 > 5000万

**示例调用**：
```
get_history("600519", days=60)
```

**下一步指引**：
- ✅ 分析完成：继续步骤4 → 调用 `get_market_overview()` 判断大盘环境
- ⚠️ 个股无数据：跳过该股票，继续分析下一只

---

## 🌐 步骤 4：获取市场概况

**目的**：判断大盘环境，验证选股逻辑

**MCP 工具**：`get_market_overview()`

**示例调用**：
```
get_market_overview()
```

**输出解读**：
- `indices`：沪深300、中证500、科创50指数
- `market_stats`：上涨/下跌家数统计
- `hot_sectors`：领涨/领跌板块

**下一步指引**：
- ✅ 完成：选股流程结束，输出候选股票列表和投资建议
- ⚠️ 大盘环境不佳：谨慎操作，减少仓位或等待

---

## 📊 完整工作流示例

```
# 第1步：获取板块成分股
result1 = get_sector_stocks("半导体")
# → 返回: ["600519", "300750", "002371", ...]

# 第2步：构建板块指数
result2 = get_sector_index("半导体", days=120)
# → 计算板块平均涨幅 sector_avg_return

# 第3步：逐股分析（循环）
for ticker in result1["tickers"]:
    result3 = get_history(ticker, days=60)
    # → 计算综合评分，筛选 > 60 分的股票

# 第4步：获取市场概况
result4 = get_market_overview()
# → 判断大盘环境

# 输出：候选股票列表 + 投资建议
```

---

## ❓ 常见问题

**Q**: 板块名称不准确怎么办？
**A**: 先用 `get_sector_list()` 获取准确名称，或用 `search_tickers()` 搜索关键词

**Q**: 成分股太多（>50只）怎么处理？
**A**: 先看板块指数整体走势，再筛选成交量排名前20只重点分析

**Q**: 某只股票无数据怎么办？
**A**: 跳过该股票，继续分析其他股票

**Q**: 如何判断选股结果是否可靠？
**A**: 结合步骤4的市场概况，如果大盘环境与板块走势一致，则选股结果更可靠
