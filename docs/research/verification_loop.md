# 验证闭环

> 基于 loverMentor 的预测验证与决策记忆体系。

---

## 验证闭环架构

### 闭环流程

```
预测 → 执行 → 验证 → 反馈 → 调整
  ↓      ↓      ↓      ↓      ↓
 LLM   策略   回测   记忆   优化
```

### 核心组件

| 组件 | 说明 |
|------|------|
| **预测追踪** | 记录每个预测的 ID、时间、内容、置信度 |
| **决策记忆** | 记录每次决策的理由、结果、事后收益 |
| **经验积累** | 自动积累成功和失败的经验教训 |
| **反馈机制** | 根据验证结果调整策略参数 |

---

## 预测验证机制

### 预测追踪

```python
from verification.predictor_tracker import PredictorTracker

tracker = PredictorTracker()

# 记录预测
prediction_id = tracker.record(
    ticker="600519",
    prediction="未来5日上涨",
    confidence=0.7,
    source="LLM",
    timestamp="2026-07-02"
)

# 验证预测
result = tracker.verify(
    prediction_id=prediction_id,
    actual_return=0.03,
    timestamp="2026-07-07"
)

print(f"预测结果: {result['correct']}")
print(f"预测准确率: {result['accuracy']}")
```

### 预测格式

```json
{
  "prediction_id": "PRED-20260702-001",
  "ticker": "600519",
  "prediction": "未来5日上涨",
  "direction": "up",
  "confidence": 0.7,
  "source": "LLM",
  "created_at": "2026-07-02",
  "verified_at": "2026-07-07",
  "actual_return": 0.03,
  "correct": true,
  "horizon": "5d"
}
```

### 预测准确率

```bash
python -m scripts prediction-accuracy --source LLM --period 30
```

```json
{
  "source": "LLM",
  "total_predictions": 150,
  "correct_predictions": 82,
  "accuracy": 0.547,
  "accuracy_by_horizon": {
    "1d": 0.52,
    "5d": 0.55,
    "10d": 0.53,
    "20d": 0.51
  },
  "accuracy_by_confidence": {
    "low (<0.5)": 0.48,
    "medium (0.5-0.7)": 0.55,
    "high (>0.7)": 0.62
  }
}
```

---

## 决策记忆系统

### 决策记录

```python
from verification.decision_memory import DecisionMemory

memory = DecisionMemory()

# 记录决策
decision_id = memory.record(
    ticker="600519",
    action="buy",
    reason="20日动量突破5%",
    confidence=0.75,
    source="momentum_strategy",
    timestamp="2026-07-02",
    position_size=0.05
)

# 更新决策结果
memory.update(
    decision_id=decision_id,
    pnl_1d=0.012,
    pnl_3d=0.028,
    pnl_5d=0.035,
    pnl_10d=0.021,
    status="profitable"
)
```

### 决策格式

```json
{
  "decision_id": "DEC-20260702-001",
  "ticker": "600519",
  "action": "buy",
  "reason": "20日动量突破5%",
  "confidence": 0.75,
  "source": "momentum_strategy",
  "created_at": "2026-07-02",
  "position_size": 0.05,
  "results": {
    "pnl_1d": 0.012,
    "pnl_3d": 0.028,
    "pnl_5d": 0.035,
    "pnl_10d": 0.021
  },
  "status": "profitable"
}
```

### 决策分析

```bash
python -m scripts decision-analysis --strategy momentum --period 90
```

```json
{
  "strategy": "momentum",
  "total_decisions": 45,
  "profitable": 26,
  "loss": 19,
  "win_rate": 0.578,
  "avg_pnl_1d": 0.008,
  "avg_pnl_5d": 0.022,
  "avg_pnl_10d": 0.018,
  "best_reason": "20日动量突破5% + RSI < 70",
  "worst_reason": "20日动量突破5% + RSI > 70"
}
```

---

## 经验教训自动积累

### 成功经验

```python
from verification.lesson_learner import LessonLearner

learner = LessonLearner()

# 学习成功经验
learner.learn_success(
    ticker="600519",
    reason="20日动量突破5% + RSI < 70",
    pnl=0.035,
    context={
        "market_regime": "bull",
        "sector": "consumer",
        "volume": "high"
    }
)
```

### 失败教训

```python
# 学习失败教训
learner.learn_failure(
    ticker="300750",
    reason="20日动量突破5% + RSI > 70",
    pnl=-0.021,
    context={
        "market_regime": "bear",
        "sector": "tech",
        "volume": "low"
    }
)
```

### 经验库

```json
{
  "success_patterns": [
    {
      "pattern": "20日动量突破5% + RSI < 70 + 放量",
      "count": 15,
      "avg_pnl": 0.032,
      "win_rate": 0.73
    },
    {
      "pattern": "20日动量突破5% + 行业龙头",
      "count": 10,
      "avg_pnl": 0.028,
      "win_rate": 0.70
    }
  ],
  "failure_patterns": [
    {
      "pattern": "20日动量突破5% + RSI > 70",
      "count": 8,
      "avg_pnl": -0.025,
      "win_rate": 0.25
    },
    {
      "pattern": "20日动量突破5% + 低流动性",
      "count": 5,
      "avg_pnl": -0.018,
      "win_rate": 0.20
    }
  ]
}
```

---

## 信号权重反馈机制

### 动态权重调整

```python
from verification.signal_feedback import SignalFeedback

feedback = SignalFeedback()

# 更新信号权重
feedback.update(
    signal_source="momentum_20d",
    recent_performance=0.025,
    historical_performance=0.032,
    decay_rate=0.1
)

# 获取调整后的权重
weights = feedback.get_weights()

print(f"信号权重: {weights}")
```

### 权重调整规则

| 规则 | 说明 | 调整方式 |
|------|------|---------|
| **近期表现下降** | 连续3次表现低于历史 | 权重降低10% |
| **近期表现上升** | 连续3次表现高于历史 | 权重增加10% |
| **因子衰减** | IC下降超过30% | 权重降低20% |
| **因子拥挤** | 太多策略使用 | 权重降低15% |

---

## 假设验证流程

### 假设生命周期

```
提出假设 → 回测验证 → 样本外测试 → 实盘验证 → 确认/拒绝
   ↓          ↓          ↓          ↓          ↓
  LLM      回测引擎   Walk-Forward  模拟盘    知识入库
```

### 假设验证

```bash
python -m scripts hypothesis-verify --id HYP-20260702-001
```

```json
{
  "hypothesis_id": "HYP-20260702-001",
  "description": "高换手率的股票未来收益更高",
  "status": "verified",
  "verification_steps": [
    {"step": "backtest", "result": "passed", "sharpe": 1.2},
    {"step": "walk_forward", "result": "passed", "avg_sharpe": 1.1},
    {"step": "paper_trading", "result": "passed", "return": 0.08}
  ],
  "final_result": "accepted",
  "confidence": 0.85
}
```

---

## 策略表现监控与预警

### 监控指标

| 指标 | 说明 | 阈值 |
|------|------|------|
| **收益偏差** | 实盘收益 vs 回测收益 | >10% |
| **胜率下降** | 近期胜率 vs 历史胜率 | >20% |
| **最大回撤** | 当前回撤 vs 历史最大回撤 | >1.5倍 |
| **换手率异常** | 近期换手率 vs 历史换手率 | >2倍 |

### 预警机制

```python
from verification.strategy_monitor import StrategyMonitor

monitor = StrategyMonitor()

# 检查策略表现
alerts = monitor.check(
    strategy_name="momentum",
    recent_return=0.05,
    historical_return=0.12,
    recent_win_rate=0.45,
    historical_win_rate=0.58
)

print(f"预警: {alerts}")
```

### 预警处理

| 预警类型 | 处理方式 |
|----------|---------|
| **收益偏差** | 检查数据质量，分析原因 |
| **胜率下降** | 检查因子表现，调整参数 |
| **回撤预警** | 触发风控规则，减仓 |
| **换手率异常** | 检查交易逻辑，优化 |

---

## 验证闭环仪表盘

### 实时监控

```
┌─────────────────────────────────────────────────────────────┐
│                    验证闭环仪表盘                           │
├─────────────────────────────────────────────────────────────┤
│  预测准确率                                                 │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ LLM: 54.7% | 因子: 62.3% | 策略: 57.8%           │    │
│  └─────────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────────┤
│  决策记忆                                                   │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 本月决策: 45 | 盈利: 26 | 亏损: 19 | 胜率: 57.8% │    │
│  └─────────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────────┤
│  经验积累                                                   │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 成功模式: 15 | 失败模式: 8 | 待验证: 5            │    │
│  └─────────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────────┤
│  预警                                                       │
│  - [WARNING] momentum 胜率下降: 58% → 45%                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 最佳实践

### 1. 预测可追踪

每个预测都要有唯一 ID，便于后续验证。

### 2. 决策可追溯

记录每次决策的理由、上下文和结果。

### 3. 经验可复用

将成功和失败的经验积累到知识库中。

### 4. 反馈可调整

根据验证结果动态调整策略参数。

### 5. 预警可处理

及时处理预警，避免问题扩大。

---

## 参考

- [预测追踪](file:///E:/Code/量化交易/quant-system/verification/predictor_tracker.py)
- [决策记忆](file:///E:/Code/量化交易/quant-system/verification/decision_memory.py)
- [经验学习](file:///E:/Code/量化交易/quant-system/verification/lesson_learner.py)
- [loverMentor](https://github.com/.../loverMentor)
