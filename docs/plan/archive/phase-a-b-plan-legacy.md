# 量化交易系统 — 整体架构方案

> ⚠️ 本文档已归档（2026-07-07），内容仅作历史参考。
> 创建日期：2026-07-02
> 最后更新：2026-07-06 (Phase A 已全部完成，清理已完成项)
> 定位：整合所有设计分析，形成可执行的架构演进路线图

---

## ⚠️ 文档状态说明

> **本文档为历史计划文档，部分内容已过时。**
>
> 当前事实基线以 [`docs/project/project-status.md`](../../project/project-status.md) 为准，路线图以 [`docs/project/roadmap.md`](../../project/roadmap.md) 为准。
>
> **主要冲突点**（已在下文相应段落标注 "⚠️ 已过时"）：
>
> 1. **MCP 定位**：本文档将 MCP 工具层列为 Phase D，当前已提升为项目核心定位（详见 project-status.md §0.1）
> 2. **LLM 内部调用**：本文档设计原则 2.3 "LLM 是研究员"，当前决策为移除 quant-system 内部的 LLM 调用，只做 MCP（详见 project-status.md §0.2）
> 3. **Phase C.1-2 MCP 工具**：本文档计划 10 个只读工具，实际已实现 30 个工具
> 4. **社交情绪（Phase C.3-2）**：当前后移到 Phase C/D，非当前 P0
> 5. **Phase B/C/D 优先级**：当前路线图见 roadmap.md，本文档优先级结构不再适用
>
> **保留价值**：本文档的架构全景图、八层设计、深度代码审计（附录 B）仍有参考价值。

---

## 零、Phase A 完成状态（2026-07-06）

### ✅ Phase A 全部完成

- **A-1** 结构化日志系统 — 已完成
- **A-2** 统一配置管理 — 已完成
- **A-3** MarketFact + FactStore — 已完成
- **A-4** OKF 报告模板 — 已完成

### 未完成项（原计划 Phase A 但推迟）

- `scripts/health_check.py` (P1) — 推迟到 Phase B
- `scripts/scheduler.py` (P1) — 推迟到 Phase B
- `data/migrations/` (P1) — 推迟到 Phase C
- `alerts` 表 (P2) — 推迟到 Phase C

---

## 一、总览：目标架构全景图

> ⚠️ 已过时：下方架构图中 "MCP 工具层 (Phase D)" 的定位已变更。MCP 当前是项目核心定位（不是 Phase D），实际已实现 30 个工具。详见 project-status.md §0.1。

```
                            ┌─────────────────────────────────┐
                            │     MCP 工具层 (核心定位)        │
                            │   30 个工具已实现，暴露给 Agent  │
                            └─────────────┬───────────────────┘
                                          │
┌─────────────────────────────────────────┼─────────────────────────────────────┐
│                              推理层 (LLM / Agent)                              │
│                                                                               │
│   ┌──────────────────────────────────────────────────────────────────────┐   │
│   │  1. 方法论检索  →  2. 市场记忆查询  →  3. 数据分析  →  4. 验证  →  5. 输出  │   │
│   │     Wiki             Facts/Events        Factors        Risk       Report │   │
│   └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────┬─────────────────────────────────────┘
                                          │
                    ┌─────────────────────┼─────────────────────┐
                    ▼                     ▼                     ▼
┌──────────────────────┐ ┌──────────────────────┐ ┌──────────────────────┐
│      输出层           │ │      融合层           │ │      策略层           │
│                      │ │                      │ │                      │
│ OKF Report           │ │ FusionEngine         │ │ S→A→T→R 管线         │
│ YAML frontmatter     │ │ 动态权重 × 多源交叉验证│ │ 连续权重 w∈[-1,+1]   │
│ facts/judgments分离  │ │ 冲突解决矩阵          │ │ SignalValidator      │
│ prediction_id 追踪   │ │ MarketSnapshot 统一输出│ │ 装饰器注册表          │
│ JSON+MD 双输出       │ │                      │ │                      │
└──────────┬───────────┘ └──────────┬───────────┘ └──────────┬───────────┘
           │                        │                        │
           └────────────────────────┼────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┬────────────────┐
                    ▼               ▼               ▼                ▼
┌──────────────────────┐ ┌──────────────────────┐ ┌──────────────────────┐
│      输入层           │ │      因子层           │ │      知识层           │
│                      │ │                      │ │                      │
│ 行情 (35%) AKShare   │ │ 25个内置因子          │ │ OKF Wiki   方法论   │
│ 因子 (25%) FactorEng │ │ IC/ICIR 每日评估      │ │ knowledge/ 市场记忆  │
│ 新闻 (15%) Pipeline  │ │ 中性化处理            │ │ events/ 事件库       │
│ 社群 (10%) 群聊情绪   │ │ 衰减追踪+自动告警      │ │ hypotheses/ 假设库   │
│ Wiki (10%) Retriever │ │                      │ │ failures/  教训库    │
│ 事实 (5%)  FactStore │ │                      │ │                      │
└──────────┬───────────┘ └──────────┬───────────┘ └──────────┬───────────┘
           │                        │                        │
           └────────────────────────┼────────────────────────┘
                                    ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                              持久化层                                          │
│                                                                              │
│  DuckDB (quant.duckdb)               Markdown (knowledge/)                    │
│  ├── stock_daily, factors, events    ├── daily/, weekly/, monthly/            │
│  ├── market_facts ✅                 └── OKF frontmatter + structured body    │
│  ├── market_snapshots (新)                                                    │
│  ├── factor_evaluations (新)         JSONL (knowledge/)                       │
│  ├── backtest_runs (新)              ├── events/                              │
│  ├── alerts (新)                     ├── hypotheses/                          │
│  └── predictions (已有，待启用)       └── failures/                            │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 二、核心设计原则

### 2.1 方法论驱动，而非数据驱动

**原则：先查 Wiki，再看数据。**

```
分析流程:
  第 1 步：方法论  → wiki_search() — 找到相关交易框架
  第 2 步：市场记忆 → 查询近期日报 + 事件 — 了解当前市场背景
  第 3 步：数据    → 查行情 + 算因子 + 跑回测 — 获取量化信号
  第 4 步：验证    → 风控检查 + 多因子交叉验证 — 不机械套用阈值
  第 5 步：输出    → 生成 OKF 报告 + 存入 knowledge/
```

来源：loverMentor 的核心设计模式。Wiki 是推理的起点，不是事后参考。

### 2.2 权重合约 — 策略的唯一接口是连续权重向量

**原则：所有策略组件输入/输出 `w ∈ [-1, +1]ⁿ`。**

- 离散信号（买/卖/持有）改为连续权重 → 多策略信号可加权融合 → 可直接输入组合优化器
- 来源：FinRL-X 的 S→A→T→R 管线

### 2.3 LLM 是研究员，不是交易员

> ⚠️ 已过时：本节描述的 LLM 内部调用模式（事件提取、多角色分析、报告撰写）当前决策为移除。quant-system 内部不再调用 LLM API，LLM 能力由调用方（Claude/Codex 等 Agent）提供。详见 project-status.md §0.2。

**原则：传统量化引擎处理交易决策，LLM 只做研究和信息处理。**

保持不变。LLM 的边界是：事件提取、因子假设生成、多角色分析、报告撰写。不直接下单、不做仓位管理、不做风控决策。

### 2.4 验证闭环

**原则：每个预测都可以被验证，每次验证都反馈回系统。**

- 每个预测带 `prediction_id` → 次日自动验证 → 准确率统计 → 反馈到信号权重
- 每次回测入库 → 可对比历史 → 策略衰退自动检测
- 来源：systematic-trading-framework 的 WFO 方法论 + loverMentor 的 facts 验证体系

### 2.5 不可逆操作不走自动化

**原则：下单、减仓、平仓等不可逆操作必须经过人工确认。**

风控可以检测、告警、建议，但实际执行需要人工确认。MCP 工具可以做查询和分析，但写操作（交易指令）走审批流程。

---

## 三、八层架构详细设计

### 3.1 输入层 — 五源融合

**当前状态**：AKShare 行情 + 新闻流水线，FactStore 已就绪。无融合引擎、无 Wiki 检索、无动态权重。

**Phase A 完成项**：`data/market_fact.py`（MarketFact + FactStore），`market_facts` DuckDB 表。

**目标状态**：六源融合输入（行情 35% + 因子 25% + 新闻 15% + 社群情绪 10% + Wiki 10% + 事实 5%），动态权重调整。

**新增第六源：社交群聊情绪（Phase C）**
- 来源：QQ 股票群聊天记录（通过 go-cqhttp 或类似开源 QQ 机器人采集）
- 数据类型：群聊文本 → 情绪分类（看多/看空/中性）+ 关注热点提取
- 处理流程：原始消息 → 清洗去噪 → LLM 观点提取 → MarketFact(fact_type="social_sentiment") → FusionEngine.apply_intelligence()
- 参考：loveMentor 已有现成的社交情绪分析管道；QQ 有开源协议实现（go-cqhttp / Mirai）可直接部署
- 价值点：
  - **群体情绪信号** — 散户看多/看空比，恐慌/贪婪程度，这是纯量化无法捕捉的
  - **热点发现** — 什么股票/板块在讨论，热度变化趋势（风口识别）
  - **LLM 群聊日报** — LLM 每日阅读最近聊天内容，输出群聊观察报告
- 注意：群聊情绪不覆盖量化信号，只做方向调制（见情报-数据融合规则）

**动态权重公式**：
```
最终权重 = 基础权重 × 数据质量分数 × 时间衰减系数 × 市场状态系数 × 策略匹配系数 × 社群可信度系数 / 归一化
```

**社群可信度系数**（新增，仅对社交情绪源生效）：
- 当日活跃用户数 > 50 → 1.0（高可信）
- 20-50 用户 → 0.7
- < 20 用户 → 0.3（低可信，权重大幅降低）

**市场状态权重调整**：

| 市场状态 | 行情 | 因子 | 新闻 | 社群 | Wiki | 事实 |
|---------|------|------|------|------|------|------|
| 趋势市 | 0.35 | 0.30 | 0.10 | 0.05 | 0.15 | 0.05 |
| 震荡市 | 0.25 | 0.20 | 0.25 | 0.15 | 0.10 | 0.05 |
| 极端波动 | 0.20 | 0.15 | 0.25 | 0.20 | 0.15 | 0.05 |
| 财报季 | 0.25 | 0.20 | 0.30 | 0.10 | 0.10 | 0.05 |
| 政策窗口 | 0.20 | 0.10 | 0.30 | 0.20 | 0.15 | 0.05 |

**冲突解决核心规则**：
- 行情和因子同向 → 高置信度（≥0.75）
- 行情和因子反向 → 置信度折半，标记"信号不明确"
- 新闻与量化方向相反 → 量化优先（新闻可能滞后或 overreaction）
- 行情极度异常（涨跌停/连续涨停/停牌复牌）→ 技术因子降权为 0.1，新闻升权为 0.5
- Wiki 只做方向验证，不翻转信号

**情报-数据融合规则**（来源：枫叶子 intelligence.py）：
- 情报不覆盖量化信号，只做方向调制 — 情报看多 + 量化看多 → 信号加强；情报看多 + 量化看空 → 量化优先
- 极端情报信号（如突发政策、黑天鹅标签）→ 触发风控复审，不直接修改信号

**社交情绪特殊规则**（新增）：
- 群聊情绪是"反指预警"而非"正向信号" — 散户高度一致看多往往是见顶信号
  - 看多比 > 80% → 反向指标，降低 bullish 置信度
  - 看空比 > 80% → 短期反弹信号（散户恐慌踩踏往往是底部）
- 群聊情绪仅做辅助参考，不单独触发交易指令
- LLM 群聊观点摘要编入日报"社会情绪观察"章节，不进入策略信号链
- 当群聊情绪与量化信号方向相反时 → 量化信号不变，但报告标记"散户情绪分歧"

**新建文件**：
- `data/market_fact.py` ✅ — MarketFact 数据类 + FactStore CRUD
- `data/news_fetcher.py` — AKShare 新闻接口封装
- `research/fusion.py` — FusionEngine 融合引擎

**新建 DuckDB 表**：
- `market_facts` ✅ — 结构化市场事实
- `market_snapshots` — 每日多源快照

---

### 3.2 知识层 — OKF Wiki + 市场记忆 + 决策记忆

**当前状态**：`knowledge/` 有日报和事件存储。OKF 报告模板已就绪。无方法论文库、无 Wiki 检索、无决策记忆。

**Phase A 完成项**：`knowledge/report_template.py`（OKFReportMetadata + 8段模板）。

**目标状态**：三轨知识系统：
- **OKF Wiki**（方法论主轴）— 交易框架、经典书籍、市场规则，pre-query 使用
- **knowledge/**（市场记忆）— 日报/周报/事件/假设/教训，post-query 积累
- **decision_memory/**（决策记忆，来源：枫叶子）— 每次调仓记录 + 1/3/5/10日事后收益验证

**Wiki 内容分类**：

| 类型 | 数量目标 | 示例条目 |
|------|---------|---------|
| entity | 10-15 | 突破交易、趋势跟踪、均值回归、动量因子、资金管理 |
| scenario | 5-8 | 牛市初期布局、熊市防守、震荡市应对、黑天鹅应对 |
| source | 8-12 | 《海龟交易法则》《笑傲股市》《黑天鹅》《聪明的投资者》 |
| synthesis | 3-5 | 趋势跟踪 vs 均值回归、价值 vs 动量、主观 vs 量化 |

**OKF 格式**（YAML frontmatter + Markdown body）：
```yaml
---
title: 突破交易
type: entity
tags: [技术分析, 入场, 趋势]
keywords: [突破, 新高, 放量]
market_regime: [趋势市, 震荡市]
timeframe: [日线, 周线]
---
```

**检索方式**（复用 loverMentor 五维评分）：标题/关键词/标签/市场状态/时间周期 + search-index.json 预建索引。

**决策记忆机制**（来源：枫叶子 decision_memory）：
- 每次调仓记录：日期、标的、方向、权重、原因
- 事后 1/3/5/10 日自动计算实际收益
- 统计每种信号的历史准确率 → 反馈到 SignalValidator

**新建文件**：
- `knowledge/wiki_retriever.py` — Wiki 检索器
- `knowledge/report_template.py` ✅ — OKF 元数据 schema + 报告模板

**新建目录**：
- `docs/wiki/entities/` — 交易概念框架
- `docs/wiki/scenarios/` — 市场场景决策
- `docs/wiki/sources/` — 经典书籍方法论来源
- `docs/wiki/synthesis/` — 综合对比

---

### 3.3 因子层 — 全生命周期管理

**当前状态**：25 个内置因子，evaluator.py 存在但未接入 daily_research。无中性化、无衰减追踪。
因子参数硬编码（如 momentum 固定 20 日），不支持参数扫描。

**审计发现**：`research/factors.py` 中所有因子的 period 参数都是硬编码常量，没有从配置或注册参数读取的机制。

**目标状态**：完整的因子生命周期 — 编写 → 评估(IC/ICIR) → 中性化 → 稳定性检验 → 入库 → 持续监控。

**改进项**：

1. **因子评估接入每日流水线**：在 step 3（因子计算）之后运行 FactorEvaluator，结果入 `factor_evaluations` 表
2. **中性化处理**：新建 `research/neutralizer.py`，行业/市值/自适应中性化
3. **衰减追踪**：IC < 0.02 持续 20 日 → WARNING；IC 方向反转 → CRITICAL；Decay > 50% 在 5 日内 → WARNING
4. **因子参数化**：借鉴枫叶子的 walk-forward 动态配置文件思路，因子参数从 config 读取而非硬编码

**新建文件**：
- `research/neutralizer.py` — 因子中性化

**新建 DuckDB 表**：
- `factor_evaluations` — date, factor_name, ic, icir, decay_speed, group_return_monotonicity, turnover_stability

---

### 3.4 策略层 — Weight-Contract S→A→T→R

**当前状态**：StrategyBase 6 个抽象方法（prepare/signal/sizing/risk_check/kill_switch/holding_period），4 个策略中 3 个空壳。Signal 是离散的（BUY/SELL/HOLD）。无资金部署回退机制。

**目标状态**：

1. **信号连续化**：`generate_signal()` 从返回 `list[Signal]` 改为 `WeightVector {symbol: w}`，w ∈ [-1, +1]

2. **插入 SignalValidator 层**（来源：SignalFlow Meta-Labeling）：
```
Strategy.generate_signal() → SignalValidator.validate() → RiskEngine.check()
                                │
                                ├── 历史胜率检查（该信号过去 N 次准确率）
                                ├── 因子一致性检查（驱动/警告因子是否矛盾）
                                └── 市场状态匹配检查（当前 regime 下是否有效）
```

3. **装饰器注册表**（参照 FactorEngine `@register` 模式）：
```python
@register_strategy("momentum", description="动量突破策略")
class MomentumStrategy(StrategyBase):
    ...
```

4. **补齐 3 个缺失策略**：
   - `event_driven` — Event → Signal 映射规则（news/ 流水线已就绪）
   - `sentiment` — Sentiment → Signal 映射规则（llm/extractor.py 已就绪）
   - `regime_switch` — 需先实现 MarketRegimeDetector

5. **现金部署回退机制**（来源：枫叶子 cash_deployment）：
   - 当策略无信号或仓位未满时，闲置资金自动配置逆回购/货基
   - 这确保资金不闲置，提升整体资金使用效率

6. **风险预算仓位管理**（来源：枫叶子 risk_budget）：
   - 每标的仓位 = 总资金 × 风险预算 / 波动率 / 标的数
   - 替代固定比例仓位，让高波动标的自适应缩小仓位

**修改文件**：
- `strategies/base/strategy_base.py` — signal 类型改为 WeightVector；添加 cash_deployment 和 risk_budget 接口
- `strategies/momentum/strategy.py` — 适配新接口

**新建文件**：
- `strategies/base/signal_validator.py` — 信号验证器（含历史胜率查询）
- `strategies/registry.py` — 策略注册表
- `research/regime_detector.py` — 市场状态识别器

---

### 3.5 回测层 — WFO + IVS + Monte Carlo + 持久化

**当前状态**：基础 VectorBT 回测，输出 print + CSV。无参数优化、无 WFO、无过拟合检测、无持久化。

**目标状态**（来源：systematic-trading-framework + 枫叶子）：

```
回测流程:
  参数优化 → Walk-Forward 验证 → IVS 鲁棒性检验 → Monte Carlo 模拟 → Kelly 仓位 → 入库
```

**核心改进**：

1. **Walk-Forward Optimization** — 借鉴枫叶子的 profile 重选机制：
   - 每 N 个交易日（如 20 日）用过去 M 日数据重新选择最优配置
   - 只用过去数据，不用未来数据 → 无 look-ahead bias
   ```bash
   python -m scripts backtest --mode walk-forward \
       --train-window 252 --test-window 63 --step 63
   ```

2. **IVS (Island Volume Selection)**：选参数"高原"（邻近参数稳定区），不选"尖峰"（过拟合点）

3. **Monte Carlo 模拟**（枫叶子已有 block bootstrap 实现）：
   block bootstrap 10k 次重采样，评估收益分布而非点估计

4. **回测结果持久化**：入 `backtest_runs` 表，带策略名、参数 JSON、基准对比、权益曲线

5. **ETF 整手优化**（来源：枫叶子 lot-aware enumeration）：
   A 股 ETF 以 100 股为单位交易，回测仓位应取整到 100 的倍数，更贴近实际可执行性

**新建 DuckDB 表**：
- `backtest_runs` — run_id, strategy, ticker, date_range, params, sharpe, max_drawdown, excess_return 等
- `backtest_equity` — run_id, date, equity_value (权益曲线)

**命令增强**：
```bash
python -m scripts backtest --strategy momentum --ticker 600519 \
    --scan lookback=10,15,20,25,30 \
    --output-format table  # table / json / chart
```

---

### 3.6 风控层 — 事前→事中→事后 三层体系

**当前状态**：7 条全局风控规则，仅策略层调用。无事中监控、无事后归因。

**目标状态**（来源：Magents 中央风控 + systematic-trading-framework 统计检验）：

```
事前 (Pre-Trade)
  ├── 7 条规则校验（已有）
  ├── StressTestEngine — 历史极端情景回放（2015/2018/2020/2024）
  └── LiquidityGate — 单日成交额 < 5000万则拒单

事中 (In-Trade, 仿真盘/实盘阶段)
  ├── LiveMonitor — 实时 PnL、VaR(95%)、组合杠杆率
  ├── AutoDeleverage — 日亏损触及 -2% → 提醒减仓（需人工确认）
  └── PriceGuard — 订单价格偏离最新价 ±2% → 拒绝

事后 (Post-Trade)
  ├── BrinsonAttribution — 收益 = 配置效应 + 选股效应 + 交互效应
  ├── StrategyDecayDetector — 滚动 20 日胜率 < 40% 且夏普 < 0 → 策略暂停告警
  └── BacktestVsLive — 回测信号 vs 实际成交偏差分析
```

**注意**：事中层的 AutoDeleverage 只触发告警和建议，实际减仓操作需要人工确认（不可逆操作不走自动化）。

**新建文件**：
- `risk/stress_test.py` — 压力测试引擎
- `risk/live_monitor.py` — 实时监控
- `risk/attribution.py` — Brinson 收益归因
- `risk/decay_detector.py` — 策略衰退检测

---

### 3.7 输出层 — OKF 格式报告

**当前状态**：OKF 模板已实现（Phase A-4）。LLM prompt 和简化日报均已更新为 OKF 8 段格式。预测追踪闭环未实现。

**Phase A 完成项**：
- `knowledge/report_template.py` — OKFReportMetadata dataclass + 8段模板 + 双输出（MD + JSON）
- `llm/report_agent.py` — prompt 模板改为 OKF 8 段格式
- `scripts/daily_research.py` — generate_simple_daily_report 改为 OKF 8 段格式

**目标状态**：OKF 格式（YAML frontmatter + 结构化 Markdown body），JSON + MD 双输出。

**OKF 元数据头关键字段**：
```yaml
---
report_id: "rpt_20260701_603005"
report_type: daily_prediction  # daily_prediction / deep_analysis / thematic / backtest
ticker: "603005"
date: "2026-07-01"
market_regime: trend  # trend / oscillating / extreme_volatility / earnings_season / policy_window
regime_confidence: 0.78
input_weights: {market_data: 0.40, factor_signals: 0.30, news_events: 0.15, wiki_methodology: 0.10, historical_facts: 0.05}
factors_used: [momentum_20d, rsi_14, macd, atr_14, volume_ratio_5d]
factor_signals:
  momentum_20d: {value: 0.065, direction: bullish, strength: moderate}
  rsi_14: {value: 65.28, direction: neutral, strength: weak}
wiki_refs:
  - {title: "趋势跟踪", score: 0.82}
  - {title: "放量突破", score: 0.75}
overall_confidence: 0.68
risk_level: medium
risk_engine_passed: true
prediction_id: "pred_20260701_603005"
previous_prediction_id: "pred_20260630_603005"
previous_prediction_correct: null
facts:
  - "收盘价 52.65，跌幅 -2.26%"
  - "换手率 17.93%，放量下跌"
judgments:
  - "短期多空分歧加剧"
  - "大概率在 51.5-53.5 区间震荡"
data_sources:
  price_data: {source: "akshare.stock_zh_a_hist", ticker: "603005"}
  factors: {source: "FactorEngine.compute_all", version: "1.0"}
  news: {source: "NewsFetcher.fetch_stock_news", count: 3}
  wiki: {source: "WikiRetriever.search", query: "放量突破 芯片 趋势"}
---
```

**报告正文结构**（8 段）：市场状态 → 行情快照 → 因子信号（驱动因子 + 警告因子 + 贡献度）→ 风控检查 → 事件与新闻 → Wiki 方法论匹配 → 预测（含回测参考胜率）→ 昨日预测验证

**已完成文件**：
- `knowledge/report_template.py` ✅ — OKF 元数据 schema + 报告模板

**已修改文件**：
- `llm/report_agent.py` ✅ — prompt 模板改为 OKF 格式输出

---

### 3.8 基础设施层 — 运维基石

**当前状态**：日志系统（A-1）和配置管理（A-2）已完成。健康检查、定时调度、DB 迁移、告警持久化尚未开始。

**Phase A 完成项**：
- `utils/logging.py` ✅ — loguru 封装，控制台彩色 + 文件按天轮转 + JSON 结构化日志
- `configs/settings.py` ✅ — pydantic-settings，读取 .env + app.yaml

**待完成项**：

| # | 事项 | 优先级 | 新建文件 | 备注 |
|---|------|--------|---------|------|
| 1 | **结构化日志系统** | P0 | `utils/logging.py` | ✅ 已完成，部分模块待替换 print |
| 2 | **统一配置管理** | P0 | `configs/settings.py` | ✅ 已完成，7 模块已迁移 |
| 3 | **系统健康检查** | P1 | `scripts/health_check.py` | 推迟到 Phase B |
| 4 | **定时任务调度** | P1 | `scripts/scheduler.py` | 推迟到 Phase B |
| 5 | **数据库迁移** | P1 | `data/migrations/` | 推迟到 Phase C |
| 6 | **告警持久化** | P2 | DuckDB `alerts` 表 + `scripts show-alerts` | 推迟到 Phase C |
| 7 | **密钥管理** | P3 | 所有密钥迁移到 .env | ✅ 已在 A-2 中完成 |

---

## 四、端到端数据流（单次分析）

```
用户: "分析一下 600519 今天的情况"

Step 1  Wiki → wiki_search("放量突破 白酒 趋势")
        → 匹配: "突破交易"(0.85), "白酒行业周期"(0.72)

Step 2  事实 → FactStore.query("600519", days=30)
        → 近期 MarketFact: "600519 MACD 金叉 3 日前" [已验证]

Step 3  数据 → FusionEngine.collect("600519", "2026-07-01")
        ├── 行情: Provider.get_daily("600519") → {close: 1850, pct: +2.3%, vol: 1.5x}
        ├── 因子: FactorEngine.compute_all(df) → {momentum_20d: 0.08, rsi: 62}
        ├── 新闻: NewsFetcher.fetch("600519") → 3 条, 2 个结构化 Event
        ├── 社群: SocialAnalyzer.get_sentiment("600519") → {bull_ratio: 0.35, heat: 0.6}
        └── 融合: fuse(sources, weights, regime) → MarketSnapshot

Step 4  验证 → SignalValidator.validate(signal, regime, history)
        ├── 历史胜率: 该信号过去 23 次, 次日上涨概率 61%
        ├── 因子一致性: 3 驱动因子同向, 1 警告因子反向
        └── 市场状态匹配: 趋势市 + 动量因子有效

Step 5  输出 → ReportAgent.generate(snapshot, wiki_refs, validation)
        → OKF 报告 (YAML frontmatter + Markdown body)
        → 存入 knowledge/daily/ + market_snapshots 表
        → Prediction 入 predictions 表（待明日验证）
```

---

## 五、优先级执行路线

### 路线图总览

```
Phase 0 [止血]       5h  让已有代码在真实数据上跑通，补依赖、修脆弱的代码
  ↓
Phase B Fixes [还债] 6.5h 修审计发现的 P0/P1 缺陷，统一 Event 模型，补测试
  ↓
Phase C.1 [地基]     10h  回测持久化 + MCP 只读工具 + DB 迁移（最优先）
  ↓
Phase C.2 [进阶]     10h  WFO + 三层风控 + 因子中性化（依赖 C.1）
  ↓
Phase C.3 [延伸]     8h  预测闭环 + 社交情绪 + paper broker（可并行）
  ↓
Phase D [生态]       22h  补齐 3 策略 + MCP 全部工具 + 数据分层 + LLM Agent
```

**核心变化**：原计划直接跳入 Phase C 加功能。审计发现代码从未在真实数据上跑通过，因此必须先加入 Phase 0（止血）和 Phase B Fixes（还债），确保地基牢固后再盖楼。

---

### Phase 0：止血（新增，约 5h）

**目标**：让已有代码在真实数据上通过最小闭环验证，修复阻碍运行的操作性问题。

**必要性**：Phase B 代码虽已通过 import 测试和语法验证，但从未在真实 A 股数据上运行。`stock_daily` 表为空，akshare 未安装，`daily_research.py` 全程走降级路径。在 Phase C 之前必须解决。

| # | 事项 | 工作量 | 涉及文件 | 说明 | 验收方案 |
|---|------|--------|---------|------|---------|
| 0.1 | **依赖分三档** | 0.5h | `requirements-core.txt`, `requirements-research.txt`, `requirements-integrations.txt`（新建） | core: pandas,numpy,duckdb,loguru,pydantic-settings,schedule（<10 包）；research: +akshare,vectorbt,riskfolio-lib；integrations: +pyqlib,vnpy,openbb,langchain,openai。目前 requirements.txt 把所有依赖混在一起，新人或换机器时需要全装 | `pip install -r requirements-core.txt` 成功且仅安装 ≤10 个包；`pip install -r requirements-research.txt` 成功安装 akshare/vectorbt/riskfolio-lib |
| 0.2 | **修复 TradingAgents 降级 bug** | 0.5h | `integrations/trading_agents.py:34` | 当 HAS_TRADING_AGENTS=False 时，TradingAgentsGraph 未定义，但 TradingAgentsEngine 直接引用它导致 NameError。降级路径应该优雅返回 None 而非崩溃 | `HAS_TRADING_AGENTS=False` 时 `from integrations.trading_agents import TradingAgentsEngine` 不抛异常；实例化返回 None 而非崩溃 |
| 0.3 | **安装 akshare + 拉取真实数据** | 1h | 运维操作（无代码变更） | `pip install -r requirements-research.txt`；`python -m scripts update-data --tickers 600519,000001,300750,000858,002415 --start 2024-01-01`。验证 `stock_daily` 表 >0 行。**这是整个 Phase 0 最关键的一步** | `python -c "import akshare; print(akshare.__version__)"` 成功；DuckDB `SELECT COUNT(*) FROM stock_daily` 返回 >0；5 只股票均有 2024-01-01 至今的日线数据 |
| 0.4 | **在真实数据上验证 Phase B 全部模块** | 2h | `scripts/daily_research.py`, `research/fusion.py`, `research/regime_detector.py`, `strategies/momentum/strategy.py`, `agents/committee.py` | 跑 `python -m scripts daily-research --no-llm`，逐项验证：数据加载、因子计算、regime 识别、融合、回测、Agent 委员会。记录每个失败为 blocking issue | `daily-research --no-llm` 日志显示：数据加载成功且行数 >0、因子计算完成且无 NaN、regime 类型非 None、FusionEngine 返回 MarketSnapshot、回测输出 Sharpe 为有限数值、Agent 委员会 5 角色均输出评分 |
| 0.5 | **补 research 导出 + scheduler 配置** | 0.5h | `research/__init__.py`, `configs/settings.py`, `configs/app.yaml` | 导出 FusionEngine/MarketRegimeDetector/MarketRegime/MarketSnapshot；添加 schedule_data_update_time 和 schedule_research_time 字段 | `from research import FusionEngine, MarketRegimeDetector, MarketRegime, MarketSnapshot` 成功；`settings.schedule_data_update_time` 和 `settings.schedule_research_time` 返回非 None 值 |
| 0.6 | **修复脆弱变量检查** | 0.2h | `scripts/daily_research.py:168` | 将 `if 'snapshot' in dir()` 改为显式 `snapshot = None` 初始化 + `if snapshot is not None` | 在 Step 3 的 try 块抛出异常后，`review_snapshot` 为 `None` 而非 NameError；正常路径下 `review_snapshot` 为有效 snapshot 对象 |
| 0.7 | **替换 print()→logger** | 0.5h | `research/factors.py`, `research/backtest.py`, `scripts/backtest.py`, `scripts/daily_research.py` | ~20 处残留 print() 替换为 logger.info()/logger.debug()，完成 Phase A 未尽事宜 | 4 个文件中 `grep -n "print("` 返回空；运行 `daily-research` 日志输出带时间戳和模块名的结构化日志而非裸 print 文本 |

**Phase 0 成功标准**：
- `pip install -r requirements-core.txt` 一键安装成功（<10 个包）
- `stock_daily` 表有 >0 行真实数据
- `python -m scripts daily-research --no-llm` 在真实数据上无异常跑完全流程
- `python -m scripts health_check --json` 无 P0 级别失败项
- `research/__init__.py` 导出了全部 6 个类

---

### Phase B Fixes：还债（约 6.5h）

**目标**：修审计发现的 P0/P1 结构性缺陷。这些不是新功能，是已有代码必须修复的 bug。

| # | 事项 | 工作量 | 涉及文件 | 说明 | 验收方案 |
|---|------|--------|---------|------|---------|
| B-fix-1 | **统一 Event 模型** | 2h | `data/schema.py`, `news/schema.py`, `llm/extractor.py`, `knowledge/knowledge_base.py`, `scripts/daily_research.py` | **影响面最大的 P0**。项目存在三套不兼容的 Event（data/schema、news/schema、llm/extractor）。方案：以 data/schema.py 的 Event 为 canonical，news/schema.py 转为子类，统一 serialization | `data/schema.Event` 的 `to_dict()`/`from_dict()` 可序列化/反序列化 news 和 llm 两套字段；`daily_research.py` 中事件保存不再需要手动映射 12 个字段；`pytest tests/test_data_schema.py` 通过 Event 兼容性测试 |
| B-fix-2 | **风控空壳修复** | 1.5h | `risk/risk_engine.py:191-202` | 行业集中度和换手率检查标注 TODO 且始终返回空列表。需要接入行业分类数据（akshare 可提供）和成交数据 | `_check_sector_exposure([{"ticker":"600519","weight":0.3},{"ticker":"000858","weight":0.3}])` 返回非空违规列表（同一白酒行业超限）；`_check_turnover_rate({"ticker":"600519","volume_ratio":15.0})` 返回违规 |
| B-fix-3 | **因子计算去重** | 1h | `strategies/momentum/strategy.py:prepare_features()` | 策略自行计算动量/RSI/量比，重复 research/factors.py 的注册因子。改为调用 FactorEngine.compute_all(df) | `MomentumStrategy.prepare_features()` 内部调用 `FactorEngine.compute_all()`；移除 `_calculate_momentum`, `_calculate_rsi`, `_calculate_volume_ratio` 三个私有方法；与 research 因子输出结果一致 |
| B-fix-4 | **核心模块单元测试** | 3h | `tests/test_data_schema.py`, `tests/test_factors.py`, `tests/test_risk_engine.py`, `tests/test_momentum_strategy.py`（新建） | **零测试是最大的质量缺口**。用合成数据添加 4 个测试文件：schema 一致性、因子计算正确性、风控规则边界条件、策略信号输出。每个文件 <100 行，只测契约不测实现 | `pytest tests/ --tb=short` 通过 ≥20 个测试；4 个测试文件均存在且可独立运行；全部使用合成数据（不依赖真实行情）；因子测试已知输入对应的预期输出值验证 |

**Phase B Fixes 成功标准**：
- `data/schema.Event` 和 `news/schema.Event` 可序列化为同一 JSON schema
- `_check_sector_exposure` 在给定集中持仓时返回非空违规列表
- `MomentumStrategy.prepare_features()` 调用 `FactorEngine.compute_all()`
- `pytest tests/` 通过 ≥20 个测试

---

### Phase C：能力建设（约 28h）

**结构调整说明**：原 Phase C 将 7 个任务平铺，缺少依赖顺序。新结构将 Phase C 拆分为三个子阶段，明确"地基→进阶→延伸"的依赖关系。

#### Phase C.1：地基（约 10h）

**目标**：回测结果可持久化、可对比。MCP 只读工具提前。

| # | 事项 | 工作量 | 涉及文件 | 说明 | 验收方案 |
|---|------|--------|---------|------|---------|
| C.1-1 | **回测结果持久化 + CLI 增强** | 3h | `scripts/backtest.py`, `data/storage.py`, `scripts/health_check.py` | **Phase C 最优先任务**。创建 backtest_runs 表（run_id, strategy, ticker, date_range, params_json, sharpe, max_drawdown, returns_annualized, volatility, sortino, calmar, excess_return, benchmark_return, timestamp）和 backtest_equity 表。CLI 增强：`--compare last_3` 对比历史，`--output table/json/chart` | `python -m scripts backtest --strategy momentum --ticker 600519` 写入 backtest_runs 表且返回 run_id；`--compare last_3` 显示 3 条不同日期的回测记录含 Sharpe/最大回撤/超额收益；`--output json` 输出可解析的 JSON；`python -m scripts health-check` 显示 backtest_runs 表状态 |
| C.1-2 | **10 个 MCP 只读工具** | 3h | `tools/data_tools.py`, `tools/knowledge_tools.py`, `tools/wiki_tools.py`（新建）, `mcp_server/server.py`（新建） | **从 Phase D 提前**。10 个工具：get_quote, get_history, get_factors, get_index_data, get_daily_report, search_events, list_strategies, wiki_search, run_health_check, get_market_regime。后端能力 Phase B 已有，MCP 层是薄包装。用 fastmcp/mcp SDK，stdio transport | MCP 服务器启动后 10 个工具均在 `tools/list` 响应中；`get_quote("600519")` 返回含最新价的行情数据；`run_health_check()` 返回 8 项健康检查结果；`wiki_search("突破")` 返回 ≥1 条方法论文档；所有工具在 akshare 不可用时返回友好错误而非崩溃 |
| C.1-3 | **DB 迁移框架** | 1h | `data/migrations/001_init.sql`（新建） | 简单约定式迁移：编号 SQL 文件 + schema_version 表。不引入 Alembic。storage.py 初始化时检查并应用未跑迁移 | `schema_version` 表存在且有 `001_init` 记录；重复启动不重复执行已跑迁移；迁移失败时 `storage.py` 初始化抛出异常而非静默跳过；`python -m scripts health-check` 显示 schema_version 状态 |

> ⚠️ 已过时：C.1-2 计划已超额完成。实际已实现 30 个 MCP 工具（9 data + 10 risk + 11 knowledge），详见 project-status.md §8.1。

**C.1 成功标准**：
- `python -m scripts backtest --strategy momentum --ticker 600519` 写入 backtest_runs 表
- `python -m scripts backtest --compare last_3` 显示 3 条不同日期的回测记录
- MCP 服务器启动后 10 个工具均响应
- schema_version 表在 `python -m scripts health-check` 中可见

#### Phase C.2：进阶（约 10h）

**目标**：回测从点估计升级为分布估计。风控从事前扩展到事后归因。

**前置**：C.1-1（回测持久化）。

| # | 事项 | 工作量 | 涉及文件 | 说明 | 验收方案 |
|---|------|--------|---------|------|---------|
| C.2-1 | **Walk-Forward + 参数扫描** | 4h | `research/walk_forward.py`（新建）, `scripts/backtest.py`（修改） | 仅用过去数据（无 look-ahead）。`--mode walk-forward --train-window 252 --test-window 63 --step 63`。参数扫描 `--scan lookback=10,15,20,25,30`。结果入 backtest_runs 表（wfo_config 元数据字段） | `python -m scripts backtest --mode walk-forward --train-window 252 --test-window 63 --step 63` 无异常跑完且输出 OOS Sharpe、最大回撤、稳定性指标；参数扫描结果入 backtest_runs 表且 params_json 字段包含完整参数组合；WFO 只用过去数据（验证任意 test window 的结束日期 ≤ 该段数据的最后交易日） |
| C.2-2 | **三层风控** | 4h | `risk/stress_test.py`, `risk/attribution.py`, `risk/decay_detector.py`（新建） | 事前：StressTestEngine 回放 4 个历史危机（2015/2018/2020/2024）。事后：Brinson 归因分解为配置效应+选股效应+交互效应。DecayDetector：滚动 20 日胜率 <40% 且夏普 <0 告警。**事中（LiveMonitor/VaR）放到 Phase D**，因为 paper broker 之前监控没有意义 | StressTestEngine 回放 4 个危机场景且每个场景输出组合最大回撤/恢复天数；Brinson 归因在给定模拟持仓和基准收益时分解出 3 个分量且之和等于超额收益（误差 <1e-10）；DecayDetector 在模拟衰减数据（胜率从 50% 持续下降至 30%）上触发 CRITICAL 告警 |
| C.2-3 | **因子中性化 + 衰减检测接入** | 2h | `research/neutralizer.py`（新建）, `scripts/daily_research.py`（修改） | 中性化移除行业和市值暴露。FactorEvaluator（已存在）接入 daily_research.py Step 3。衰减规则：IC<0.02 持续 20 日→WARNING，IC 方向反转→CRITICAL | 中性化后因子与行业哑变量的 Pearson 相关性绝对值均值 <0.05；`daily-research --no-llm` 日志输出每个因子的 IC/ICIR 值；使用合成衰减数据验证衰减规则触发阈值正确（IC<0.02 持续 20 日 → WARNING，IC 反转 → CRITICAL） |

**C.2 成功标准**：
- WFO 输出 OOS Sharpe、最大回撤、稳定性指标
- 压力测试回放 4 个危机场景
- Brinson 归因分解出 3 个分量
- 中性化降低因子与行业哑变量的相关性

#### Phase C.3：延伸（约 8h）

**目标**：预测可追踪可验证。社交情绪新数据源接入。执行层开始搭建。

**依赖关系**：C.3-1 和 C.3-2 完全独立。C.3-3 与 C.2 无依赖。

| # | 事项 | 工作量 | 涉及文件 | 说明 | 验收方案 |
|---|------|--------|---------|------|---------|
| C.3-1 | **预测追踪 + 决策记忆** | 3h | `knowledge/decision_memory.py`（新建）, `scripts/daily_research.py`（修改）, `data/storage.py`（修改） | decision_memory 表：date, ticker, direction, weight, reason, returns_1d/3d/5d/10d（调度器后续回填）。predictions 表链接 previous_prediction_id 次日自动验证。按信号类型统计历史准确率反馈给 SignalValidator | 日报生成后 `predictions` 表有对应记录且 `prediction_id` 唯一；次日运行时 `previous_prediction_correct` 自动回填且与实际涨跌幅一致；`decision_memory.get_accuracy(strategy_type="momentum")` 返回 {signal_type: accuracy} 字典且值在 [0,1] 范围内 |
| C.3-2 | **社交情绪管道** | 5h | `data/social_collector.py`（新建）, `llm/social_analyzer.py`（新建） | **完全独立**，可和 C.3-1 并行。采集：go-cqhttp WebSocket 接入 QQ 群。分析：LLM 每条消息标记看多/看空/中性+热点标的。入 MarketFact(fact_type="social_sentiment")。日报增加"社会情绪观察"章节。特殊规则见设计 §3.1 | 采集器成功连接至少 1 个 QQ 群通道且 `on_message` 回调收到消息；LLM 分析输出 {sentiment: bullish/bearish/neutral, confidence: float, tickers: [str]}；MarketFact(fact_type="social_sentiment") 入库成功；日报输出包含"社会情绪观察"章节 |
| C.3-3 | **Paper Broker 基础** | 3h | `execution/broker/base.py`（新建）, `execution/simulator/engine.py`（新建） | **从 Phase D 提前**。定义抽象接口（place_order, cancel_order, get_positions, get_open_orders）。本地仿真：权重向量→可配置滑点模型→订单生命周期（submitted→accepted→filled/cancelled/rejected）。验证策略权重是否可执行（考虑最小交易单位 100 股） | `place_order`/`cancel_order`/`get_positions`/`get_open_orders` 4 个接口可调用且返回类型一致；仿真引擎接受权重向量 `{"600519": 0.3, "000858": 0.2}` 输出订单生命周期完整记录（含 submitted/accepted/filled 时间戳和成交价）；滑点模型生效（滑点 = 指定价格 × 滑点率）；权重 0.3 × 总资金 100 万 = 3 万 → 折算股数自动取整到 100 的倍数 |

> ⚠️ 已过时：C.3-2 社交情绪管道当前后移到 Phase C/D，非当前 P0。依赖 go-cqhttp 后端且依赖内部 LLM 调用，与当前"移除内部 LLM 调用"决策冲突。详见 project-status.md §0.2 和 §13 P2。

**C.3 成功标准**：
- 预测生成后次日自动验证，`previous_prediction_correct` 字段更新
- 决策记忆按策略和信号类型查询，显示滚动准确率
- 社交采集器连接至少 1 个 QQ 群通道
- Paper broker 接受风控后的权重向量、模拟 10 笔成交含滑点

---

### Phase D：生态（调整后，约 22h）

**调整说明**：
- D-5 的 MCP 工具从 48 个减为约 38 个（10 个已在 C.1-2 完成）
- D-7 数据分层和 D-8 知识条目状态机为新增（来自 improvements.md 但未纳入原始计划）
- D-9 适配器统一解决审计的 P2-1
- "事中"风控（LiveMonitor/VaR）从 Phase C 后移到 D，等 paper broker 就绪后才需要

| # | 事项 | 工作量 | 涉及文件 | 验收方案 |
|---|------|--------|---------|---------|
| D-1 | event_driven 策略实现 | 3h | `strategies/event_driven/` | `python -m scripts backtest --strategy event_driven --ticker 600519 --start 2026-06-01 --end 2026-07-01` 无异常跑完；策略信号在有事件日期和无事件日期有差异；输出符合 WeightVector 格式 |
| D-2 | sentiment 策略实现 | 3h | `strategies/sentiment/` | `python -m scripts backtest --strategy sentiment --ticker 600519` 无异常跑完；正/负/中性情绪输入对应不同方向信号 |
| D-3 | regime_switch 策略实现 | 3h | `strategies/regime_switch/` | `python -m scripts backtest --strategy regime_switch --ticker 600519` 无异常跑完；趋势市和震荡市输出不同策略信号 |
| D-4 | AICriticAgent LLM 接入 | 3h | `agents/committee.py`（修改） | 委员会在 `--use-llm` 模式下输出包含 LLM 角色的分析意见；非 LLM 模式回退到纯规则引擎 |
| D-5 | MCP 剩余约 38 个工具 | 5h | `tools/risk_tools.py`, `tools/backtest_tools.py`（新建） | 全部 48 个 MCP 工具在 `tools/list` 中可见；写操作工具（回测触发、策略配置变更）执行前返回权限确认；只读工具无副作用 |
| D-6 | OKF Wiki 内容填充 | 持续 | `docs/wiki/entities/`, `docs/wiki/scenarios/`, `docs/wiki/sources/`, `docs/wiki/synthesis/` | 4 个目录各有 ≥1 个条目且使用 OKF Yaml frontmatter 格式；`wiki_retriever.search("趋势跟踪")` 返回 Wiki 结果而非仅内置 fallback；`wiki_retriever.search("不存在的概念")` 仍返回相关度最高的内置 fallback |
| D-7 | **数据分层重构** | 3h | `data/storage.py`（重构）— 将原始/清洗/研究/发布层分离为独立的 DuckDB schema | `raw`/`cleaned`/`research`/`published` 4 个 schema 在 DuckDB 中存在；`stock_daily` 迁移到 `raw` schema 且数据完整；`SELECT COUNT(*) FROM raw.stock_daily` = `SELECT COUNT(*) FROM stock_daily`（迁移前）；`python -m scripts health-check` 显示各 schema 的表数量 |
| D-8 | **知识条目状态机** | 2h | `knowledge/knowledge_base.py`（修改）— 添加 status 字段：draft→verified→invalidated→obsolete | 新建条目默认 status="draft"；支持 `set_status(id, "verified")` 正向流转和 `set_status(id, "obsolete")` 终态；无效流转（verified→draft）抛出 ValueError；按 status 过滤查询返回正确结果 |
| D-9 | **集成适配器统一** | 3h | `integrations/` — 废弃旧 engine 接口，统一转 adapter 模式 | `daily_research.py` 和 `scripts/` 中不再 import 旧 engine 接口；全部通过 adapter 访问外部项目且功能等价；旧 engine 文件保留但标记 `@deprecated` |

---

## 六、优先级核心逻辑

**为什么是现在这个顺序？**

```
Phase 0  [止血]         ← 新增，最优先
  → 依赖分三档：core/research/integrations，新人一键安装
  → 安装 akshare + 拉真实数据：stock_daily 从 0 行变 >0 行
  → 在真实数据上验证 Phase B 全部模块
  → 补导出、配置、脆弱代码、print 残留
  一句话：让已有代码在真实数据上跑通最小闭环

Phase B Fixes  [还债]   ← 原 B-fix 独立成阶段
  → 统一 Event 模型：三套不兼容 schema 合为一套
  → 补风控空壳：行业集中度和换手率检查真正生效
  → 因子计算去重：策略复用 FactorEngine
  → 加核心测试：20+ 单元测试保护后续重构

Phase C.1  [地基]       ← Phase C 拆为三档，地基最先
  → 回测持久化：从 CSV 丢失变为 DuckDB 可查询可对比
  → 10 个 MCP 只读工具（从 Phase D 提前）
  → DB 迁移框架：防止 schema 漂移

Phase C.2  [进阶]       ← 依赖 C.1 的回测持久化
  → WFO + 参数扫描：从点估计到分布估计
  → 三层风控：事前压力测试 + 事后 Brinson 归因 + 衰减检测
  → 因子中性化：移除行业和市值暴露

Phase C.3  [延伸]       ← 可并行
  → 预测追踪 + 决策记忆：每个 prediction_id 次日自动验证
  → 社交情绪管道：QQ 群聊 → LLM 分析 → MarketFact 入库
  → Paper broker：执行层接口定义 + 本地仿真

Phase D  [生态]         ← 基础打好后的放大
  → 补齐 3 个策略（event/sentiment/regime）
  → MCP 剩余 38 个工具（含写操作）
  → 数据分层 + 知识条目状态机 + 适配器统一
  → Wiki 内容填充
```

**为什么 Phase 0 在 Phase C 之前？**

三份独立评审的共同结论：项目现有的问题不是"缺下一层架构"，而是"已有层没有可信闭环"。`stock_daily` 表为空，akshare 未安装，Phase B 全部模块从未在真实数据上验证过。继续按原计划推 Phase C（WFO/Brinson/预测闭环），每个功能都会建立在脆弱的降级路径上。Phase 0 的核心价值不是"加新能力"，而是"验证已有能力"。大约 5 小时可以完成。

**为什么 MCP 只读工具提前到 Phase C.1？**

原计划把 MCP 放在 Phase D，理由是"后端能力没准备好"。审计发现 10 个只读工具（get_quote, get_factors, wiki_search, run_health_check 等）的后端能力在 Phase B 已完成（FusionEngine + WikiRetriever + HealthCheck），MCP 层只需薄包装。提前实现它们可以让 Claude Code 在后续开发中自主查询系统状态，加速调试和验证。写操作工具（回测触发、策略写入、风控变更）保留在 Phase D。

**为什么事中风控（LiveMonitor/VaR）后移到 Phase D？**

事中风控的前提是存在真实交易来监控。在 paper broker 实现之前（Phase C.3），系统没有交易活动可以监控。过早实现只会产生"监控空气"的空壳。

**为什么原计划的 Phase C→D 顺序不变？**

文档一致性、项目维护、社区分享、长期可维护性仍然是正确方向。只是需要在它们前面加入两个更基础的阶段。

---

## 七、不做什么（显式排除）

1. **Rust 重写核心引擎** — 不着急。对 A 股日频 ≤5000 只股票的规模，Python 足够。真正的瓶颈是方法论和验证体系，不是执行速度。
2. **实盘自动下单** — 当前阶段仅做仿真和研究。实盘涉及合规、券商对接、资金安全，至少是 Phase E+ 的事。
3. **高频/分钟级回测** — 保持日频为主。分钟级需要完全不同的数据基础设施。
4. **SaaS 化 / Web UI** — 保持 CLI + MCP 为主。Web UI 是锦上添花，不解决核心问题。
5. **LLM 直接做交易决策** — 硬边界不动。LLM 只做研究和分析。
6. **SignalFlow 集成** — 该项目克隆失败，模式已记录（Meta-Labeling），但代码暂不可用。
7. **Qt 桌面应用** — 枫叶子有 PySide6 桌面端，我们不跟。CLI + MCP 是更适合我们这个场景的交互方式。

---

## 八、成功标准

| 维度 | Phase A 后 (7/2) | Phase B 后 (7/2) | Phase 0 后 | Phase C.1 后 | Phase C.2 后 | Phase C.3 后 | Phase D 后 |
|------|------------------|------------------|-----------|-------------|-------------|-------------|-----------|
| 日志 | ✅ 结构化日志 | — | ✅ 全部换 logger | — | — | — | — |
| 配置 | ✅ Config 单例 | — | ✅ scheduler 字段补全 | — | — | — | — |
| 真实数据 | 无 | 无 | **✅ ≥5只股票 stock_daily>0行** | — | — | — | — |
| 输入源 | 3 个（行情+新闻+事实） | 5 个（+因子+Wiki） | — | — | — | 6 个（+社交情绪） | — |
| 因子监控 | 无 | 每日 IC/ICIR | — | — | ✅ 中性化+衰减告警 | — | — |
| 信号类型 | 离散 | 连续权重 w∈[-1,+1] | — | — | — | — | ✅ 4 策略全部连续 |
| 市场状态 | 不识别 | ✅ 5 种 regime | — | — | ✅ 动态权重 | — | — |
| 回测验证 | print+CSV | print+CSV | — | **✅ 持久化 DB, 可对比** | ✅ WFO+参数扫描 | — | — |
| 风控 | 7 条事前规则 | 7 条 | ✅ 行业+换手率已修 | — | ✅ 三层：事前+事后+衰减 | — | ✅ 事中监控 |
| 报告格式 | ✅ OKF frontmatter | OKF+因子归因 | — | — | — | ✅ OKF+风控+预测+社交 | — |
| 预测追踪 | prediction_id | prediction_id | — | — | — | ✅ 闭环验证+准确率 | — |
| 决策记忆 | 无 | 内存缓存 | — | — | — | ✅ DuckDB 持久化 | — |
| 社交情绪 | 无 | 无 | — | — | — | ✅ QQ 群聊管道 | — |
| MCP 工具 | 0 | 0 | — | **✅ 10 只读工具** | — | — | ✅ 全部 48 工具 |
| 策略数量 | 1 | 1 | — | — | — | — | ✅ 4 个 |
| Agent 分析 | 无 | 5 角色规则 | — | — | — | — | ✅ 规则+LLM |
| 健康检查 | 无 | ✅ 8 项 | — | — | — | — | — |
| 定时调度 | 无 | ✅ 交易日 16:00 | — | — | — | — | — |
| 测试覆盖 | 0 | 0 | — | ✅ 20+ 单元测试 | — | — | ✅ 核心模块 |
| 执行层 | 无 | 无 | — | — | — | ✅ paper broker | — |
| 数据分层 | 无 | 无 | — | — | — | — | ✅ raw/cleaned/research/published |
| 知识状态 | 无 | 无 | — | — | — | — | ✅ draft/verified/invalidated/obsolete |
| 适配器 | 引擎+适配器双轨 | — | — | — | — | — | ✅ 统一 adapter |

---

## 九、文件总清单

### Phase A 新建（✅ 全部完成）

```
QuantAgent/
  utils/
    logging.py              ✅ 结构化日志
  configs/
    settings.py             ✅ pydantic-settings
    app.yaml                ✅ 非敏感配置
    .env.example            ✅ 敏感字段模板
  data/
    market_fact.py          ✅ MarketFact + FactStore
  knowledge/
    report_template.py      ✅ OKF 元数据 schema
```

### Phase A 修改（✅ 全部完成）

```
QuantAgent/
  monitoring/notifier.py        ✅ print→logger, settings迁移
  data/storage.py               ✅ db_path from settings
  risk/risk_engine.py           ✅ RiskConfig from settings
  llm/extractor.py              ✅ api_key/model from settings
  llm/report_agent.py           ✅ OKF 8段 prompt + settings迁移
  llm/summarizer.py             ✅ settings迁移
  knowledge/knowledge_base.py   ✅ base_dir from settings
  scripts/backtest.py           ✅ params from settings
  scripts/daily_research.py     ✅ OKF 8段简化日报
```

### Phase B 新建/修改（✅ 全部完成）

```
QuantAgent/
  research/
    fusion.py               ← FusionEngine (含情报融合规则)
    regime_detector.py      ← MarketRegimeDetector
  knowledge/
    wiki_retriever.py       ← Wiki 检索器
  agents/
    committee.py            ← 5 角色规则引擎委员会
  strategies/
    registry.py             ← 装饰器注册表
    base/signal_validator.py  ← 信号验证器
    base/strategy_base.py   ← [修改] WeightVector + cash_deployment
    momentum/strategy.py    ← [修改] 适配新接口
  scripts/
    daily_research.py       ← [修改] 接入融合层 + Agent委员会
    health_check.py         ← 系统健康检查
    scheduler.py            ← 定时任务调度

docs/phase-b-issues.md       ← 实施记录
```

### Phase 0：止血（新增，约 5h）

```
新建:
  requirements-core.txt       ← 核心依赖 (<10 包)
  requirements-research.txt   ← 研究依赖 (akshare, vectorbt, riskfolio)
  requirements-integrations.txt ← 集成依赖 (qlib, vnpy, openbb, langchain)

修改:
  integrations/trading_agents.py  ← 修复降级 bug
  research/__init__.py            ← 补全导出
  configs/settings.py             ← 加 scheduler 字段
  configs/app.yaml                ← 加 schedule 配置段
  scripts/daily_research.py       ← 修复脆弱变量检查
  research/factors.py             ← print→logger
  research/backtest.py            ← print→logger
  scripts/backtest.py             ← print→logger

运维 (无代码):
  pip install -r requirements-research.txt  ← 安装 akshare
  python -m scripts update-data ...          ← 拉取真实数据
  在真实数据上验证 Phase B 全部模块           ← 手动验证
```

### Phase B Fixes：还债（约 6.5h）

```
新建:
  tests/test_data_schema.py        ← Event 模型一致性测试
  tests/test_factors.py            ← 因子计算正确性测试
  tests/test_risk_engine.py        ← 风控规则边界测试
  tests/test_momentum_strategy.py  ← 策略信号输出测试

修改:
  data/schema.py                   ← Event 模型统一 (canonical)
  news/schema.py                   ← Event 子类化
  llm/extractor.py                 ← 引用 data/schema.Event
  knowledge/knowledge_base.py      ← 统一 Event 存取
  risk/risk_engine.py              ← 行业集中度+换手率修复
  strategies/momentum/strategy.py  ← 复用 FactorEngine
```

### Phase C.1：地基（约 10h）

```
新建:
  tools/data_tools.py              ← MCP 行情/因子工具 (4个)
  tools/knowledge_tools.py         ← MCP 查询工具 (3个)
  tools/wiki_tools.py              ← MCP Wiki 工具 (2个)
  mcp_server/server.py             ← FastMCP 服务入口
  data/migrations/001_init.sql     ← 初始迁移

修改:
  scripts/backtest.py              ← 回测持久化 + CLI 增强
  data/storage.py                  ← backtest_runs + backtest_equity 表
  scripts/health_check.py          ← 回测持久化验证项
```

### Phase C.2：进阶（约 10h）

```
新建:
  research/walk_forward.py         ← WFO 引擎
  risk/stress_test.py              ← 压力测试
  risk/attribution.py              ← Brinson 归因
  risk/decay_detector.py           ← 策略衰减检测
  research/neutralizer.py          ← 因子中性化

修改:
  scripts/backtest.py              ← WFO 模式 + 参数扫描
  scripts/daily_research.py        ← 因子评估接入 Step 3
```

### Phase C.3：延伸（约 8h）

```
新建:
  knowledge/decision_memory.py     ← 决策记忆
  data/social_collector.py         ← QQ 群聊采集
  llm/social_analyzer.py           ← 社交情绪分析
  execution/broker/base.py         ← Paper broker 抽象接口
  execution/simulator/engine.py    ← 本地成交仿真

修改:
  scripts/daily_research.py        ← 预测追踪+决策记忆+社交情绪
  data/storage.py                  ← decision_memory 表
```

### Phase D：生态（约 22h）

```
新建:
  strategies/event_driven/         ← 事件驱动策略
  strategies/sentiment/            ← 情绪策略
  strategies/regime_switch/        ← 市场状态切换策略
  tools/risk_tools.py              ← MCP 风控工具
  tools/backtest_tools.py          ← MCP 回测工具

修改:
  agents/committee.py              ← AICriticAgent LLM 接入
  data/storage.py                  ← 数据分层重构
  knowledge/knowledge_base.py      ← 知识条目状态机
  integrations/                    ← 适配器统一 (3 对 engine/adapter)

填充:
  docs/wiki/entities/              ← OKF Wiki 内容
  docs/wiki/scenarios/
  docs/wiki/sources/
  docs/wiki/synthesis/
```

---

## 附录 A：参考项目清单

### 核心参考

| 项目 | 路径 | 借鉴内容 |
|------|------|---------|
| **loverMentor** | (外部项目，原开发机路径) | 五步分析流程（方法论→市场记忆→数据→验证→输出）、OKF Wiki 五维评分检索、facts/judgments 分离、事实验证体系、**社交情绪分类管道（搬用）** |
| **枫叶子 (fengyezi)** | (外部项目，原开发机路径) | Multi-Agent 规则委员会、ETF 整手优化、风险预算、现金部署回退、Walk-Forward 动态配置重选、决策记忆（1/3/5/10日事后验证）、情报-数据融合规则 |

### 参考项目（_reference/ 目录下）

| 项目 | 借鉴内容 |
|------|---------|
| FinRL | S→A→T→R 管线、连续权重向量 |
| Riskfolio-Lib | 组合优化、风险预算 |
| qlib | 因子评估框架（IC/ICIR） |
| VectorBT | 回测引擎、参数扫描 |
| systematic-trading-framework | WFO、IVS、Kelly 仓位 |
| SignalFlow | Meta-Labeling 模式（代码不可用，模式已记录） |
| TradingAgents | LLM 多 Agent 协作 |
| Magents | 中央风控体系 |

---

## 附录 B：深度代码审计（2026-07-02）

> 审计方法：逐文件阅读 QuantAgent/ 下所有 68 个源文件，对比架构文档与实现的一致性。
> 范围：14 个模块（strategies / research / risk / data / integrations / llm / monitoring / news / knowledge / configs / scripts / agents / utils / execution）

---

### B.1 严重问题 — P0（阻塞后续开发）

#### P0-1: 三套互不兼容的 Event 模型

项目存在三种不同的 `Event` 定义，字段不统一：

| 位置 | 类名 | 关键差异 |
|------|------|---------|
| `data/schema.py` | `Event` | event_id, timestamp, event_type, ticker, detail, source |
| `news/schema.py` | `Event` | event_id, source, event_type, title, tickers(复数!), body, confidence, tier, dedup_key |
| `llm/extractor.py` | `ExtractedEvent` | event_id, timestamp, source, event_type, ticker, company, detail, sentiment, impact_objects, time_window, confidence, tradability, tags |

**影响**：
- `daily_research.py:202-217` 保存事件时需要手动映射 12 个字段（脆弱的胶水代码）
- `FusionEngine` 使用 `news/schema.py` 的 Event，但 `knowledge_base.py` 存入的是 `llm/extractor.py` 的 ExtractedEvent
- 新增功能时开发者需要理解三套模型的差异才能正确使用

**建议修复**：在 `data/schema.py` 中定义唯一的 `Event` dataclass，`news/schema.py` 和 `llm/extractor.py` 通过继承或组合引用它。`knowledge_base.py` 统一存取这一个 Event 类型。

#### P0-2: `research/__init__.py` 导出不完整

`research/` 目录新增了 `FusionEngine`、`MarketRegimeDetector`、`MarketRegime`、`MarketSnapshot`，但 `__init__.py` 未导出：

```python
# 当前 research/__init__.py
from .factors import FactorEngine
from .backtest import BacktestEngine
from .evaluator import FactorEvaluator
# 缺失: FusionEngine, MarketRegimeDetector, MarketRegime, MarketSnapshot
```

**影响**：`daily_research.py` 被迫使用深层 import 路径（`from research.fusion import FusionEngine`），破坏模块封装。

**建议修复**：在 `research/__init__.py` 中补全导出。

#### P0-3: `configs/settings.py` 缺少 scheduler 字段

`scheduler.py:91-92` 读取 `settings.schedule_data_update_time` 和 `settings.schedule_research_time`，但 `settings.py` 和 `app.yaml` 都未定义这两个字段。代码只能 fallback 到硬编码值 `'15:30'`/`'16:00'`。

**建议修复**：在 `app.yaml` 中添加 `schedule` 段，在 `settings.py` 中添加对应 pydantic Field。

---

### B.2 高优先级 — P1（Phase C 前应修复）

#### P1-1: 风控引擎两个检查是空壳

| 检查项 | 位置 | 当前行为 | 缺失 |
|--------|------|---------|------|
| 行业集中度 | `risk/risk_engine.py:195` | `# TODO: 接入行业分类数据`，始终返回 `[]` | 需要申万/中信行业分类数据 |
| 换手率限制 | `risk/risk_engine.py:201` | `# TODO: 接入价格数据`，始终返回 `[]` | 需要当日成交量数据 |

**影响**：这两项风控检查形同虚设。行业集中度过高是 A 股常见的回撤原因（如 2020 年消费抱团瓦解），换手率异常是流动性风险的前兆。

#### P1-2: 因子计算重复实现

`strategies/momentum/strategy.py:prepare_features()` 自行计算动量/RSI/量比，而 `research/factors.py` 已有完全相同的 25 个注册因子。两套实现各自维护。

**影响**：
- 因子逻辑不一致风险（一处改了另一处没改）
- 策略无法利用 FactorEngine 的 `@register` 机制动态切换因子

**建议修复**：策略的 `prepare_features()` 改为调用 `FactorEngine.compute_all(df)`，而非自己算。

#### P1-3: `daily_research.py` 中的脆弱变量检查

`daily_research.py:168`:
```python
if 'snapshot' in dir():   # ← 脆弱：依赖变量在 try 块内定义
    review_snapshot = snapshot
```
如果前面的 try 块抛出异常，`snapshot` 未定义，`dir()` 返回空。这在函数作用域内会静默失败。

**建议修复**：显式初始化 `snapshot = None` 在 try 块之前。

#### P1-4: 执行层完全缺失

`execution/broker/__init__.py` 和 `execution/simulator/__init__.py` 只有空包标记。整个 `execution/` 模块不存在任何实现。

虽然有 `integrations/vnpy_engine.py` 提供 CTP 连接能力，但缺少统一的订单执行抽象：
- 无 OrderManager（订单生命周期管理）
- 无 SlippageModel（滑点模型）
- 无 FillSimulator（成交模拟）
- 无 ExecutionReport（执行报告/成交分析）

**影响**：回测和实盘之间缺少关键的"仿真盘"环节。回测假设完美成交，仿真盘才能暴露真实流动性问题。

---

### B.3 中优先级 — P2（Phase C/D 期间修复）

#### P2-1: 集成层并行实现（引擎 vs 适配器）

`integrations/` 下每个外部项目存在两套代码：

| 旧引擎（直接使用第三方对象） | 新适配器（转换为内部类型） | 状态 |
|------|------|------|
| `qlib_engine.py` | `qlib_adapter.py` | 两套都可用，功能重叠 |
| `trading_agents.py` | `trading_agents_adapter.py` | 两套都可用，功能重叠 |
| `vnpy_engine.py` | `vnpy_adapter.py` | 两套都可用，功能重叠 |

重构进行到一半。旧引擎仍在被使用（如 `daily_research.py` 未引用任何 adapter），新适配器的转换逻辑虽有但未被调用。

**建议**：Phase D 统一使用 adapter 层，废弃旧 engine 的对外接口（保留内部实现供 adapter 调用）。

#### P2-2: 两个 Tier-1 新闻采集器未实现

`news/collector.py` 中：
- `CNInfoCollector`（巨潮资讯）— 标注 `# TODO`，仅空壳
- `SECEdgarCollector`（SEC EDGAR）— 标注 `# TODO`，仅空壳

巨潮资讯（cninfo.com.cn）是 A 股法定信息披露平台，属于最高信源等级。当前 A 股新闻只能通过 AKShare 间接获取，缺少一手信源。

#### P2-3: 零测试覆盖

`tests/__init__.py` 是空文件，项目没有任何单元测试或集成测试。

**影响**：重构风险高。如 P0-1 的 Event 模型统一化，缺少测试意味着只能靠手工验证。

**建议**：至少在 Phase C 前为核心模块添加测试：
- `data/schema.py` — schema 一致性测试
- `research/factors.py` — 因子计算正确性测试（用已知数据验证）
- `risk/risk_engine.py` — 风控规则边界条件测试

#### P2-4: 因子评估未接入每日流水线

`research/evaluator.py` 提供了完整的 IC/ICIR/分组收益/衰减检测，但 `daily_research.py` 从未调用它。因子计算后直接保存，没有评估反馈。

**影响**：IC 衰减、因子失效等信号不会被自动检测。这是"因子全生命周期管理"中的关键缺口。

---

### B.4 低优先级 — P3（已知限制，已有计划）

| # | 问题 | 位置 | 备注 |
|---|------|------|------|
| 1 | MemoryAgent 是 stub | `agents/committee.py` | Phase C 接入 decision_memory |
| 2 | AICriticAgent 是 stub | `agents/committee.py` | Phase D 接入 LLM |
| 3 | 告警 webhook 通知是空函数 | `monitoring/alerts.py:152` | `_send_notification()` 仅 `pass` |
| 4 | 决策记忆用进程内缓存 | `strategies/base/signal_validator.py` | Phase C 接入 DuckDB |
| 5 | 层级压缩 pipeline 未接入 | `knowledge/knowledge_base.py` | 压缩方法已定义，无自动触发 |
| 6 | 拆股调整未实现 | `data/cleaner.py:adjust_for_splits()` | 未提供 split_ratio 时仅返回原 df |
| 7 | `docs/wiki/` 目录不存在 | `knowledge/wiki_retriever.py` | 始终 fallback 到 16 个内置条目 |
| 8 | Qlib LightGBM 模型训练未使用 | README Phase 2 标记 `[ ]` | 因子模型仍是纯规则 |
| 9 | 日报未用新 OKF 渲染器 | `knowledge/daily/2026-07-02.md` | 用的是手动拼接而非 `render_okf_report()` |
| 10 | print() 残留 | `research/factors.py`, `research/backtest.py`, `scripts/backtest.py`, `scripts/daily_research.py` | 约 20+ 处仍用 print 而非 logger |

---

### B.5 模块完成度评估

| 模块 | 完成度 | 评价 |
|------|--------|------|
| `data/` | 95% | schema/provider/storage/cleaner/aligner 全部完整，仅 market_fact 略独立 |
| `research/` | 90% | 因子/回测/评估/融合/regime 全部实现，仅 neutralizer 缺失，导出不全 |
| `knowledge/` | 90% | 知识库/wiki/报告模板完整，仅压缩 pipeline 未自动化和决策记忆未接入 |
| `risk/` | 70% | 核心 7 条规则可用，但行业/换手率检查是空壳，事后归因全缺 |
| `strategies/` | 40% | momentum 完整，3 个策略空壳，因子计算重复 |
| `llm/` | 85% | 三个模块完整，OKF prompt 已更新，缺重试/限流 |
| `news/` | 75% | pipeline/schema 设计优秀，2 个 tier-1 采集器缺失 |
| `monitoring/` | 80% | 指标/告警/通知完整，webhook 通知是空函数 |
| `integrations/` | 70% | 4 个外部项目都可连接，但 engine/adapter 双轨制待统一 |
| `agents/` | 60% | 5 角色委员会框架完整，2 个 agent 是 stub |
| `scripts/` | 85% | 核心流程 + 健康检查 + 调度 + 回测 + 数据更新 全覆盖 |
| `configs/` | 85% | pydantic-settings 设计优秀，缺 scheduler 字段 |
| `execution/` | 0% | 完全空目录 |
| `tests/` | 0% | 完全空目录 |

**整体评分：72/100**

核心引擎（数据→因子→回测→研究）扎实，但生产就绪度不足：无测试、执行层缺失、风控有空壳、schema 不一致。
