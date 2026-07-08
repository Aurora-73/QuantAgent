# 数据模型文档

> 统一数据契约 — 所有模块共享的核心类型定义。

---

## 设计原则

1. **所有模块依赖这些类型，不直接依赖第三方对象**
2. **第三方对象在适配器层转换为这些类型**
3. **字段命名统一：symbol, timestamp, source, market**

---

## 枚举类型

### Direction
交易方向

| 值 | 说明 |
|----|------|
| `LONG` | 多头 |
| `SHORT` | 空头 |

### OrderSide
订单方向

| 值 | 说明 |
|----|------|
| `BUY` | 买入 |
| `SELL` | 卖出 |

### OrderType
订单类型

| 值 | 说明 |
|----|------|
| `LIMIT` | 限价单 |
| `MARKET` | 市价单 |

### OrderStatus
订单状态

| 值 | 说明 |
|----|------|
| `PENDING` | 待提交 |
| `SUBMITTED` | 已提交 |
| `PARTIAL` | 部分成交 |
| `FILLED` | 全部成交 |
| `CANCELLED` | 已取消 |
| `REJECTED` | 已拒绝 |

### SignalStrength
信号强度

| 值 | 说明 |
|----|------|
| `STRONG` | 强信号 |
| `MODERATE` | 中等信号 |
| `WEAK` | 弱信号 |
| `NONE` | 无信号 |

### Sentiment
情绪类型

| 值 | 说明 |
|----|------|
| `POSITIVE` | 正面 |
| `NEGATIVE` | 负面 |
| `NEUTRAL` | 中性 |

### RuntimeMode
运行模式

| 值 | 说明 |
|----|------|
| `RESEARCH` | 研究模式 |
| `PAPER` | 模拟盘模式 |
| `LIVE` | 实盘模式 |

---

## 行情数据

### Bar — K线

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `symbol` | str | 是 | 股票代码 |
| `timestamp` | datetime | 是 | 时间戳 |
| `open` | float | 是 | 开盘价 |
| `high` | float | 是 | 最高价 |
| `low` | float | 是 | 最低价 |
| `close` | float | 是 | 收盘价 |
| `volume` | float | 是 | 成交量 |
| `amount` | float | 否 | 成交额 |
| `turnover` | float | 否 | 换手率 |
| `source` | str | 否 | 数据源 |
| `adjust` | str | 否 | 复权类型（qfq/hfq/""） |

**示例**：
```python
Bar(
    symbol="600519",
    timestamp=datetime(2024, 1, 15, 15, 0, 0),
    open=1680.0,
    high=1695.0,
    low=1675.0,
    close=1690.0,
    volume=500000,
    amount=845000000.0,
    turnover=0.02,
    source="akshare",
    adjust="qfq"
)
```

### Quote — 实时报价

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `symbol` | str | 是 | 股票代码 |
| `timestamp` | datetime | 是 | 时间戳 |
| `last` | float | 是 | 最新价 |
| `bid` | float | 否 | 买一价 |
| `ask` | float | 否 | 卖一价 |
| `volume` | float | 否 | 成交量 |
| `source` | str | 否 | 数据源 |

---

## 基本面数据

### FundamentalRecord — 基本面记录

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `symbol` | str | 是 | 股票代码 |
| `timestamp` | datetime | 是 | 报告日期 |
| `report_type` | str | 否 | 报告类型（annual/quarterly） |
| `revenue` | float | 否 | 营收 |
| `net_profit` | float | 否 | 净利润 |
| `pe` | float | 否 | 市盈率 |
| `pb` | float | 否 | 市净率 |
| `roe` | float | 否 | ROE |
| `source` | str | 否 | 数据源 |

---

## 新闻与事件

### NewsItem — 新闻条目

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `title` | str | 是 | 标题 |
| `timestamp` | datetime | 是 | 发布时间 |
| `source` | str | 是 | 来源（东方财富/财联社等） |
| `url` | str | 否 | 原文链接 |
| `content` | str | 否 | 内容 |
| `symbols` | list[str] | 否 | 关联股票代码列表 |
| `sentiment` | Sentiment | 否 | 情绪分类 |

### Event — 结构化事件

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `event_id` | str | 是 | 事件唯一ID |
| `event_type` | str | 是 | 事件类型 |
| `symbol` | str | 是 | 关联股票代码 |
| `timestamp` | datetime | 是 | 事件时间 |
| `detail` | str | 是 | 事件详情 |
| `sentiment` | Sentiment | 否 | 情绪分类 |
| `confidence` | float | 否 | 置信度（0-1） |
| `source` | str | 否 | 来源 |
| `tags` | list[str] | 否 | 标签列表 |
| `company` | str | 否 | 公司名称 |
| `impact_horizon` | str | 否 | 影响周期（short/medium/long） |

---

## 特征与信号

### FeatureVector — 因子/特征向量

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `symbol` | str | 是 | 股票代码 |
| `timestamp` | datetime | 是 | 时间戳 |
| `features` | dict[str, float] | 否 | 因子值字典 |
| `source` | str | 否 | 来源 |

**示例**：
```python
FeatureVector(
    symbol="600519",
    timestamp=datetime(2024, 1, 15),
    features={
        "momentum_20d": 0.085,
        "rsi_14": 62.5,
        "volatility_20d": 0.021
    },
    source="factor_calculator"
)
```

### Signal — 交易信号

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `symbol` | str | 是 | 股票代码 |
| `timestamp` | datetime | 是 | 时间戳 |
| `direction` | Direction | 是 | 交易方向 |
| `strength` | SignalStrength | 是 | 信号强度 |
| `score` | float | 是 | 信号分数（-1.0 ~ +1.0） |
| `source` | str | 是 | 来源（因子名/策略名/LLM） |
| `reason` | str | 否 | 信号原因 |
| `confidence` | float | 否 | 置信度（0-1） |

---

## 订单与成交

### Order — 订单

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `order_id` | str | 是 | 订单唯一ID |
| `symbol` | str | 是 | 股票代码 |
| `side` | OrderSide | 是 | 买卖方向 |
| `order_type` | OrderType | 是 | 订单类型 |
| `price` | float | 是 | 价格 |
| `volume` | float | 是 | 数量 |
| `filled_volume` | float | 否 | 已成交数量 |
| `status` | OrderStatus | 否 | 订单状态 |
| `timestamp` | datetime | 否 | 创建时间 |
| `source` | str | 否 | 来源 |
| `strategy_id` | str | 否 | 策略ID |

### Fill — 成交

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `fill_id` | str | 是 | 成交唯一ID |
| `order_id` | str | 是 | 关联订单ID |
| `symbol` | str | 是 | 股票代码 |
| `side` | OrderSide | 是 | 买卖方向 |
| `price` | float | 是 | 成交价格 |
| `volume` | float | 是 | 成交数量 |
| `timestamp` | datetime | 否 | 成交时间 |
| `commission` | float | 否 | 佣金 |
| `slippage` | float | 否 | 滑点 |

---

## 持仓与组合

### Position — 持仓

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `symbol` | str | 是 | 股票代码 |
| `direction` | Direction | 是 | 持仓方向 |
| `volume` | float | 是 | 持仓数量 |
| `avg_cost` | float | 是 | 平均成本 |
| `market_value` | float | 否 | 市值 |
| `unrealized_pnl` | float | 否 | 未实现盈亏 |
| `realized_pnl` | float | 否 | 已实现盈亏 |

### PortfolioSnapshot — 组合快照

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `timestamp` | datetime | 是 | 时间戳 |
| `positions` | list[Position] | 否 | 持仓列表 |
| `cash` | float | 否 | 现金 |
| `total_value` | float | 否 | 总资产 |
| `daily_pnl` | float | 否 | 当日盈亏 |
| `drawdown` | float | 否 | 回撤 |
| `source` | str | 否 | 来源 |

---

## 研究输出

### ResearchReport — 研究报告

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `report_id` | str | 是 | 报告唯一ID |
| `report_type` | str | 是 | 报告类型（daily/weekly/monthly/event） |
| `timestamp` | datetime | 是 | 时间戳 |
| `title` | str | 是 | 标题 |
| `summary` | str | 是 | 摘要 |
| `sentiment` | Sentiment | 否 | 情绪分类 |
| `confidence` | float | 否 | 置信度 |
| `key_points` | list[str] | 否 | 关键点列表 |
| `risk_flags` | list[str] | 否 | 风险标记 |
| `symbols` | list[str] | 否 | 关联股票 |
| `source` | str | 否 | 来源 |

### Hypothesis — 投资假设

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `hypothesis_id` | str | 是 | 假设唯一ID |
| `description` | str | 是 | 假设描述 |
| `timestamp` | datetime | 是 | 创建时间 |
| `metrics` | list[str] | 否 | 评估指标 |
| `status` | str | 否 | 状态（pending/verified/rejected） |
| `result` | str | 否 | 验证结果 |
| `source` | str | 否 | 来源 |

---

## 回测结果

### BacktestResult — 回测结果

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `strategy_id` | str | 是 | 策略ID |
| `start_date` | str | 是 | 开始日期 |
| `end_date` | str | 是 | 结束日期 |
| `total_return` | float | 否 | 总收益 |
| `annual_return` | float | 否 | 年化收益 |
| `sharpe_ratio` | float | 否 | 夏普比率 |
| `max_drawdown` | float | 否 | 最大回撤 |
| `win_rate` | float | 否 | 胜率 |
| `total_trades` | int | 否 | 交易次数 |
| `turnover` | float | 否 | 换手率 |
| `params` | dict | 否 | 参数配置 |

---

## 风控

### RiskDecision — 风控决策

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `approved` | bool | 是 | 是否通过 |
| `violations` | list[str] | 否 | 违规项列表 |
| `warnings` | list[str] | 否 | 警告项列表 |
| `adjusted_orders` | list[Order] | 否 | 调整后的订单 |

---

## 告警

### Alert — 告警

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `alert_id` | str | 是 | 告警唯一ID |
| `timestamp` | datetime | 是 | 时间戳 |
| `level` | str | 是 | 级别（info/warning/critical） |
| `alert_type` | str | 是 | 告警类型 |
| `title` | str | 是 | 标题 |
| `detail` | str | 是 | 详情 |
| `source` | str | 否 | 来源 |
| `acknowledged` | bool | 否 | 是否已确认 |

---

## DuckDB 表结构

### 数据分层

| 层级 | 说明 | 表前缀 |
|------|------|--------|
| `raw` | 原始数据 | `raw_*` |
| `cleaned` | 清洗后数据 | `cleaned_*` |
| `research` | 研究数据 | `research.*` |
| `published` | 发布数据 | `published.*` |

### 核心表

> 行数为快照性质，**以 `python -m scripts.db_stats` 实时输出为准**。下表仅列说明，不固化行数。

| 表名 | 说明 |
|------|------|
| `stock_daily` | 股票日线数据 |
| `index_daily` | 指数日线数据 |
| `factors` | 因子值（注册 29 个，实际计算数以 db_stats 为准） |
| `financials` | 基本面数据 |
| `news` | 新闻数据 |
| `events` | 事件数据 |
| `backtest_runs` | 回测记录 |
| `equity_curve` | 权益曲线 |

---

## 数据流转流程

```
AKShare / baostock → raw_stock_daily → cleaned_stock_daily → stock_daily
                                                              ↓
                                                    FactorCalculator
                                                              ↓
                                                         factors
                                                              ↓
                                                    StrategyEngine → signals
                                                              ↓
                                                    RiskEngine → orders
                                                              ↓
                                                    BacktestEngine → backtest_runs
                                                              ↓
                                                    ResearchReportGenerator → knowledge/daily/
```

---

## 使用示例

```python
from data.schema import Bar, Signal, Order, Position

# 创建K线
bar = Bar(
    symbol="600519",
    timestamp=datetime(2024, 1, 15),
    open=1680.0,
    high=1695.0,
    low=1675.0,
    close=1690.0,
    volume=500000
)

# 创建信号
signal = Signal(
    symbol="600519",
    timestamp=datetime(2024, 1, 15),
    direction=Direction.LONG,
    strength=SignalStrength.MODERATE,
    score=0.65,
    source="momentum_20d",
    reason="20日动量为正且大于5%"
)

# 创建订单
order = Order(
    order_id="ORD-20240115-001",
    symbol="600519",
    side=OrderSide.BUY,
    order_type=OrderType.LIMIT,
    price=1690.0,
    volume=1000
)
```
