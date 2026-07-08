# 未来计划

> 生成日期：2026-07-03 | 最后更新：2026-07-06（Phase 2 计划更新）
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

## 二、当前执行阶段：Phase 2

> 详细计划见 [`docs/plan/phase-2-implementation-plan.md`](../plan/phase-2-implementation-plan.md)

| # | 任务 | 预计耗时 | 说明 |
|---|------|---------|------|
| P2.1 | **baostock 稳定数据源** | 15min | 替换 AKShare 间歇性失败 |
| P2.2 | **定时调度器跑通** | 2h | 日终自动研究流程 + 告警对接 SendChan |
| P2.3 | **4 策略样本外回测验证** | 3-4h | 批量回测 + 结果入库，支持 --compare |
| P2.4 | **MCP 写工具** | 2h | run_backtest / update_data / daily_research |
| P2.5 | **Walk-Forward CLI** | 3h | 参数扫描命令行入口 + JSON 输出 |

### 验收标准

- [ ] P2.1: baostock 安装并验证通过
- [ ] P2.2: scheduler --dry-run 输出正确，--run-now 完成一次流程
- [ ] P2.2: 告警对接 SendChan 成功
- [ ] P2.3: 4 策略批量回测脚本可用，结果写入 backtest_runs 表
- [ ] P2.4: MCP run_backtest / update_data 工具可用
- [ ] P2.5: walkforward CLI 命令可用，参数扫描输出有效
- [ ] **整体**：健康检查 8 pass, 0 warn, 0 fail

---

## 三、后续阶段

| # | 事项 | 说明 | 前置 |
|---|------|------|------|
| C-1 | **MCP 写工具深化** | 策略配置变更、参数调整 | P2.4 |
| C-2 | **AICriticAgent LLM 接入** | 委员会 LLM 模式 | — |
| C-3 | **社交情绪管道** | go-cqhttp → LLM 情绪分析 | 外部后端 |
| C-4 | **Wiki 知识库构建** | 持续构建量化知识图谱 | — |
| C-5 | **数据分层重构** | raw/cleaned/research/published 分离 | — |
| C-6 | **集成适配器统一** | 废弃旧 engine，统一 adapter | — |

---

## 四、当前建议优先级

```
Phase 2（~10h）
  ├── P2.1 baostock 安装      — 数据源稳定
  ├── P2.2 scheduler 调度器    — 自动化
  ├── P2.3 策略回测验证        — 可验证
  ├── P2.4 MCP 写工具          — Agent 可操作
  └── P2.5 Walk-Forward CLI    — 参数优化
```
