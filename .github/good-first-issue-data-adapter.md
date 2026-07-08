# [Good First Issue] 添加新数据源适配器

## 适合谁

- 熟悉 Python 和 pandas
- 想了解量化数据管道如何工作
- 希望快速上手项目贡献

## 任务

为 QuantAgent 添加一个新的数据源适配器（如 Tushare、JoinQuant、东方财富等），让用户可以选择更多数据来源。

## 背景

当前项目支持 `baostock`（主）和 `AKShare`（备）两个数据源。不同用户可能有不同的数据源偏好或 API key，添加适配器可以让更多人用上 QuantAgent。

## 你需要做的

### 1. 阅读现有适配器

先看 `data/provider.py`，了解 `DataProvider` 如何调度数据源：
- `get_stock_daily(ticker, start, end)` — 获取日线
- `get_financials(ticker)` — 获取财务报表

### 2. 创建适配器文件

在 `data/adapters/` 下新建文件，例如 `tushare_adapter.py`：

```python
import pandas as pd

class TushareAdapter:
    """Tushare 数据源适配器"""

    def __init__(self, token: str):
        import tushare as ts
        ts.set_token(token)
        self.pro = ts.pro_api()

    def get_stock_daily(self, ticker: str, start: str, end: str) -> pd.DataFrame:
        """返回 DataFrame，列: date, open, high, low, close, volume"""
        df = self.pro.daily(ts_code=ticker, start_date=start, end_date=end)
        # ... 格式化列名和类型
        return df

    def get_financials(self, ticker: str) -> pd.DataFrame:
        """返回财务报表"""
        ...
```

### 3. 注册到 DataProvider

在 `data/provider.py` 的数据源优先级列表中添加你的适配器。

### 4. 写测试

在 `tests/` 下添加测试，确保适配器返回的 DataFrame 列名和类型正确。

## 验收标准

- [ ] 适配器实现 `get_stock_daily` 和 `get_financials` 方法
- [ ] 返回的 DataFrame 列名与现有格式一致（`date`, `open`, `high`, `low`, `close`, `volume`）
- [ ] 在 `DataProvider` 中注册成功
- [ ] 至少一个单元测试通过

## 需要帮助？

- 在本 Issue 下留言
- 或发 GitHub Discussions

## 标签

`good first issue` `data-source` `help wanted`
