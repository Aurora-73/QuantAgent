---
name: 数据源请求
about: 请求接入新的行情/财务/另类数据源
title: "[DATA] 请求接入 "
labels: ["data-source", "good first issue"]
---

## 数据源信息

- **名称**: [e.g. Tushare / JoinQuant / Wind / 同花顺]
- **官网/API文档链接**:
- **是否免费**:
- **覆盖范围**: [A股 / 港股 / 美股 / 期货 / 另类数据]

## 需要的数据类型

- [ ] 日线行情（OHLCV）
- [ ] 分钟线
- [ ] 财务报表（资产负债表 / 利润表 / 现金流量表）
- [ ] 指数成分股
- [ ] 板块 / 概念板块
- [ ] 分红送配
- [ ] 龙虎榜 / 大单
- [ ] 另类数据（新闻、舆情、研报）

## 动机

当前数据源（baostock / AKShare）在哪方面不足？新数据源能解决什么问题？

## 实现参考

参考 `data/provider.py` 中的适配器接口。新适配器需实现：

```python
class NewAdapter:
    def get_stock_daily(self, ticker: str, start: str, end: str) -> pd.DataFrame:
        ...
    def get_financials(self, ticker: str) -> pd.DataFrame:
        ...
```

## 补充信息

API key 要求、限流策略、已知坑等。
