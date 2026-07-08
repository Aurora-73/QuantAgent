# 半导体板块选股工作流

---
name: sector-screening
description: 行业/概念板块选股四步筛选法，从获取板块成分股到构建指数再到逐股分析
requires_mcp: [get_sector_stocks, get_sector_index, get_history, search_tickers, get_market_overview, get_sector_list]
---

## 步骤 1：获取板块成分股

调用 `get_sector_stocks(板块名称, sector_type="concept")` 获取股票列表。

- `sector_type="concept"`：东方财富概念板块（默认）
- `sector_type="industry"`：申万行业板块

**示例**：
```
get_sector_stocks("半导体", sector_type="concept")
```

**Fallback**：如果返回空列表或数量过少（<5只），尝试：
1. 先用 `get_sector_list(sector_type="concept")` 获取所有板块名称，确认板块是否存在
2. 用 `search_tickers(板块名称)` 搜索已知龙头股作为备选

---

## 步骤 2：构建板块指数

调用 `get_sector_index(板块名称, sector_type="concept", days=60)` 构建等权指数。

首次调用耗时较长（30s-2min），后续调用从缓存返回。

**示例**：
```
get_sector_index("半导体", days=120)
```

**输出解读**：关注 `close`、`pct_change`、`stock_count` 字段，判断板块整体走势和成分股覆盖度。

---

## 步骤 3：逐股分析

对列表中每只股票调用 `get_history(ticker, days=60)`，分析以下指标：

### 3.1 近期走势

计算近 N 日平均涨幅：
```python
# 近20日平均涨幅
avg_return = df["pct_change"].rolling(window=20).mean().iloc[-1]
```

### 3.2 成交量变化

计算成交量与近20日均量的比值：
```python
# 成交量相对于20日均量的倍数
vol_ratio = df["volume"].iloc[-1] / df["volume"].rolling(window=20).mean().iloc[-1]
```

### 3.3 与板块指数的相关性

**计算方法**：获取板块指数数据和个股数据，对齐日期后计算皮尔逊相关系数。

```python
# 1. 获取板块指数数据
sector_index = get_sector_index("半导体", days=60)
sector_df = pd.DataFrame(sector_index)
sector_df["date"] = pd.to_datetime(sector_df["date"])
sector_df = sector_df.set_index("date")

# 2. 获取个股数据
stock_df = get_history("600519", days=60)

# 3. 对齐日期
combined = pd.concat([sector_df["pct_change"], stock_df["pct_change"]], axis=1)
combined.columns = ["sector_return", "stock_return"]
combined = combined.dropna()

# 4. 计算相关性
correlation = combined["sector_return"].corr(combined["stock_return"])
```

**相关性解读**：
- `correlation > 0.7`：强正相关，跟随板块走势
- `0.3 < correlation <= 0.7`：中度相关
- `correlation <= 0.3`：弱相关或负相关，可能有独立走势

### 3.4 综合评分

```python
def score_stock(df, sector_corr, sector_avg_return):
    """综合评分（0-100分）"""
    score = 0
    
    # 涨幅得分（30分）：高于板块平均得满分
    stock_avg_return = df["pct_change"].rolling(window=20).mean().iloc[-1]
    if stock_avg_return > sector_avg_return:
        score += 30
    else:
        score += int(30 * stock_avg_return / sector_avg_return) if sector_avg_return > 0 else 15
    
    # 成交量得分（25分）：放量得高分
    vol_ratio = df["volume"].iloc[-1] / df["volume"].rolling(window=20).mean().iloc[-1]
    if vol_ratio > 2:
        score += 25
    elif vol_ratio > 1.5:
        score += 20
    elif vol_ratio > 1:
        score += 15
    else:
        score += 10
    
    # 相关性得分（25分）：跟随板块但不完全同步
    if 0.3 < sector_corr <= 0.7:
        score += 25
    elif sector_corr > 0.7:
        score += 20
    elif sector_corr > 0:
        score += 15
    else:
        score += 10
    
    # 流动性得分（20分）：日均成交额 > 5000万
    avg_amount = (df["close"] * df["volume"]).rolling(window=20).mean().iloc[-1]
    if avg_amount > 50_000_000:
        score += 20
    elif avg_amount > 20_000_000:
        score += 15
    else:
        score += 10
    
    return score
```

**示例**：
```
get_history("600519", days=60)
```

**筛选条件建议**：
- 综合评分 > 60 分
- 近期涨幅 > 板块平均涨幅
- 成交量持续放大（vol_ratio > 1.5）
- 与板块指数中度相关（0.3 < correlation <= 0.7）
- 流动性充足（日均成交额 > 5000万）

---

## 步骤 4：获取市场概况

调用 `get_market_overview()` 获取沪深300/中证500/科创50指数最新数据，判断大盘环境。

---

## 完整工作流示例

```
1. get_sector_stocks("半导体") → 获取成分股列表
2. get_sector_index("半导体") → 构建板块指数
3. get_market_overview() → 大盘环境判断
4. get_history("600519") → 分析龙头股
5. get_history("300750") → 分析热门股
```

---

## 常见问题

**Q**: 板块名称不准确怎么办？
**A**: 先用 `get_sector_list()` 获取准确名称，或用 `search_tickers()` 搜索关键词

**Q**: 成分股太多（>50只）怎么处理？
**A**: 先看板块指数整体走势，再筛选成交量排名前20只重点分析

**Q**: 某只股票无数据怎么办？
**A**: 跳过该股票，继续分析其他股票
