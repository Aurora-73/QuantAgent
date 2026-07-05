# 因子开发指南

> 如何添加和评估自定义因子。

---

## 因子架构

### 因子分类

| 类别 | 因子 | 说明 |
|------|------|------|
| **价格因子** | 动量、反转、均线偏离 | 基于价格序列 |
| **成交量因子** | 量比、成交量动量、价量相关 | 基于成交量 |
| **波动率因子** | 历史波动率、ATR、偏度、峰度 | 基于收益分布 |
| **技术指标** | RSI、MACD、布林带 | 经典技术分析 |
| **基本面因子** | ROE、PE_TTM、营收增速、净利润增速 | 基于财务数据 |
| **复合因子** | 质量动量、聪明资金 | 多因子组合 |

### 因子引擎

系统使用 `FactorEngine` 作为因子计算引擎：

```python
from research.factors import FactorEngine

engine = FactorEngine()

# 计算所有因子
df_with_factors = engine.compute_all(df)

# 计算指定因子
df_with_factors = engine.compute(df, ["momentum_20d", "rsi_14", "volatility_20d"])

# 列出所有因子
factors = engine.list_factors()
```

---

## 添加新因子

### 步骤 1：注册因子

使用 `@FactorEngine.register` 装饰器注册新因子：

```python
from research.factors import FactorEngine
import pandas as pd

@FactorEngine.register("my_factor", "我的自定义因子")
def my_factor(df: pd.DataFrame) -> pd.Series:
    """计算我的自定义因子"""
    # 输入: OHLCV DataFrame
    # 输出: pd.Series (index 为日期)
    return df["close"].pct_change(10) / df["close"].pct_change().rolling(20).std()
```

### 步骤 2：因子规范

每个因子函数必须满足：

| 要求 | 说明 |
|------|------|
| 输入 | `pd.DataFrame`，必须包含 `open`, `high`, `low`, `close`, `volume` |
| 输出 | `pd.Series`，index 为日期，值为因子值 |
| 命名 | 使用 snake_case，如 `momentum_20d`, `rsi_14` |
| 描述 | 简洁的中文描述 |

### 步骤 3：因子测试

```python
import pandas as pd
import numpy as np
from research.factors import FactorEngine, my_factor

# 创建测试数据
dates = pd.date_range("2024-01-01", periods=100)
prices = np.cumprod(1 + np.random.randn(100) * 0.01) * 100

df = pd.DataFrame({
    "open": prices,
    "high": prices * 1.01,
    "low": prices * 0.99,
    "close": prices,
    "volume": np.random.randint(100000, 1000000, 100)
}, index=dates)

# 测试因子计算
result = my_factor(df)
print(f"因子计算完成，非 NaN 值: {result.notna().sum()}")
print(f"因子均值: {result.mean():.4f}")
print(f"因子标准差: {result.std():.4f}")
```

---

## 内置因子详解

### 价格因子

| 因子名 | 计算方式 | 说明 |
|--------|---------|------|
| `momentum_5d` | `close.pct_change(5)` | 5日收益率 |
| `momentum_10d` | `close.pct_change(10)` | 10日收益率 |
| `momentum_20d` | `close.pct_change(20)` | 20日收益率 |
| `momentum_60d` | `close.pct_change(60)` | 60日收益率 |
| `reversal_5d` | `-close.pct_change(5)` | 5日反转 |
| `reversal_20d` | `-close.pct_change(20)` | 20日反转 |
| `ma_deviation_5` | `(close - ma5) / ma5` | 偏离5日均线 |
| `ma_deviation_20` | `(close - ma20) / ma20` | 偏离20日均线 |
| `ma_deviation_60` | `(close - ma60) / ma60` | 偏离60日均线 |
| `high_low_ratio` | `(close - low20) / (high20 - low20)` | 20日高低位 |

### 成交量因子

| 因子名 | 计算方式 | 说明 |
|--------|---------|------|
| `volume_ratio_5d` | `volume / ma_volume_5` | 5日量比 |
| `volume_ratio_20d` | `volume / ma_volume_20` | 20日量比 |
| `volume_momentum` | `volume.pct_change(5)` | 成交量动量 |
| `turnover_ma5` | `turnover.rolling(5).mean()` | 5日平均换手率 |
| `price_volume_corr` | `corr(returns, volume_returns, 20d)` | 价量相关性 |

### 波动率因子

| 因子名 | 计算方式 | 说明 |
|--------|---------|------|
| `volatility_20d` | `std(returns, 20d) * sqrt(252)` | 年化波动率 |
| `volatility_60d` | `std(returns, 60d) * sqrt(252)` | 年化波动率 |
| `atr_14` | `ATR(14) / close` | 归一化ATR |
| `realized_skew` | `skew(returns, 20d)` | 实现偏度 |
| `realized_kurt` | `kurt(returns, 20d)` | 实现峰度 |

### 技术指标

| 因子名 | 计算方式 | 说明 |
|--------|---------|------|
| `rsi_14` | `100 - (100 / (1 + RS))` | 14日RSI |
| `macd_diff` | `MACD - Signal` | MACD差值 |
| `bollinger_position` | `(close - lower) / (upper - lower)` | 布林带位置 |

### 基本面因子

| 因子名 | 计算方式 | 说明 |
|--------|---------|------|
| `roe` | `df["roe"]` | 净资产收益率 |
| `pe_ttm` | `close / eps` | 市盈率(TTM) |
| `revenue_growth` | `revenue / revenue.shift(60) - 1` | 营收同比增速 |
| `profit_growth` | `net_profit / net_profit.shift(60) - 1` | 净利润同比增速 |

### 复合因子

| 因子名 | 计算方式 | 说明 |
|--------|---------|------|
| `quality_momentum` | `momentum_20d / volatility_20d` | 质量动量 |
| `smart_money` | `mean(returns * volume_change, 10d)` | 聪明资金 |

---

## 因子评估

### 评估指标

| 指标 | 说明 | 阈值 |
|------|------|------|
| **IC** | 信息系数，因子与收益的相关性 | >0.03 有效 |
| **ICIR** | IC的稳定性（IC均值/IC标准差） | >0.3 稳定 |
| **Rank IC** | 秩相关系数 | >0.03 有效 |
| **Rank ICIR** | 秩相关系数的稳定性 | >0.3 稳定 |
| **Decay Half-Life** | 因子衰减半衰期（天数） | >10 持久 |
| **分组收益** | 多空分组收益差 | >0 有效 |

### 评估流程

```bash
# 评估单个因子
python -m scripts factor-eval --factor momentum_20d --start 2024-01-01

# 评估所有因子
python -m scripts factor-eval --all --start 2024-01-01
```

### 评估结果解读

```json
{
  "factor": "momentum_20d",
  "ic": 0.052,
  "icir": 0.38,
  "rank_ic": 0.048,
  "rank_icir": 0.35,
  "decay_half_life": 12,
  "group_returns": [0.021, 0.015, 0.008, -0.003, -0.012],
  "long_short_spread": 0.033
}
```

**解读**：
- IC=0.052 > 0.03，因子有效
- ICIR=0.38 > 0.3，因子稳定
- 分组收益单调递减，因子区分度好
- 多空收益差=3.3%，因子有Alpha

---

## 因子中性化

### 行业中性化

系统支持截面OLS回归中性化：

```python
from research.neutralization import neutralize

# 对因子进行行业中性化
neutralized_factor = neutralize(
    factor=df["momentum_20d"],
    industry=df["industry"],
    market_cap=df["market_cap"]
)
```

**中性化步骤**：
1. 对因子进行截面回归
2. 自变量：行业哑变量 + log(市值)
3. 中性化后因子 = 原始因子 - 预测值

### 中性化效果

| 指标 | 中性化前 | 中性化后 |
|------|---------|---------|
| IC | 0.052 | 0.048 |
| ICIR | 0.38 | 0.42 |
| 行业暴露 | 0.25 | 0.02 |
| 市值暴露 | 0.18 | 0.01 |

---

## 因子衰减检测

### 衰减曲线

```python
from research.decay_detection import detect_decay

result = detect_decay(
    factor=df["momentum_20d"],
    returns=df["close"].pct_change().shift(-1),
    max_lag=20
)

print(f"衰减半衰期: {result['half_life']} 天")
```

### 衰减解读

| 半衰期 | 说明 |
|--------|------|
| >20 天 | 持久因子，适合中长线 |
| 10-20 天 | 中等衰减，适合波段 |
| 5-10 天 | 快速衰减，适合短线 |
| <5 天 | 极快衰减，需谨慎使用 |

---

## 因子生命周期

### 生命周期管理

```
假设生成 → 代码实现 → 回测评估 → 归因分析 → 入库部署 → 衰减追踪 → 自动告警 → 淘汰
```

### 因子状态

| 状态 | 说明 |
|------|------|
| `pending` | 待验证 |
| `verified` | 已验证，可部署 |
| `active` | 正在使用 |
| `decayed` | 衰减，需重新评估 |
| `deprecated` | 已淘汰 |

---

## 最佳实践

### 1. 因子标准化

- 因子值应标准化到相同量纲
- 使用 Z-score 或分位数标准化
- 避免因子值过大或过小

```python
def normalize_factor(factor: pd.Series) -> pd.Series:
    return (factor - factor.mean()) / factor.std()
```

### 2. 缺失值处理

- 使用前向填充或后向填充
- 对于基本面因子，使用最近财报数据
- 避免删除太多数据

```python
df["roe"] = df["roe"].fillna(method="ffill")
```

### 3. 因子正交化

- 避免因子之间高度相关
- 使用 PCA 或逐步回归
- 确保因子提供独立信息

### 4. 样本外测试

- 训练集和测试集严格分开
- 避免数据窥探
- 使用 Walk-Forward 验证

### 5. 因子组合

- 多因子组合优于单因子
- 使用等权或 IC 加权
- 定期重新平衡

---

## 常见问题

### Q: 因子计算出现大量 NaN？

**原因**：数据不足或计算窗口不够

**解决方案**：
```python
# 检查数据完整性
print(f"数据行数: {len(df)}")
print(f"缺失值比例: {df.isnull().mean() * 100:.2f}%")

# 调整计算窗口
# 对于20日因子，至少需要20个交易日的数据
```

### Q: 因子 IC 不稳定？

**原因**：因子在不同市场状态下表现不同

**解决方案**：
- 检查因子在牛市/熊市/震荡市的表现
- 考虑市场状态切换
- 使用自适应因子权重

### Q: 如何验证因子不包含未来信息？

```python
# 确保因子计算不使用未来数据
# 例如：计算20日动量时，只使用过去20天的数据
factor = df["close"].pct_change(20)

# 验证：因子值应在当天收盘后才能确定
# 如果因子值提前出现，说明存在未来信息泄露
```

### Q: 如何处理因子拥挤？

**原因**：太多人使用相同的因子策略

**解决方案**：
- 寻找新的因子
- 组合多个因子
- 使用另类数据（新闻、情绪等）

---

## 参考

- [因子引擎源码](file:///E:/Code/量化交易/quant-system/research/factors.py)
- [因子评估工具](file:///E:/Code/量化交易/quant-system/research/evaluator.py)
- [行业中性化](file:///E:/Code/量化交易/quant-system/research/neutralization.py)
- [衰减检测](file:///E:/Code/量化交易/quant-system/research/decay_detection.py)
