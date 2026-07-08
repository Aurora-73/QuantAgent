# 回测最佳实践

> 如何进行有效的回测验证。

---

## 回测架构

### 回测引擎

系统使用 VectorBT 作为快速回测引擎，同时支持 Qlib 进行更复杂的研究回测。

```python
from research.backtest import BacktestEngine

# 基于信号的回测
result = BacktestEngine.signal_backtest(
    close=df["close"],
    entries=entries_signal,
    exits=exits_signal,
    init_cash=1000000,
    fees=0.001,
    slippage=0.001
)

# 基于权重的组合回测
result = BacktestEngine.portfolio_backtest(
    close=df[["ticker1", "ticker2", "ticker3"]],
    weights=daily_weights,
    init_cash=1000000,
    fees=0.001,
    rebalance_freq="W"
)
```

### 回测流程

```
数据准备 → 因子计算 → 信号生成 → 仓位计算 → 风控检查 → 订单执行 → 绩效评估
```

---

## 回测指标

### 收益指标

| 指标 | 说明 | 计算方式 |
|------|------|---------|
| **总收益** | 累计收益率 | `(最终净值 - 初始净值) / 初始净值` |
| **年化收益** | 年化收益率 | `(1 + 总收益) ^ (252 / 交易天数) - 1` |
| **日收益** | 每日收益率 | `当日净值 / 前一日净值 - 1` |

### 风险指标

| 指标 | 说明 | 计算方式 |
|------|------|---------|
| **最大回撤** | 从高点到低点的最大跌幅 | `min(累计净值 / 前高 - 1)` |
| **波动率** | 年化波动率 | `日收益标准差 * sqrt(252)` |
| **夏普比率** | 风险调整后收益 | `(年化收益 - 无风险利率) / 年化波动率` |
| **索提诺比率** | 下行风险调整后收益 | `(年化收益 - 无风险利率) / 下行波动率` |

### 交易指标

| 指标 | 说明 | 计算方式 |
|------|------|---------|
| **胜率** | 盈利交易比例 | `盈利交易数 / 总交易数` |
| **盈亏比** | 平均盈利 / 平均亏损 | `avg(盈利) / avg(亏损)` |
| **换手率** | 日均换手率 | `日均成交额 / 组合市值` |
| **交易次数** | 总交易次数 | 累计交易笔数 |

### 综合指标

| 指标 | 说明 | 阈值 |
|------|------|------|
| **Calmar比率** | 年化收益 / 最大回撤 | >1.0 |
| **MAR比率** | 年化收益 / 最大回撤 | >1.5 |
| **Omega比率** | 收益分布的风险收益比 | >1.0 |

---

## 回测结果解读

### 示例输出

```json
{
  "strategy": "momentum",
  "ticker": "600519",
  "total_return": 0.235,
  "annual_return": 0.182,
  "sharpe_ratio": 1.28,
  "max_drawdown": -0.125,
  "win_rate": 0.58,
  "total_trades": 45,
  "turnover": 0.85,
  "calmar_ratio": 1.46
}
```

### 解读标准

| 指标 | 优秀 | 良好 | 一般 | 较差 |
|------|------|------|------|------|
| 总收益 | >30% | 10-30% | 0-10% | <0% |
| 年化收益 | >20% | 10-20% | 0-10% | <0% |
| 夏普比率 | >1.5 | 1.0-1.5 | 0.5-1.0 | <0.5 |
| 最大回撤 | <10% | 10-15% | 15-20% | >20% |
| 胜率 | >60% | 55-60% | 50-55% | <50% |

---

## 回测陷阱

### 1. 未来信息泄露

**问题**：使用了未来数据计算因子或信号

**示例**：
```python
# 错误：使用未来数据计算均值
df["ma_20"] = df["close"].rolling(20).mean()  # OK，rolling是向后看

# 错误：使用了还未发生的数据
df["next_day_return"] = df["close"].shift(-1).pct_change()  # 这是未来信息！
```

**检测方法**：
- 检查因子计算是否只使用 `shift()` 或 `rolling()`
- 确保因子值在当天收盘后才能确定
- 使用时间戳验证

### 2. 过度拟合

**问题**：参数过于优化，在样本外表现差

**表现**：
- 回测收益很高，但实盘表现差
- 参数在微小变化时收益大幅波动
- 交易次数过多

**避免方法**：
- 使用样本外测试
- 使用 Walk-Forward 验证
- 限制参数搜索空间
- 考虑交易成本

### 3. 幸存者偏差

**问题**：只测试了存活下来的股票

**示例**：
- 只测试当前沪深300成分股
- 忽略了已经退市的股票

**避免方法**：
- 使用历史成分股数据
- 在回测时考虑股票退市

### 4. 前视偏差

**问题**：使用了当时不可获得的信息

**示例**：
- 使用季度财报数据，但财报还未发布
- 使用未来的股票拆分信息

**避免方法**：
- 使用财报发布日期
- 延迟使用基本面数据

### 5. 交易成本忽略

**问题**：忽略了手续费、印花税、滑点

**影响**：
- 高频策略收益被成本吞噬
- 实际收益远低于回测收益

**处理方法**：
```python
# 考虑交易成本
fees = 0.001  # 手续费
slippage = 0.001  # 滑点
stamp_tax = 0.001  # 印花税（卖出时）

total_cost = fees + slippage + stamp_tax
```

---

## Walk-Forward 验证

### 方法概述

Walk-Forward 验证是一种更可靠的回测方法：

```
训练窗口 → 测试窗口 → 滚动前进
[------]  [--]
        [------]  [--]
                [------]  [--]
```

### 参数设置

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `train_window` | 252 | 训练窗口（交易日） |
| `test_window` | 63 | 测试窗口（交易日） |
| `step` | 21 | 步长（交易日） |

### 执行方式

```python
from research.backtest import BacktestEngine

# Walk-forward 验证
result = BacktestEngine.walk_forward(
    close=df["close"],
    signal_func=generate_signals,
    train_window=252,
    test_window=63,
    step=21
)
```

### 结果解读

Walk-Forward 验证输出多个测试窗口的结果：

```json
{
  "walk_forward_results": [
    {"period": "2024Q1", "sharpe": 1.2, "return": 0.05},
    {"period": "2024Q2", "sharpe": 1.1, "return": 0.04},
    {"period": "2024Q3", "sharpe": 1.3, "return": 0.06},
    {"period": "2024Q4", "sharpe": 1.0, "return": 0.03}
  ],
  "average_sharpe": 1.15,
  "worst_sharpe": 1.0,
  "best_sharpe": 1.3
}
```

---

## 参数扫描

### 网格搜索

```python
from itertools import product

params = {
    "lookback": [10, 20, 60],
    "entry_threshold": [0.03, 0.05, 0.08],
    "exit_threshold": [-0.01, -0.02, -0.03]
}

best_result = None
best_params = None

for lookback, entry, exit in product(*params.values()):
    config = {"lookback": lookback, "entry_threshold": entry, "exit_threshold": exit}
    strategy = MomentumStrategy(config)
    result = engine.run(strategy, df)
    
    if best_result is None or result["sharpe_ratio"] > best_result["sharpe_ratio"]:
        best_result = result
        best_params = config

print(f"最佳参数: {best_params}")
print(f"最佳夏普: {best_result['sharpe_ratio']}")
```

### 参数重要性

使用热力图或柱状图展示参数影响：

| 参数 | 影响程度 | 说明 |
|------|---------|------|
| `lookback` | 高 | 回看周期决定信号频率 |
| `entry_threshold` | 中 | 入场阈值决定信号数量 |
| `exit_threshold` | 中 | 出场阈值决定止损程度 |
| `max_position` | 高 | 仓位大小决定风险 |

---

## 基准选择

### 常见基准

| 基准 | 说明 | 适用场景 |
|------|------|---------|
| **沪深300** | 大盘基准 | 全市场策略 |
| **中证500** | 中小盘基准 | 中小盘策略 |
| **行业指数** | 行业基准 | 行业策略 |
| **无风险利率** | 国债收益率 | 绝对收益策略 |

### 基准对比

```python
# 计算相对收益
strategy_return = result["total_return"]
benchmark_return = benchmark["total_return"]
alpha = strategy_return - benchmark_return

print(f"策略收益: {strategy_return:.2%}")
print(f"基准收益: {benchmark_return:.2%}")
print(f"Alpha: {alpha:.2%}")
```

---

## 回测可视化

### 权益曲线

```python
import matplotlib.pyplot as plt

equity = result["equity_curve"]
benchmark_equity = benchmark["equity_curve"]

plt.figure(figsize=(12, 6))
plt.plot(equity, label="策略")
plt.plot(benchmark_equity, label="基准")
plt.title("权益曲线")
plt.legend()
plt.savefig("equity_curve.png")
```

### 回撤曲线

```python
drawdown = result["drawdown"]

plt.figure(figsize=(12, 6))
plt.fill_between(drawdown.index, drawdown.values, 0, alpha=0.3)
plt.plot(drawdown, label="回撤")
plt.title("回撤曲线")
plt.savefig("drawdown.png")
```

### 月度收益热力图

```python
import seaborn as sns

monthly_returns = result["monthly_returns"]
sns.heatmap(monthly_returns, annot=True, fmt=".1%", cmap="RdYlGn")
plt.title("月度收益热力图")
plt.savefig("monthly_heatmap.png")
```

---

## 实盘偏差分析

### 偏差来源

| 来源 | 说明 | 影响 |
|------|------|------|
| **滑点** | 实际成交价格与预期不同 | 收益降低 |
| **流动性** | 无法按预期数量成交 | 仓位不足 |
| **延迟** | 信号生成到执行的时间差 | 价格变化 |
| **市场冲击** | 大额订单影响市场价格 | 成本增加 |

### 偏差监控

```python
# 计算回测与实盘的偏差
backtest_return = 0.235
live_return = 0.182

deviation = live_return - backtest_return
print(f"偏差: {deviation:.2%}")

# 分析偏差原因
if deviation < -0.05:
    print("警告：实盘收益显著低于回测")
    print("建议检查：滑点、流动性、交易成本")
```

---

## 回测检查清单

- [ ] 数据是否包含未来信息？
- [ ] 是否考虑了交易成本和滑点？
- [ ] 是否使用了样本外测试？
- [ ] 是否考虑了幸存者偏差？
- [ ] 参数是否过度优化？
- [ ] 是否使用了正确的基准？
- [ ] 权益曲线是否合理？
- [ ] 最大回撤是否可接受？
- [ ] 换手率是否过高？
- [ ] 是否有足够的交易次数？

---

## 最佳实践

### 1. 严格的数据时间戳

确保所有数据都有正确的时间戳，避免使用未来数据。

### 2. 保守的成本假设

使用比实际更高的成本假设，确保策略在最坏情况下也能盈利。

### 3. 充足的样本量

至少使用 3-5 年的历史数据，覆盖不同市场周期。

### 4. 多样化的测试

在不同市场环境下测试策略，确保鲁棒性。

### 5. 透明的记录

记录所有回测参数和结果，便于复现和审计。

---

## 高级验证方法

### IVS 检验（参数鲁棒性）

IVS 检验用于评估参数的鲁棒性，通过在参数空间中随机采样来检验策略表现的稳定性：

```python
def ivs_test(strategy, data, param_ranges, n_samples=100):
    results = []
    for _ in range(n_samples):
        params = {k: np.random.uniform(*v) for k, v in param_ranges.items()}
        strategy.set_params(params)
        result = run_backtest(strategy, data)
        results.append(result["sharpe_ratio"])
    
    return {
        "mean_sharpe": np.mean(results),
        "std_sharpe": np.std(results),
        "robustness": np.mean([r > 0.5 for r in results])
    }
```

### Monte Carlo 模拟

Block Bootstrap 用于评估策略收益的统计显著性：

```python
def block_bootstrap(returns, n_simulations=1000, block_size=21):
    n_blocks = len(returns) // block_size
    bootstrapped_returns = []
    
    for _ in range(n_simulations):
        blocks = np.random.randint(0, n_blocks, n_blocks)
        bootstrapped = []
        for b in blocks:
            start = b * block_size
            end = start + block_size
            bootstrapped.extend(returns[start:end])
        bootstrapped_returns.append(np.mean(bootstrapped[:len(returns)]))
    
    return {
        "mean_return": np.mean(bootstrapped_returns),
        "p_value": np.mean([r > 0 for r in bootstrapped_returns])
    }
```

### 统计检验

**Ljung-Box 检验**：检验收益序列的自相关性

```python
from statsmodels.stats.diagnostic import acorr_ljungbox

def ljung_box_test(returns, lags=20):
    result = acorr_ljungbox(returns.dropna(), lags=lags)
    return {
        "p_values": result["lb_pvalue"].tolist(),
        "is_random": all(p > 0.05 for p in result["lb_pvalue"])
    }
```

### 多指标综合评估

| 指标 | 权重 | 说明 |
|------|------|------|
| 夏普比率 | 0.3 | 风险调整后收益 |
| 最大回撤 | 0.2 | 风险控制 |
| 胜率 | 0.15 | 交易成功率 |
| 盈亏比 | 0.15 | 收益风险比 |
| 稳健性 | 0.1 | 参数鲁棒性 |
| 统计显著性 | 0.1 | 收益显著性 |

---

## 过拟合检测

### 检测方法

| 方法 | 说明 | 阈值 |
|------|------|------|
| 样本内外差异 | 样本内 vs 样本外收益差 | <10% |
| 参数敏感度 | 参数微小变化导致收益大幅波动 | 否 |
| 交易次数 | 交易次数过多 | <50次/年 |

### 检测流程

```python
def detect_overfitting(backtest_result, walk_forward_result):
    flags = []
    
    in_sample_sharpe = backtest_result["sharpe_ratio"]
    out_sample_sharpe = walk_forward_result["average_sharpe"]
    if in_sample_sharpe / out_sample_sharpe > 1.5:
        flags.append("样本内外差异过大")
    
    trades_per_year = backtest_result["total_trades"] / (
        (pd.to_datetime(backtest_result["end_date"]) - 
         pd.to_datetime(backtest_result["start_date"])).days / 365
    )
    if trades_per_year > 100:
        flags.append("交易次数过多")
    
    return {
        "overfitting": len(flags) > 0,
        "flags": flags,
        "risk_level": "high" if len(flags) >= 2 else "medium" if len(flags) == 1 else "low"
    }
```

---

## 参考

- [回测引擎源码](file:///home/edalab/Desktop/cme_code/quant-system/QuantAgent/research/backtest.py)
- [Walk-Forward 验证](file:///home/edalab/Desktop/cme_code/quant-system/QuantAgent/research/walk_forward.py)
- [回测指标计算](file:///home/edalab/Desktop/cme_code/quant-system/QuantAgent/research/metrics.py)
