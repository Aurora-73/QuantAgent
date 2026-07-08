# 策略开发指南

> 如何编写自定义策略。

---

## 策略架构

### 核心设计原则

1. **信号和执行分离** — 信号只表达方向，不表达仓位
2. **研究和实盘分离** — 同一策略可用于研究和实盘
3. **预测和仓位分离** — 预测值不直接等于仓位
4. **AI 和规则分离** — LLM 只做信息处理，不做决策

### 策略接口

每个策略必须实现 `StrategyBase` 的以下方法：

| 方法 | 说明 |
|------|------|
| `prepare_features()` | 准备特征（数据变换） |
| `generate_signal()` | 生成信号（方向和强度） |
| `position_sizing()` | 仓位计算（信号→交易指令） |
| `risk_check()` | 风控检查（策略级） |
| `expected_holding_period()` | 预期持仓周期 |
| `kill_switch_condition()` | 熔断条件 |

---

## 创建新策略

### 步骤 1：创建策略目录

```
strategies/
  my_strategy/
    __init__.py
    config.yaml
    strategy.py
```

### 步骤 2：编写策略代码

```python
from strategies.base.strategy_base import (
    StrategyBase, Direction, Signal, SignalStrength,
    Position, TradeOrder, RiskCheckResult
)
from strategies.registry import register_strategy

@register_strategy("my_strategy", 
                   description="我的自定义策略",
                   category="trend")
class MyStrategy(StrategyBase):
    def __init__(self, config: dict = None):
        super().__init__("my_strategy", config)
        self.lookback = config.get("lookback", 20)
        self.entry_threshold = config.get("entry_threshold", 0.05)
        self.exit_threshold = config.get("exit_threshold", -0.02)

    def prepare_features(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        df["momentum"] = df["close"].pct_change(self.lookback)
        df["ma_20"] = df["close"].rolling(20).mean()
        df["ma_deviation"] = (df["close"] - df["ma_20"]) / df["ma_20"]
        return df

    def generate_signal(self, features: pd.DataFrame, 
                        context: dict = None) -> list[Signal]:
        signals = []
        for idx, row in features.iterrows():
            momentum = row.get("momentum", 0)
            ma_dev = row.get("ma_deviation", 0)
            
            if momentum > self.entry_threshold and ma_dev > 0:
                signals.append(Signal(
                    ticker=row.get("ticker", ""),
                    direction=Direction.LONG,
                    strength=SignalStrength.MODERATE,
                    score=min(momentum, 1.0),
                    confidence=0.7,
                    source="momentum",
                    reason=f"动量{momentum:.2%}突破{self.entry_threshold:.0%}"
                ))
            elif momentum < self.exit_threshold:
                signals.append(Signal(
                    ticker=row.get("ticker", ""),
                    direction=Direction.FLAT,
                    strength=SignalStrength.WEAK,
                    score=0.0,
                    confidence=0.6,
                    source="momentum",
                    reason=f"动量{momentum:.2%}跌破{self.exit_threshold:.0%}"
                ))
        return signals

    def position_sizing(self, signals: list[Signal],
                        portfolio: list[Position],
                        total_capital: float) -> list[TradeOrder]:
        orders = []
        max_position = self.config.get("max_position", 0.05)
        
        for signal in signals:
            target_weight = signal.score * max_position
            current_pos = next((p for p in portfolio if p.ticker == signal.ticker), None)
            
            if signal.direction == Direction.LONG:
                target_value = total_capital * target_weight
                current_value = current_pos.market_value if current_pos else 0
                delta_value = target_value - current_value
                
                if delta_value > 0:
                    orders.append(TradeOrder(
                        ticker=signal.ticker,
                        direction=Direction.LONG,
                        target_shares=int(delta_value / signal.price),
                        order_type="market",
                        reason=signal.reason
                    ))
        return orders

    def risk_check(self, orders: list[TradeOrder],
                   portfolio: list[Position]) -> RiskCheckResult:
        violations = []
        warnings = []
        
        for order in orders:
            if order.target_shares < 100:
                warnings.append(f"{order.ticker}: 下单数量小于100股")
        
        return RiskCheckResult(
            passed=len(violations) == 0,
            violations=violations,
            warnings=warnings,
            adjusted_orders=orders
        )

    def expected_holding_period(self) -> dict:
        return {
            "min_days": 3,
            "max_days": 20,
            "typical_days": 10,
            "rebalance_freq": "daily"
        }

    def kill_switch_condition(self) -> dict:
        return {
            "max_drawdown": -0.05,
            "daily_loss_limit": -0.02,
            "consecutive_losses": 5,
            "volatility_spike": 3.0
        }
```

### 步骤 3：编写配置文件

```yaml
# strategies/my_strategy/config.yaml
lookback: 20
entry_threshold: 0.05
exit_threshold: -0.02
max_position: 0.05
rsi_overbought: 70
rsi_oversold: 30
```

### 步骤 4：编写 __init__.py

```python
from .strategy import MyStrategy

__all__ = ["MyStrategy"]
```

---

## 核心数据结构

### Signal — 交易信号

| 字段 | 类型 | 说明 |
|------|------|------|
| `ticker` | str | 股票代码 |
| `direction` | Direction | LONG/SHORT/FLAT |
| `strength` | SignalStrength | STRONG/MODERATE/WEAK/NONE |
| `score` | float | 原始分数 (-1 ~ +1) |
| `confidence` | float | 置信度 (0 ~ 1) |
| `source` | str | 来源 |
| `reason` | str | 生成理由 |

### WeightVector — 连续权重向量（推荐）

```python
WeightVector(
    weights={"600519": 0.05, "300750": 0.03, "002475": -0.02},
    confidence=0.8,
    source="momentum",
    reason="基于20日动量"
)
```

**权重含义**：
- `+1.0` = 满仓做多
- `0.0` = 空仓
- `-1.0` = 满仓做空

**优点**：多策略融合时直接加权平均，不需要离散信号转换。

### TradeOrder — 交易指令

| 字段 | 类型 | 说明 |
|------|------|------|
| `ticker` | str | 股票代码 |
| `direction` | Direction | LONG/SHORT |
| `target_shares` | int | 目标股数 |
| `order_type` | str | "limit" / "market" |
| `limit_price` | float | 限价（可选） |
| `reason` | str | 下单理由 |
| `urgency` | str | "low" / "normal" / "high" |

### RiskCheckResult — 风控检查结果

| 字段 | 类型 | 说明 |
|------|------|------|
| `passed` | bool | 是否通过 |
| `violations` | list | 违规项列表 |
| `warnings` | list | 警告项列表 |
| `adjusted_orders` | list | 调整后的订单 |

---

## 策略注册

使用 `@register_strategy` 装饰器注册策略：

```python
@register_strategy(
    name="momentum",
    description="动量突破策略",
    category="trend"
)
class MomentumStrategy(StrategyBase):
    ...
```

**策略分类**：

| 分类 | 说明 |
|------|------|
| `trend` | 趋势跟踪 |
| `reversal` | 反转策略 |
| `arbitrage` | 套利策略 |
| `event` | 事件驱动 |
| `meta` | 元策略（如市场状态切换） |

---

## 内置策略

### 1. Momentum — 动量策略

**逻辑**：买入近期上涨趋势确认的股票，卖出下跌趋势确认的股票。

**参数**：
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `lookback` | 20 | 回看周期（天） |
| `entry_threshold` | 0.05 | 入场阈值（5%） |
| `exit_threshold` | -0.02 | 出场阈值（-2%） |
| `rsi_overbought` | 70 | RSI超买 |
| `rsi_oversold` | 30 | RSI超卖 |

### 2. EventDriven — 事件驱动策略

**逻辑**：基于新闻事件生成交易信号，支持多事件叠加和时间衰减。

**参数**：
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `event_decay_half_life` | 5 | 事件衰减半衰期（天） |
| `min_confidence` | 0.7 | 最低置信度 |
| `max_events_per_day` | 10 | 每日最大事件数 |

### 3. Sentiment — 情绪策略

**逻辑**：基于社交情绪和新闻情绪生成信号，支持反指规则和情绪调制。

**参数**：
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `sentiment_threshold` | 0.3 | 情绪阈值 |
| `contrarian_window` | 3 | 反指窗口（天） |
| `sentiment_source` | "all" | 情绪来源 |

### 4. RegimeSwitch — 市场状态切换策略

**逻辑**：根据市场状态（牛市/熊市/震荡）选择不同的子策略。

**参数**：
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `regime_lookback` | 60 | 状态识别周期（天） |
| `cooling_period` | 5 | 状态切换冷却期（天） |
| `volatility_threshold` | 0.02 | 波动率阈值 |

---

## 策略融合

### 多策略融合

系统支持多策略加权融合：

```python
from strategies.momentum.strategy import MomentumStrategy
from strategies.sentiment.strategy import SentimentStrategy

# 创建策略实例
momentum = MomentumStrategy()
sentiment = SentimentStrategy()

# 生成权重向量
features = ...
weights_momentum = momentum.generate_weight_vector(features)
weights_sentiment = sentiment.generate_weight_vector(features)

# 加权融合 (动量0.6权重 + 情绪0.4权重)
combined_weights = {}
for ticker in set(weights_momentum.weights.keys()) | set(weights_sentiment.weights.keys()):
    w1 = weights_momentum.weights.get(ticker, 0) * 0.6
    w2 = weights_sentiment.weights.get(ticker, 0) * 0.4
    combined_weights[ticker] = w1 + w2

combined = WeightVector(
    weights=combined_weights,
    confidence=0.5 * weights_momentum.confidence + 0.5 * weights_sentiment.confidence,
    source="multi_strategy",
    reason="动量+情绪融合"
)
```

### 权重合约架构

系统采用权重合约架构，策略输出连续权重，由统一的执行引擎转换为订单：

```
Strategy A → WeightVector → ExecutionEngine → Orders
Strategy B → WeightVector → ExecutionEngine → Orders
Strategy C → WeightVector → ExecutionEngine → Orders
```

---

## 策略开发流程

### 标准流程

```
1. 定义策略假设 → 2. 编写策略代码 → 3. 回测验证 → 4. 参数优化 → 5. 样本外测试 → 6. 模拟盘运行 → 7. 实盘部署
```

### 开发检查清单

- [ ] 策略是否实现了所有必需的抽象方法？
- [ ] 信号生成是否只依赖规则，不依赖 LLM 直接决策？
- [ ] 仓位计算是否考虑了现有持仓？
- [ ] 风控检查是否实现了策略级规则？
- [ ] 熔断条件是否合理？
- [ ] 回测是否通过？
- [ ] 是否有样本外测试？

---

## 最佳实践

### 1. 信号生成

- 信号只表达方向和强度，不表达仓位大小
- 使用标准化的分数（-1 ~ +1）
- 提供置信度估计
- 使用清晰的理由说明

### 2. 仓位管理

- 考虑现有持仓，计算增量变化
- 遵守最小交易单位（100股）
- 考虑交易成本和滑点
- 使用权重而非固定数量

### 3. 风控

- 策略级风控 + 全局风控双重保障
- 单票仓位上限
- 行业集中度限制
- 换手率控制

### 4. 可测试性

- 每个策略应有对应的测试用例
- 测试数据应使用模拟数据或历史数据的子集
- 测试应覆盖正常和异常情况

---

## 常见问题

### Q: 如何调试策略？

```python
# 打印信号
signals = strategy.generate_signal(features)
for s in signals:
    print(f"{s.ticker}: {s.direction} {s.strength} score={s.score}")

# 打印权重向量
weights = strategy.generate_weight_vector(features)
print(weights.weights)

# 打印交易指令
orders = strategy.position_sizing(signals, portfolio, total_capital)
for o in orders:
    print(f"{o.ticker}: {o.direction} {o.target_shares}股")
```

### Q: 如何优化策略参数？

```python
# 使用网格搜索
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
    strategy = MyStrategy(config)
    result = run_backtest(strategy, data)
    
    if best_result is None or result["sharpe_ratio"] > best_result["sharpe_ratio"]:
        best_result = result
        best_params = config

print(f"最佳参数: {best_params}")
print(f"最佳夏普: {best_result['sharpe_ratio']}")
```

### Q: 如何处理数据缺失？

```python
def prepare_features(self, data: pd.DataFrame) -> pd.DataFrame:
    df = data.copy()
    
    # 填充缺失值
    df = df.fillna(method="ffill").fillna(method="bfill")
    
    # 检查数据质量
    if df.isnull().any().any():
        self.logger.warning("数据存在缺失值")
    
    # 计算特征
    df["momentum"] = df["close"].pct_change(self.lookback)
    
    return df
```

---

## 参考

- [StrategyBase 源码](file:///home/edalab/Desktop/cme_code/quant-system/QuantAgent/strategies/base/strategy_base.py)
- [策略注册表](file:///home/edalab/Desktop/cme_code/quant-system/QuantAgent/strategies/registry.py)
- [动量策略示例](file:///home/edalab/Desktop/cme_code/quant-system/QuantAgent/strategies/momentum/strategy.py)
