# 未来计划

> 生成日期：2026-07-03 | 最后更新：2026-07-09（Phase 2/3 归档，Phase 4 计划新增）
> 核心定位：**MCP Server** — 把量化研究能力暴露为工具供外部 Agent 调用

---

## 一、已完成工作回顾

| # | 事项 | 状态 | 说明 |
|---|------|------|------|
| 1 | **架构定位** | ✅ | 确定为 MCP Server，移除内部 LLM 调用 |
| 2 | **Phase 0** | ✅ | 股票池扩充、事件冷启动入库、LLM 模块清理 |
| 3 | **基本面存储+因子** | ✅ | baostock → DuckDB，新增 ROE/PE/营收/利润 4 因子 |
| 4 | **行业中性化** | ✅ | 截面 OLS 回归中性化（行业哑变量 + log市值） |
| 5 | **新闻接入** | ✅ | AKShare 东方财富+财联社，日报已启用 |
| 6 | **Phase B 管线** | ✅ | MarketRegimeDetector / WikiRetriever / FusionEngine / AgentCommittee |
| 7 | **Phase 1 验证** | ✅ | P1 流水线跑通（10/10 组件测试，全流程运行正常） |
| 8 | **文档整理** | ✅ | 旧文档清理 + CLAUDE.md 重写 + docs/README.md 索引 + 归档 |

**当前数据库状态**（P1 验证后快照，行数以 `python -m scripts.db_stats` 实时输出为准）：

| 指标 | P1 验证后 |
|------|----------|
| stock_daily | 日线数据（行数以 db_stats 为准） |
| factors | 因子值（注册 29 个，实际计算数以 db_stats 为准） |
| index_daily | 指数日线数据 |
| events | 结构化新闻事件 |
| decision_memory | 决策记忆 |
| backtest_runs | 回测记录（4 策略 × 多标的） |
| 单元测试 | 全部通过（以 `pytest tests/` 输出为准） |
| 健康检查 | 通过（以 `python -m scripts.health_check` 输出为准） |

---

## 二、已完成阶段（已归档）

| 阶段 | 计划文档 | 状态 |
|------|---------|------|
| Phase 2 | [archive/phase-2-implementation-plan.md](../plan/archive/phase-2-implementation-plan.md) | ✅ 大部分完成（baostock、批量回测、MCP 写工具；scheduler 部分完成） |
| Phase 3 | [archive/phase-3-improvement-plan.md](../plan/archive/phase-3-improvement-plan.md) | ✅ 大部分完成（Skills、MCP 自动发现、DuckDB 优化、I/O 优化、dry-run、因子参数化） |

> 已完成的验收标准和数据质量改进计划也已归档至 `docs/plan/archive/`。

---

## 四、后续待办（非 Phase 4 范围）

| # | 事项 | 说明 | 前置 |
|---|------|------|------|
| C-1 | **MCP 写工具深化** | 策略配置变更、参数调整 | P2.4 |
| C-2 | **AICriticAgent LLM 接入** | 委员会 LLM 模式 | — |
| C-3 | **社交情绪管道** | go-cqhttp → LLM 情绪分析 | 外部后端 |
| C-4 | **Wiki 知识库构建** | 持续构建量化知识图谱 | — |
| C-5 | **数据分层重构** | raw/cleaned/research/published 分离 | — |
| C-6 | **集成适配器统一** | 废弃旧 engine，统一 adapter | — |

---

## 五、Phase 4：从"查询工具"到"会进化的研究平台"

> 详细计划见 [`docs/plan/phase-4-improvement-plan.md`](../plan/phase-4-improvement-plan.md)（唯一 active plan）
> 核心诊断：骨架搭好了但上半身没长出来——数据有了但分析不及时，日报有了但高阶报告缺失，回测跑了但经验不积累
> 执行原则：基于现有代码准确改哪里，复用已有 API，不重造轮子

### 5.1 执行顺序（P0 前置 → B1 → B2 → ADR → B4 → B3 条件触发）

```
P0  前置能力（~6h）← 解锁 B1，否则 B1 是空中楼阁
  ├── P0.1 拆分独立增量更新任务        2h
  ├── P0.2 正式交易日历模块            2h
  └── P0.3 storage 层 freshness API    2h

B1  关键基础设施（🔴 ~9h）
  ├── B1.1 Scheduler → systemd         3h   (依赖 P0.1 + P0.2)
  ├── B1.2 数据新鲜度 MCP 工具         2h   (依赖 P0.3)
  └── B1.3 周报/月报/季报生成          4h   (复用 KnowledgeBase)

B2  打通闭环（🟡 ~7h）
  ├── B2.1 回测→决策记忆自动写入       2h   (集成任务，复用 DecisionMemory)
  ├── B2.2 因子共线性报告              2h
  └── B2.3 假设自动生成                3h   (复用 HYPOTHESIS_TRANSITIONS)

ADR 委员会去留决策（~1h）← 提前，不拖到最后
  └── ADR-001 Agent 委员会：删或接 LLM  1h

B4  清理加固（🔵 ~5h）
  ├── B4.1 DuckDB 自动备份             1h
  ├── B4.2 standard 模式参数扫描       1h   (walk-forward 已支持)
  └── B4.3 执行 realism                2h

B3  体验优化（🟠 条件触发，~6h）← 仅当 profiling 证明延迟影响使用时
  ├── B3.1 慢工具缓存                  2h
  ├── B3.2 便利查询工具                2h
  └── B3.3 策略 leaderboard            2h
```

### 5.2 关键工程约束

- **假设生命周期**：复用现有 `HYPOTHESIS_TRANSITIONS`（draft/active/verified/invalidated/obsolete/rejected），禁止另造第二套语义
- **高阶报告存储**：复用 `KnowledgeBase.save_report(weekly/monthly/quarterly/annual)`，不另起 published schema
- **决策记忆**：B2.1 是集成任务（在 `scripts/backtest.py` 调 `record_decision`），不是新系统建设
- **回测主链路**：`research/backtest.py` + `scripts/backtest.py`（原计划写的 `strategy/backtest_engine.py` 不存在）
- **每个任务**：必须有单元测试 + 集成测试 + 回滚路径

### 5.3 验收里程碑

| 里程碑 | 完成标志 | 预期效果 |
|--------|---------|----------|
| M0: P0 完成 | 独立增量更新 + 交易日历 + freshness API | B1 不再是空中楼阁 |
| M1: B1 完成 | scheduler 自动跑 + 周报可查 + freshness MCP | 数据不再滞后，知识金字塔有上层 |
| M2: B2 完成 | decision_memory > 50 + 假设 > 30 | 回测→决策→验证闭环打通 |
| M3: ADR 完成 | 委员会去留落地，健康检查 0 skip | 系统无空壳模块 |
| M4: B4 完成 | 备份 + 参数扫描 + realism | 系统加固完成 |
| M5: B3（条件） | 仅在 profiling 证明需要时 | 交互式研究流畅 |

---

## 六、当前建议优先级

```
Phase 4（~28h）
  P0  （6h）  独立增量更新 + 交易日历 + freshness API
  B1  （🔴 9h）scheduler→systemd + 数据新鲜度 MCP + 周月报（复用 KnowledgeBase）
  B2  （🟡 7h）回测闭环 + 因子共线性 + 假设自动生成（复用现有状态机）
  ADR （1h）  Agent 委员会去留（提前决策）
  B4  （🔵 5h）备份 + 参数扫描 + 执行 realism
  B3  （🟠 6h）缓存 + 便利查询 + leaderboard（仅 profiling 证明需要时启动）
```
