# 市场快速检查工作流

---
name: market-quick-check
description: 快速获取市场概况、个股行情和指数数据的组合查询
requires_mcp: [get_market_overview, get_quote, get_index_data, get_calendar, get_universe]
workflow:
  - step: 1
    name: 获取市场概况
    mcp: get_market_overview
    next: 查询个股行情(get_quote)
  - step: 2
    name: 查询个股行情
    mcp: get_quote
    next: 获取指数数据(get_index_data)
  - step: 3
    name: 获取指数数据
    mcp: get_index_data
    next: 获取交易日历(get_calendar)
  - step: 4
    name: 查看跟踪股票列表
    mcp: get_universe
    next: 完成
---

## 🔄 工作流总览

```
get_market_overview → get_quote → get_index_data → get_calendar → get_universe
    (步骤1)            (步骤2)        (步骤3)          (步骤4)        (步骤5)
```

---

## 🌐 步骤 1：获取市场概况

**目的**：快速了解大盘整体情况

**MCP 工具**：`get_market_overview()`

**示例调用**：
```
get_market_overview()
```

**输出解读**：
- `indices`：沪深300、中证500、科创50等指数最新数据
- `market_stats`：上涨家数、下跌家数、平盘家数
- `hot_sectors`：领涨/领跌板块

**下一步指引**：
- ✅ 获取到概况：继续步骤2 → 调用 `get_quote(ticker)` 查询关注个股

---

## 📈 步骤 2：查询个股行情

**目的**：获取指定股票的实时行情

**MCP 工具**：`get_quote(ticker)`

**示例调用**：
```
get_quote("600519")
```

**输出解读**：
- `price`：最新价
- `open`：开盘价
- `high`：最高价
- `low`：最低价
- `volume`：成交量
- `pct_change`：涨跌幅
- `turnover`：换手率

**下一步指引**：
- ✅ 获取到行情：继续步骤3 → 调用 `get_index_data(index_code, days=60)`
- ❌ 无数据：调用 `get_universe()` 确认股票是否在跟踪范围

---

## 📊 步骤 3：获取指数数据

**目的**：了解指数走势，判断市场趋势

**MCP 工具**：`get_index_data(index_code, days=60)`

**参数说明**：
- `index_code`：指数代码（沪深300="000300"、中证500="000905"、科创50="000688"）
- `days`：回溯天数

**示例调用**：
```
get_index_data("000300", days=120)
```

**输出解读**：
- `close`：收盘价
- `pct_change`：涨跌幅
- `volume`：成交量

**下一步指引**：
- ✅ 获取到数据：继续步骤4 → 调用 `get_calendar(count=30)`

---

## 📅 步骤 4：获取交易日历

**目的**：了解近期交易日安排，规划操作时间

**MCP 工具**：`get_calendar(count=30)`

**示例调用**：
```
get_calendar(count=30)
```

**输出解读**：
- 未来30个交易日的日期
- 用于规划回测时间段和数据更新时间

**下一步指引**：
- ✅ 获取到日历：继续步骤5 → 调用 `get_universe()`

---

## 📋 步骤 5：查看跟踪股票列表

**目的**：确认股票池范围，验证股票是否在跟踪范围内

**MCP 工具**：`get_universe()`

**示例调用**：
```
get_universe()
```

**输出解读**：
- 系统跟踪的所有股票代码

**下一步指引**：
- ✅ 完成：市场快速检查流程结束

---

## 📊 完整工作流示例

```
# 开盘前快速检查
get_market_overview()
# → 返回: 大盘概况

get_index_data("000300", days=5)
# → 返回: 沪深300近期走势

get_quote("600519")
# → 返回: 关注个股最新价

get_calendar(count=7)
# → 返回: 本周交易日安排

get_universe()
# → 返回: 确认股票池

# 盘中快速检查
get_market_overview()
# → 返回: 实时涨跌统计

get_quote("600519")
# → 返回: 个股实时行情

# 输出：市场快照 + 操作建议
```

---

## ❓ 常见问题

**Q**: get_quote 返回空怎么办？
**A**: 检查股票代码格式是否正确，或调用 `get_universe()` 确认股票是否在跟踪范围

**Q**: 如何选择指数代码？
**A**: 常用指数：沪深300("000300")、中证500("000905")、科创50("000688")

**Q**: get_calendar 返回日期不够怎么办？
**A**: 增加 `count` 参数，如 `get_calendar(count=60)`

**Q**: 如何判断市场整体强弱？
**A**: 结合 `get_market_overview()` 的上涨家数/下跌家数比例和指数涨跌幅判断
