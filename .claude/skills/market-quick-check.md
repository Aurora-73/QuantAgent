# 市场快速检查工作流

---
name: market-quick-check
description: 快速获取市场概况、个股行情和指数数据的组合查询
requires_mcp: [get_market_overview, get_quote, get_index_data, get_calendar, get_universe]
---

## 步骤 1：获取市场概况

调用 `get_market_overview()` 获取当日大盘指数和涨跌统计。

**示例**：
```
get_market_overview()
```

**输出解读**：
- `indices`：沪深300、中证500、科创50等指数最新数据
- `market_stats`：上涨家数、下跌家数、平盘家数
- `hot_sectors`：领涨/领跌板块

---

## 步骤 2：查询个股行情

调用 `get_quote(ticker)` 获取指定股票的最新行情。

**示例**：
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

---

## 步骤 3：获取指数数据

调用 `get_index_data(index_code, days=60)` 获取指数的历史行情。

**示例**：
```
get_index_data("000300", days=120)
```

**输出解读**：
- `close`：收盘价
- `pct_change`：涨跌幅
- `volume`：成交量
- 用于判断大盘趋势

---

## 步骤 4：获取交易日历

调用 `get_calendar(count=30)` 获取近期交易日历。

**示例**：
```
get_calendar(count=30)
```

**输出解读**：
- 未来30个交易日的日期
- 用于规划回测时间段和数据更新时间

---

## 步骤 5：查看跟踪股票列表

调用 `get_universe()` 获取系统跟踪的股票列表。

**示例**：
```
get_universe()
```

**输出解读**：
- 系统跟踪的所有股票代码
- 用于确认股票是否在跟踪范围内

---

## 完整工作流示例

```
# 开盘前快速检查
1. get_market_overview() → 大盘概况
2. get_index_data("000300", days=5) → 沪深300近期走势
3. get_quote("600519") → 关注个股最新价
4. get_calendar(count=7) → 本周交易日安排
5. get_universe() → 确认股票池

# 盘中快速检查
1. get_market_overview() → 实时涨跌统计
2. get_quote("600519") → 个股实时行情
3. get_index_data("000300", days=1) → 指数今日走势
```

---

## 常见问题

**Q**: get_quote 返回空怎么办？
**A**: 检查股票代码格式是否正确，或调用 `get_universe()` 确认股票是否在跟踪范围

**Q**: 如何选择指数代码？
**A**: 常用指数：沪深300("000300")、中证500("000905")、科创50("000688")

**Q**: get_calendar 返回日期不够怎么办？
**A**: 增加 `count` 参数，如 `get_calendar(count=60)`

**Q**: 如何判断市场整体强弱？
**A**: 结合 `get_market_overview()` 的上涨家数/下跌家数比例和指数涨跌幅判断
