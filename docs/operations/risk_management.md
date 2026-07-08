# 风控体系文档

> 生成日期：2026-07-06 | 最后更新：2026-07-07 | 适用场景：风险控制体系说明

---

## 风控架构

### 三层风控体系

```
事前风控 → 事中风控 → 事后风控
   ↓          ↓          ↓
 规则检查  实时监控   归因分析
   ↓          ↓          ↓
 订单拦截  熔断机制   策略调整
```

### 风控引擎

```python
from risk.risk_engine import RiskEngine

engine = RiskEngine()

# 事前风控检查 - 检查订单是否违反风控规则
result = engine.check_orders(orders, portfolio, market_data)

# 事中风控监控 - 检查回撤是否触发熔断
drawdown_result = engine.check_drawdown(equity_curve)

# 事中风控监控 - 检查日亏损是否超过限额
daily_loss_result = engine.check_daily_loss(daily_return)
```

---

## 事前风控规则

### 1. 仓位限制

| 规则 | 参数 | 默认值 | 说明 |
|------|------|--------|------|
| **单只股票最大仓位** | `max_single_position` | 5% | 单票上限 |
| **单行业最大敞口** | `max_sector_exposure` | 20% | 行业集中度 |
| **总敞口上限** | `max_total_exposure` | 100% | 杠杆限制 |

### 2. 流动性限制

| 规则 | 参数 | 默认值 | 说明 |
|------|------|--------|------|
| **最小日成交量** | `min_daily_volume` | 5000万 | 流动性筛选 |
| **最大换手率** | `max_daily_turnover` | 10% | 换手率控制 |

### 3. 风险限制

| 规则 | 参数 | 默认值 | 说明 |
|------|------|--------|------|
| **最大回撤** | `max_drawdown_stop` | -5% | 回撤熔断 |
| **日亏损限额** | `daily_loss_limit` | -2% | 单日亏损限制 |
| **连续亏损次数** | `consecutive_losses_limit` | 5次 | 连续亏损限制 |
| **波动率上限** | `volatility_cap` | 3.0 | 波动率突增限制 |

### 4. 合规限制

| 规则 | 说明 |
|------|------|
| **涨跌停限制** | A股涨跌停±10%，ST股±5% |
| **持仓限制** | 单一股票不超过流通股的5% |
| **交易时间** | 9:30-11:30, 13:00-15:00 |

---

## 风控检查流程

### 检查步骤

```python
from risk.risk_engine import RiskEngine, RiskReport

engine = RiskEngine()

# 检查订单是否违反风控规则
result = engine.check_orders(
    orders=orders,
    portfolio=[
        {"ticker": "600519", "weight": 0.04, "sector": "消费"},
        {"ticker": "300750", "weight": 0.03, "sector": "科技"}
    ],
    market_data=market_data
)

# 检查结果包含：
# - passed: 是否通过
# - violations: 违规列表 (rule, ticker, detail, severity)
# - adjusted: 是否有调整
# - notes: 备注信息

if result.passed:
    print("风控检查通过")
else:
    print(f"风控检查未通过: {len(result.violations)} 条违规")
    for v in result.violations:
        print(f"  [{v.severity}] {v.rule}: {v.ticker} - {v.detail}")
```

### 处理策略

| 结果 | 处理方式 |
|------|---------|
| **通过** | 订单正常执行 |
| **警告** | 订单执行，但发送告警 |
| **违规** | 订单被拦截或调整 |
| **熔断** | 停止所有开仓，可选强制平仓 |

---

## 事中风控

### 实时监控

```python
from risk.risk_engine import RiskEngine

engine = RiskEngine()

# 检查回撤是否触发熔断
drawdown_result = engine.check_drawdown(equity_curve)
if not drawdown_result.passed:
    for v in drawdown_result.violations:
        print(f"[CRITICAL] 回撤熔断: {v.detail}")

# 检查日亏损是否超过限额
daily_loss_result = engine.check_daily_loss(daily_return)
if not daily_loss_result.passed:
    for v in daily_loss_result.violations:
        print(f"[CRITICAL] 日亏损超限: {v.detail}")

# 检查订单是否违反风控规则
order_result = engine.check_orders(orders, portfolio, market_data)
if not order_result.passed:
    for v in order_result.violations:
        level = "CRITICAL" if v.severity == "block" else "WARNING"
        print(f"[{level}] {v.rule}: {v.ticker} - {v.detail}")
```

### 熔断机制

| 触发条件 | 熔断级别 | 处理方式 |
|---------|---------|---------|
| 回撤 > -5% | Level 1 | 停止开新仓 |
| 回撤 > -10% | Level 2 | 强制平仓50% |
| 回撤 > -15% | Level 3 | 强制全部平仓 |
| 日亏损 > -2% | Level 1 | 停止开新仓 |
| 连续亏损5次 | Level 1 | 停止开新仓，审查策略 |

---

## 事后风控

### Brinson 归因分析

```bash
python -m scripts brinson --ticker 600519,300750 --benchmark 000300
```

**归因结果**：
```json
{
  "total_return": 0.15,
  "benchmark_return": 0.10,
  "excess_return": 0.05,
  "attribution": {
    "allocation_effect": 0.025,    # 配置效应
    "selection_effect": 0.015,     # 选股效应
    "interaction_effect": 0.010    # 交互效应
  },
  "sector_attribution": {
    "金融": {"allocation": 0.01, "selection": 0.005},
    "消费": {"allocation": 0.008, "selection": 0.006},
    "科技": {"allocation": 0.007, "selection": 0.004}
  }
}
```

### 策略衰减检测

```bash
python -m scripts decay-detect --strategy momentum --period 60
```

**衰减结果**：
```json
{
  "strategy": "momentum",
  "current_ic": 0.045,
  "historical_ic": 0.052,
  "ic_decay": 0.13,
  "half_life": 10,
  "status": "stable"  # stable / decaying / critical
}
```

---

## 压力测试

### 测试场景

| 场景 | 说明 | 参数 |
|------|------|------|
| **熊市** | 大盘下跌20% | market_return=-0.20 |
| **暴跌** | 单日下跌5% | daily_return=-0.05 |
| **流动性危机** | 成交量萎缩50% | volume_shrinkage=0.5 |
| **波动率飙升** | 波动率翻倍 | volatility_multiplier=2.0 |
| **行业冲击** | 特定行业下跌30% | sector_return=-0.30 |

### 执行命令

```bash
python -m scripts stress-test --ticker 600519 --scenario bear_market
python -m scripts stress-test --ticker 600519 --scenario flash_crash
```

### 测试结果

```json
{
  "scenario": "bear_market",
  "strategy": "momentum",
  "stress_return": -0.18,
  "normal_return": 0.05,
  "stress_drawdown": -0.25,
  "normal_drawdown": -0.12,
  "max_drawdown_in_stress": -0.28,
  "violations": ["max_drawdown"],
  "impact": "high"
}
```

---

## 组合优化

### 目标函数

系统使用 Riskfolio-Lib 进行组合优化：

```python
from risk.portfolio import PortfolioOptimizer

optimizer = PortfolioOptimizer()

# 最大化夏普比率
weights = optimizer.maximize_sharpe(
    returns=returns,
    cov_matrix=cov_matrix,
    constraints={
        "max_single_position": 0.05,
        "max_sector_exposure": 0.20
    }
)

# 最小化风险
weights = optimizer.minimize_risk(
    returns=returns,
    target_return=0.15,
    constraints={}
)

# 风险预算
weights = optimizer.risk_budget(
    returns=returns,
    budgets={"600519": 0.2, "300750": 0.3, "002475": 0.5}
)
```

### 约束条件

| 约束 | 说明 |
|------|------|
| **单票上限** | 单只股票最大权重 |
| **行业上限** | 单行业最大权重 |
| **总敞口** | 总权重不超过100% |
| **权重范围** | 每只股票权重范围 |
| **交易成本** | 考虑交易成本 |

---

## 风控指标仪表盘

### 核心指标

| 指标 | 当前值 | 阈值 | 状态 |
|------|--------|------|------|
| 总收益 | 15% | - | ✅ |
| 最大回撤 | -8% | -15% | ✅ |
| 夏普比率 | 1.3 | 1.0 | ✅ |
| 单票最大仓位 | 4.5% | 5% | ✅ |
| 行业最大敞口 | 18% | 20% | ✅ |
| 日亏损 | -1.2% | -2% | ✅ |
| 换手率 | 8% | 10% | ✅ |

### 告警历史

```
2026-07-02 14:30  [WARNING] 波动率突增，当前波动率是正常水平的2.1倍
2026-06-30 10:15  [CRITICAL] 日亏损-2.1%，超过阈值-2%，已触发熔断
2026-06-28 16:00  [WARNING] 600519 流动性不足，建议减仓
```

---

## 风控规则配置

### 自定义规则

```yaml
# configs/app.yaml
risk:
  # 仓位限制
  max_single_position: 0.05
  max_sector_exposure: 0.20
  max_total_exposure: 1.00
  
  # 流动性限制
  min_daily_volume: 50000000
  max_daily_turnover: 0.10
  
  # 风险限制
  max_drawdown_stop: -0.05
  daily_loss_limit: -0.02
  consecutive_losses_limit: 5
  volatility_cap: 3.0
  
  # 熔断配置
  drawdown_level1: -0.05
  drawdown_level2: -0.10
  drawdown_level3: -0.15
```

---

## 最佳实践

### 1. 双重风控

策略级风控 + 全局风控双重保障，避免单点故障。

### 2. 动态调整

根据市场状态动态调整风控参数：
- 高波动期：收紧仓位限制
- 低波动期：适度放宽

### 3. 压力测试

定期进行压力测试，确保策略在极端情况下的表现。

### 4. 归因分析

定期进行 Brinson 归因，了解超额收益来源。

### 5. 熔断机制

明确的熔断机制，避免大幅亏损。

---

## 常见问题

### Q: 风控过于严格怎么办？

**解决方案**：
- 根据策略类型调整参数
- 使用动态风控（根据市场状态调整）
- 分阶段逐步放宽

### Q: 风控过于宽松怎么办？

**解决方案**：
- 回顾历史最大回撤
- 设定更严格的参数
- 添加额外的风控规则

### Q: 如何处理流动性不足的股票？

**解决方案**：
- 在选股阶段筛选流动性
- 限制单票仓位
- 使用 VWAP 算法下单
- 分拆订单

---

## 参考

- [风控引擎源码](file:///home/edalab/Desktop/cme_code/quant-system/QuantAgent/risk/risk_engine.py)
- [组合优化](file:///home/edalab/Desktop/cme_code/quant-system/QuantAgent/risk/portfolio.py)
- [压力测试](file:///home/edalab/Desktop/cme_code/quant-system/QuantAgent/risk/stress_test.py)
- [Brinson 归因](file:///home/edalab/Desktop/cme_code/quant-system/QuantAgent/risk/brinson.py)
