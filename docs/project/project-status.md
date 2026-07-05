# 项目现状报告

> 生成日期：2026-07-06 | 范围：quant-system 全模块

---

## 一、一句话总览

A 股量化研究系统，**数据→因子→回测→策略→风控→仿真** 完整闭环，可直接用于研究。Phase A 全部完成，9 个 Bug 已修复，文档已整理合并。执行层可仿真但无实盘对接，新闻源已接入，社交情绪因缺后端而空载。

---

## 二、数据层

| 项目 | 状态 | 详情 |
|------|------|------|
| **行情数据** | ✅ 正常 | baostock(优先) → AKShare(回退)，187,482 条日线 |
| **指数数据** | ✅ 正常 | AKShare 回退，6,543 条 |
| **基本面** | ✅ 已接入 | baostock 5 种报表 API，research.financials 表 (已入库 1 只股票) |
| **估值** | ✅ 正常 | AKShare stock_value_em，PE/PB/市值 |
| **行业分类** | ✅ 正常 | baostock query_stock_industry，全市场映射 |
| **北向资金** | ✅ 正常 | AKShare 北向净流入 |
| **融资融券** | ✅ 正常 | AKShare |
| **新闻** | ✅ 已接入 | news/aggregator.py + AKShareCollector，真实 A 股新闻，日报已启用 |
| **社交情绪** | ⚠️ 空载 | SocialCollector 存在，但无 go-cqhttp 后端，返回空 |

**数据源依赖**：
- baostock: 核心行情 + 基本面，免费稳定
- AKShare: 估值 + 新闻 + 北向资金，免费但爬虫易变
- pytdx: 本机网络不可达（连通测试全部失败），代码有降级路径

---

## 三、因子引擎

| 项目 | 状态 | 详情 |
|------|------|------|
| **注册因子数** | ✅ 29 个 | 25 OHLCV + 4 基本面 (roe/pe_ttm/revenue_growth/profit_growth) |
| **因子评估** | ✅ 已实现 | IC/ICIR 每日评估 + 衰减检测 (DecayDetector) |
| **因子中性化** | ✅ 已实现 | FactorNeutralizer 支持回归法和组内去均值法 |
| **中性化流水线** | ✅ 已接入 | daily_research 新增截面回归中性化 (行业+市值) |
| **因子存储** | ✅ 675,664 条 | public.factors + research.factors 双写，含 neutralized_value |

---

## 四、研究层

| 项目 | 状态 | 详情 |
|------|------|------|
| **StockAnalyzer** | ✅ 正常 | 行情分析 + 技术指标 + 同业对比 + 关键价位 + 情景推演 |
| **BacktestEngine** | ✅ 正常 | VectorBT 封装，参数扫描 |
| **FactorEvaluator** | ✅ 正常 | IC/ICIR/分组收益 |
| **WalkForward** | ✅ 已实现 | WFO 引擎 (research/walk_forward.py) |
| **FusionEngine** | ✅ 已实现 | 多源融合 + 情报-数据融合规则 |
| **MarketRegimeDetector** | ✅ 已实现 | 5 种市场状态识别 |
| **FactorNeutralizer** | ✅ 已实现 | 回归中性化 + 组内去均值 |

---

## 五、策略层

| 策略 | 状态 | 详情 |
|------|------|------|
| **MomentumStrategy** | ✅ 完整 | 动量突破策略，含 prepare→signal→sizing→risk 全管线 |
| **EventDrivenStrategy** | ✅ 完整 | 事件→信号映射、时间衰减、多事件叠加、置信度加权 |
| **SentimentStrategy** | ✅ 完整 | 社交/新闻情绪→信号映射，含反指规则和情绪调制 |
| **RegimeSwitchStrategy** | ✅ 完整 | 市场状态检测→子策略选择，含冷却期和切换阈值 |

4 个策略均已注册（`@register_strategy`），全部实现 StrategyBase 接口。

---

## 六、风控层

| 项目 | 状态 | 详情 |
|------|------|------|
| **7 条事前规则** | ✅ 正常 | 仓位上限、杠杆限制、集中度、波动率、流动性、相关度、回撤 |
| **行业集中度** | ✅ 正常 | 聚合持仓 > 配置上限时返回警告 |
| **换手率限制** | ✅ 正常 | 每日换手率超限检测 |
| **StressTest** | ✅ 已实现 | 4 个历史危机场景 (2015/2018/2020/2024) |
| **Brinson 归因** | ✅ 已实现 | 配置效应 + 选股效应 + 交互效应 |
| **DecayDetector** | ✅ 已实现 | 滚动胜率 + IC 衰减检测 |
| **组合优化** | ✅ 已实现 | Riskfolio-Lib 封装 |

---

## 七、知识层

| 项目 | 状态 | 详情 |
|------|------|------|
| **KnowledgeBase** | ✅ 正常 | 日报/周报/月报/季报/年报 分级存储 |
| **日报** | ✅ 29 篇 | knowledge/daily/ 目录 |
| **WikiRetriever** | ✅ 已实现 | 五维评分检索 (标题/关键词/标签/市场状态/时间周期) |
| **Wiki 内容** | ⚠️ 6 个条目 | entities(2), scenarios(2), sources(1), synthesis(1) — 偏少 |
| **ReportTemplate** | ✅ 正常 | OKF 8 段格式 |
| **DecisionMemory** | ✅ 已实现 | 决策记录 + 1/3/5/10 日事后收益回填 |
| **EventExtractor** | ✅ 正常 | LLM 新闻事件抽取 |
| **ReportAgent** | ✅ 正常 | LLM 日报生成 (OKF 格式) |
| **market_fact** | ✅ 正常 | MarketFact + FactStore |
| **Event 模型** | ✅ 已统一 | news.schema.Event 继承 data.schema.Event，llm 共用同一模型 |

---

## 八、基础设施

| 项目 | 状态 | 详情 |
|------|------|------|
| **日志系统** | ✅ 正常 | loguru，控制台彩色 + 文件轮转 + JSONL |
| **配置管理** | ✅ 正常 | pydantic-settings，~80 参数 |
| **数据库** | ✅ 正常 | DuckDB 110MB，含分层 schema (raw/cleaned/research/published) |
| **DB 迁移** | ✅ 已实现 | 2 个迁移文件已应用 |
| **健康检查** | ✅ 已实现 | scripts/health_check.py |
| **定时调度** | ✅ 已实现 | scripts/scheduler.py |
| **告警** | ⚠️ 空壳 | webhook 通知是空函数 `pass` |
| **MCP Server** | ✅ 30 个工具 | 9 data + 10 risk + 11 knowledge，stdio transport |
| **Paper Broker** | ✅ 仿真引擎 | SimulationEngine 含权重→订单、滑点、佣金、最小交易单位(100股) |
| **测试** | ✅ 122 passed | 11 个测试文件，合成数据，覆盖核心模块 |

---

## 九、执行层

`execution/` 包含完整的本地仿真引擎：

- **SimulationEngine** — 权重向量→订单转换，含滑点/佣金/印花税模型
- **BrokerBase** — 抽象接口定义（place_order/cancel_order/get_positions）
- **订单生命周期** — submitted→accepted→filled/cancelled/rejected
- **A 股约束** — 最小交易单位 100 股/手，资金不足部分成交
- **无实盘对接** — 仅仿真，无 CTP/IB 等网关连接

---

## 十、集成层

4 个外部项目可连接，但 engine/adapter 双轨制：

| 项目 | 引擎 | 适配器 | 状态 |
|------|------|--------|------|
| Qlib | qlib_engine.py | qlib_adapter.py | 双轨运行 |
| TradingAgents | trading_agents.py | trading_agents_adapter.py | 双轨运行 |
| vnpy | vnpy_engine.py | vnpy_adapter.py | 双轨运行 |
| OpenBB | openbb_data.py | — | 单一接口 |

---

## 十一、数据统计

| 表 | 行数 |
|----|------|
| stock_daily | 187,482 |
| index_daily | 6,543 |
| factors | 675,664 |
| backtest_runs | 21 |
| backtest_equity | 3,102 |
| events | 0 |
| predictions | 1 |
| decision_memory | 3 |
| research.financials | 2 (1 只股票) |

---

## 十二、测试状态

- **单元测试**: 122/122 通过 (pytest tests/)
- **覆盖模块**: 因子计算、策略注册、风控规则、压力测试、仓储层双写、知识库、Event 模型

---

## 十三、主要短板

### P0 — 阻塞
1. **无实盘/模拟执行** — 仿真引擎可用，但无定时执行和实盘网关接入
2. **社交情绪空载** — 缺 go-cqhttp 后端，SocialCollector 返回空

### P1 — 高优先级
3. **无定时执行** — scheduler.py 写好了但从未在真实数据上跑通
4. **告警空壳** — webhook 通知是空函数 `pass`

### P2 — 中优先级
5. **print 残留** — 部分模块仍用 print 而非 logger
6. **引擎/适配器双轨** — Qlib/TradingAgents/vnpy 各两套代码
7. **Wiki 内容偏少** — 仅 6 个条目，需扩充
8. **基本面数据不完整** — 仅 1 只股票，需批量拉取
