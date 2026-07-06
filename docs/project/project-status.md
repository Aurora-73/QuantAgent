# 项目现状报告

> 生成日期：2026-07-06 | 最后更新：2026-07-06（Phase 0 数据补齐 + 事件冷启动）| 范围：quant-system 全模块

---

## 零、架构定位（必读）

### 0.1 项目定位

本项目是 **MCP Server**：把行情、因子、回测、风控、知识库能力暴露成工具，供 Claude / Codex / 其他 Agent 调用。

**MCP Server 不负责实盘自动交易，但仍需要研究闭环。** 数据、因子、回测、风控、预测验证这些闭环仍然重要——只是闭环的终点不是自动下单，而是给外部 Agent / 用户提供**可验证的研究工具和结果**。

### 0.2 LLM API 与 MCP 的边界

| 层 | 定位 | 当前状态 |
|----|------|---------|
| **MCP** | 系统把行情、因子、回测、风控、知识库能力暴露成工具，给 Claude/Codex/其他 Agent 调用 | ✅ 核心定位，工具清单见 `python -m mcp_server.server --list-tools` |
| **LLM API** | quant-system 内部主动调用模型（新闻事件抽取、日报生成、多 Agent 分析） | ⚠️ **当前阶段移除**，外部 Agent 自带 LLM 能力 |

**当前决策**：移除 `llm/` 模块对外的 LLM 调用，只做 MCP。LLM 能力由调用方（Claude/Codex 等 Agent）提供，不在 quant-system 内部内置。

### 0.3 当前阶段目标

**稳定 MCP + 数据/研究/回测/风控工具闭环**：

1. 数据层（行情/基本面/估值/新闻）— 真实可用
2. 研究层（因子计算/回测/WFO/中性化）— 闭环可用
3. 风控层（事前规则/压力测试/Brinson 归因）— 闭环可用
4. MCP 工具层（见 `python -m mcp_server.server --list-tools`）— Claude/Codex 可稳定调用

**不作为当前 P0**：OPENAI_API_KEY、内部 ReportAgent 调用、LLM 事件抽取、多 Agent 投研委员会、社交情绪（go-cqhttp）。

---

## 一、一句话总览

A 股量化研究 MCP Server，**数据→因子→回测→策略→风控** 完整闭环，MCP 工具可被 Claude/Codex 调用（清单见 `python -m mcp_server.server --list-tools`）。Phase A 全部完成，9 个 Bug 已修复，文档已整理合并。新闻源已接入，社交情绪因缺后端而空载（已后移到 Phase C/D）。LLM 模块计划移除（详见 §0.2）。

---

## 二、数据层

| 项目 | 状态 | 详情 |
|------|------|------|
| **行情数据** | ✅ 正常 | baostock(优先) → AKShare(回退)，452,054 条日线，301 只股票 |
| **指数数据** | ✅ 正常 | AKShare 回退，7,515 条 |
| **基本面** | ✅ 已接入 | baostock 5 种报表 API，research.financials 表 604 条，301 只股票（Q4 完整 + Q1 完整） |
| **估值** | ✅ 正常 | AKShare stock_value_em，PE/PB/市值 |
| **行业分类** | ✅ 正常 | baostock query_stock_industry，全市场映射 |
| **北向资金** | ✅ 正常 | AKShare 北向净流入 |
| **融资融券** | ✅ 正常 | AKShare |
| **新闻** | ✅ 已接入 | news/aggregator.py + AKShareCollector，真实 A 股新闻，日报已启用。events 表 106 条（含冷启动） |
| **社交情绪** | ⚠️ 空载 | SocialCollector 存在，但无 go-cqhttp 后端，返回空 |

**数据源依赖**：
- baostock: 核心行情 + 基本面，免费稳定
- AKShare: 估值 + 新闻 + 北向资金，免费但爬虫易变
- pytdx: 本机网络不可达（连通测试全部失败），代码有降级路径

---

## 三、因子引擎

| 项目 | 状态 | 详情 |
|------|------|------|
| **注册因子数** | ✅ 29 个 | 25 OHLCV + 4 基本面 (roe/pe_ttm/revenue_growth/profit_growth)，factors 表实际存储 26 个（3 个未计算） |
| **因子评估** | ✅ 已实现 | IC/ICIR 每日评估 + 衰减检测 (DecayDetector) |
| **因子中性化** | ✅ 已实现 | FactorNeutralizer 支持回归法和组内去均值法 |
| **中性化流水线** | ✅ 已接入 | daily_research 新增截面回归中性化 (行业+市值) |
| **因子存储** | ✅ 11,354,151 条 | research.factors 表 + factor_evaluation 表，含 neutralized_value |

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
| **EventExtractor** | ⚠️ 待移除 | LLM 新闻事件抽取 — 随 LLM 模块清理移除（详见 §0.2） |
| **ReportAgent** | ⚠️ 待移除 | LLM 日报生成 (OKF 格式) — 随 LLM 模块清理移除（详见 §0.2） |
| **market_fact** | ✅ 正常 | MarketFact + FactStore |
| **Event 模型** | ✅ 已统一 | news.schema.Event 继承 data.schema.Event，llm 共用同一模型 |

---

## 八、基础设施与 MCP 工具层

### 8.1 MCP 工具层（核心定位，详见 §0.1）

> 工具数量不手写，事实来源：`python -m mcp_server.server --list-tools`

| 项目 | 状态 | 详情 |
|------|------|------|
| **MCP Server** | ✅ | stdio transport，工具清单见上方命令 |
| **工具覆盖** | ✅ | 行情查询、因子计算、回测触发、风控检查、Wiki 检索、健康检查等 |
| **调用方** | Claude / Codex / 其他 Agent | 外部 Agent 通过 MCP 协议调用工具，自带 LLM 能力 |

### 8.2 基础设施

| 项目 | 状态 | 详情 |
|------|------|------|
| **日志系统** | ✅ 正常 | loguru，控制台彩色 + 文件轮转 + JSONL |
| **配置管理** | ✅ 正常 | pydantic-settings，~80 参数 |
| **数据库** | ✅ 正常 | DuckDB 110MB，含分层 schema (raw/cleaned/research/published) |
| **DB 迁移** | ✅ 已实现 | 2 个迁移文件已应用 |
| **健康检查** | ✅ 已实现 | scripts/health_check.py |
| **定时调度** | ✅ 已实现 | scripts/scheduler.py |
| **告警** | ⚠️ 部分实现 | Server酱推送已实现(SendChanNotifier)，AlertManager._send_notification 未对接 |
| **Paper Broker** | ✅ 仿真引擎 | SimulationEngine 含权重→订单、滑点、佣金、最小交易单位(100股) |
| **测试** | ✅ 139 passed | 11 个测试文件，合成数据，覆盖核心模块 |

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

> 数据日期：2026-07-06，来源：`python -m scripts health-check` + DuckDB 统计

| 表 | 行数 | 说明 |
|----|------|------|
| stock_daily | 231,481 | 301 只股票日线 |
| index_daily | 3,148 | 指数日线 |
| financials | 604 | 301 只股票基本面（Q4+Q1 完整） |
| factors | 675,664 | 26 个因子（注册 29 个，3 个未计算，待 Linux 服务器补算） |
| backtest_runs | 21 | 回测结果记录 |
| backtest_equity | 3,102 | 回测权益曲线 |
| events | 56 | 事件表（已冷启动，新闻事件） |
| predictions | 1 | 预测记录 |
| decision_memory | 3 | 决策记忆 |
| market_facts | 2 | 市场事实 |
| lessons | 0 | 教训库 |
| schema_version | 2 | DB 迁移版本 |

---

## 十二、测试状态

- **单元测试**: 139/139 通过 (pytest tests/)
- **覆盖模块**: 因子计算、策略注册、风控规则、压力测试、仓储层双写、知识库、Event 模型

---

## 十三、主要短板

> 注：本项目是 MCP Server（详见 §0.1），不追求实盘交易闭环。"无实盘/模拟执行"不再作为 P0 短板。

### P0 — 阻塞（当前阶段）
1. **LLM 模块清理** — 移除 `llm/` 目录的 ReportAgent/Extractor/SocialAnalyzer，简化 `daily_research.py` 中 Step 3/4 的 LLM 调用，清理 `configs/settings.py` 中 LLM 配置段（详见 §0.2）
2. ~~**事件表为空**~~ — ✅ 已解决（2026-07-06），冷启动 56 条新闻事件入库，见 `scripts/cold_start_events.py`
3. **预测/决策闭环未启动** — predictions=1, decision_memory=3，验证闭环不通（需 Linux 服务器跑 daily_research 验证）

### P1 — 高优先级
4. **无定时执行** — scheduler.py 写好了但从未在真实数据上跑通（需 Linux 服务器验证，见 `docs/plan/linux-server-test-plan.md`）
5. **告警部分实现** — Server酱推送已实现，AlertManager 未对接（与 scheduler 一起验收）
6. ~~**股票池接近完整**~~ — ✅ 已解决（2026-07-06），301 只股票 231,481 条记录
7. ~~**基本面数据不完整**~~ — ✅ 已解决（2026-07-06），301 只股票 604 条记录（Q4+Q1 完整）

### P2 — 中优先级（暂不做）
8. **社交情绪空载** — 缺 go-cqhttp 后端，SocialCollector 返回空（已后移到 Phase C/D）
9. **print 残留** — 部分模块仍用 print 而非 logger
10. **引擎/适配器双轨** — Qlib/TradingAgents/vnpy 各两套代码
11. **Wiki 内容偏少** — 仅 6 个条目
