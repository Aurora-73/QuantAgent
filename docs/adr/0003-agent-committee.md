# ADR-0003: Agent 委员会去留与 MCP 化

> 决定多 Agent 委员会的命运：移除内部 LLM、保留规则评审、整体封装为 MCP 工具。

---

## 状态

**Implemented**

## 上下文

`agents/committee.py` 原设计为 5 个 agent 的规则委员会（DataAgent / StrategyAgent /
RiskAgent / MemoryAgent / AICriticAgent），在 `scripts/daily_research.py` 的 Step 2.5c
自动运行，输出 `CommitteeReview`（共识动作、风险等级、人工复核标记）。

审计发现三个问题：

1. **AICriticAgent 是死代码**：其 `_llm_critic` 通过 OpenAI 调用 LLM，但 ADR-0001 已
   将项目定位为 MCP Server，内部 LLM 全部废弃。健康检查将 LLM API 项标记为 skip，
   委员会的 LLM 路径从未在生产中被启用。
2. **MemoryAgent 是 stub**：注释写"Phase C 接入决策记忆"，但 B2.1 已让
   `DecisionMemory` 落地（回测自动写入、scheduler 回填）。stub 与现实脱节。
3. **与 MCP 架构方向相悖**：委员会作为内部 Python 调用存在，而项目的智能编排已交给
   通过 MCP 接入的外部 agent。继续保留一个"内部半空壳委员会"会误导架构方向。

真正有价值的部分是 DataAgent / StrategyAgent / RiskAgent 三者的**确定性风控规则**
（数据覆盖度、价格异常、信号冲突、做空检测、集中度、总敞口、回撤、极端波动）——
这些规则不应被丢弃。

## 可选方案

| 方案 | 优点 | 缺点 |
|------|------|------|
| **A. 接 LLM** 每个 agent 暴露为 MCP 工具并接 DeepSeek | 端到端智能 | 维护成本高；与"规则确定性风控"的初衷冲突；外部 agent 已能提供 LLM 推理 |
| **B. 删除** 移除 `agents/` 与所有调用 | 最干净 | 浪费 Data/Strategy/Risk 三个 agent 的真实风控逻辑 |
| **C. 降级为示例** 移到 `examples/` | 保留逻辑 | 仍不在主链路，逻辑无法被复用 |
| **D. 降级 + MCP 化（最终选择）** 保留 4 个规则 agent，删 LLM，MemoryAgent 接 DecisionMemory，整体封装为 MCP 工具 | 保留有价值的风控规则；对齐 MCP 架构；外部 agent 可开 subagent 各调一工具 | 单标的多次构建快照有冗余（可接受，按需触发） |

## 最终选择

**方案 D：降级 + MCP 化。**

具体做法：
- 移除 AICriticAgent 及其 OpenAI `_llm_critic` 路径；委员会从 5 agent 降为 4 agent。
- `MemoryAgent` 接入 `DecisionMemory`：查询近 90 天决策准确率，按准确率高/低给出
  支持或谨慎投票；无 storage 或样本不足时降级为"历史参考不足"。
- DataAgent / StrategyAgent / RiskAgent 的规则逻辑保持不变，方法改为公开
  （`data_agent` / `strategy_agent` / `risk_agent` / `memory_agent`）。
- 新增 `AgentCommittee.synthesize(votes)`：从一组已收集的投票计算共识，供"分别评审
  后汇总"的场景复用。
- 新建 `mcp_server/tools_committee.py`，暴露 5 个 MCP 工具：
  `review_data_quality` / `review_strategy_signals` / `review_risk_exposure` /
  `review_decision_history` / `compute_committee_consensus`。
- `scripts/daily_research.py` 移除 Step 2.5c 的委员会自动调用与对应的
  `committee_review` 决策记录；委员会评审改为外部 agent 按需通过 MCP 触发。

## 理由

- **不丢弃确定性风控**：Data/Strategy/Risk 三个 agent 的规则（权重上限、总敞口、
  回撤警戒、极端波动、信号冲突）是可回测、可审计的，比 LLM 即兴评审更可靠。
- **对齐 ADR-0001（LLM 边界）**：项目作为 MCP Server，LLM 推理由外部 agent 提供。
  委员会的"AI 评审"角色本就属于外部 agent，内部不应再保留 LLM 调用。
- **subagent 编排**：外部 agent 可为每个评审角色开一个 subagent，各调用专属 MCP
  工具（DataAgent→`review_data_quality` 等），再自行或通过
  `compute_committee_consensus` 合成共识。这把"何时评审、评审谁、如何综合"的决策权
  交还给智能层，规则层只提供确定性能力。
- **MemoryAgent 落地**：B2.1 已让 `DecisionMemory` 真正可用，stub 终于接上真实数据。

## 影响范围

| 模块 | 变更 |
|------|------|
| `agents/committee.py` | 移除 AICriticAgent / `_llm_critic` / `use_llm`；4 agent 方法公开；MemoryAgent 接 DecisionMemory；新增 `synthesize` |
| `agents/__init__.py` | 导出不变（`AgentCommittee`, `CommitteeReview` 仍存在） |
| `mcp_server/tools_committee.py` | 新增，5 个 MCP 工具 |
| `mcp_server/server.py` | 注册 `tools_committee` 模块 |
| `scripts/daily_research.py` | 移除委员会调用与 committee 决策记录 |
| `scripts/health_check.py` | LLM API skip 项保留（标注内部 LLM 已废弃，与 ADR-0001 一致） |

## 实施计划

1. 重构 `agents/committee.py`（移除 LLM、公开 agent、接 Memory、加 `synthesize`）。
2. 新建 `mcp_server/tools_committee.py` 并在 `server.py` 注册。
3. 清理 `scripts/daily_research.py` 的委员会调用与决策记录。
4. 单元测试覆盖重构后的委员会与 5 个 MCP 工具。

## 验证方法

- `agents.committee` 无 `_llm_critic` / `_ai_critic_agent`，4 个 agent 方法公开。
- `mcp_server.tools_committee` 注册 5 个工具，server.py 发现成功。
- `daily_research.py` 无 `committee_review` / `AgentCommittee` 残留引用，语法通过。
- 单元测试：4 agent 行为、MemoryAgent 准确率分支、`synthesize` 共识、5 个 MCP 工具
  返回结构、错误处理。

## 参考

- [ADR-0001: LLM 边界设计](0001-llm-boundary.md)
- `docs/plan/phase-4-improvement-plan.md` 第五节 ADR-001
- B2.1 回测→决策记忆自动写入（`knowledge/decision_memory.py`）
