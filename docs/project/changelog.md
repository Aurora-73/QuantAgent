# 变更记录

## 2026-07-06

### Bug 修复
- wiki_search — WikiEntry JSON 序列化问题修复
- get_prediction_accuracy — NaN 转换崩溃修复
- run_stress_test — 默认参数错误修复（000300→600519）
- run_brinson_attribution — 参数验证不足修复
- get_market_overview — Series 真值判断修复
- run_backtest — win_rate 始终为 0 修复
- run_backtest — Sharpe 为 NaN 修复
- run_backtest — 参数验证缺失修复
- run_factor_evaluation — 数据不足时提示不友好修复

### 文档整理
- 清理 plan/ 目录，归档已完成项
- 更新项目状态报告

## 2026-07-03

### 文档整理与重构

#### 删除的文档
- `docs/archive/` 目录（8个过期架构设计草稿）
- `docs/项目分析报告.md`（过时，被项目现状报告替代）
- `docs/项目分析总结.md`（内容已合并到参考项目分析报告）
- `docs/phase-b-issues.md`（内容已合并到 plan/issues.md）
- `crispy-wondering-petal.md`（根目录重复文件）

#### 合并的文档
- `项目分析总结.md` + `参考项目分析报告.md` → `reference-projects.md`（新增学习路径和趋势观察章节）
- `phase-b-issues.md` → `plan/issues.md`（新增环境问题章节）

#### 重命名的文件（统一为英文 kebab-case）

| 旧文件名 | 新文件名 |
|---------|---------|
| `项目现状报告.md` | `project-status.md` |
| `参考项目分析报告.md` | `reference-projects.md` |
| `未来计划.md` | `roadmap.md` |
| `架构设计.md` | `architecture.md` |
| `变更记录.md` | `changelog.md` |
| `plan/crispy-wondering-petal.md` | `plan/phase-a-b-plan.md` |
| `plan/验收计划.md` | `plan/acceptance-criteria.md` |
| `plan/bug.md` | `plan/issues.md` |
| `runbook/common-issues.md` | `runbook/troubleshooting.md` |
| `runbook/phase0-issues.md` | `runbook/phase-0-issues.md` |

#### 文档分类体系
```
docs/
├── architecture.md          # 架构设计
├── project-status.md        # 项目现状报告
├── reference-projects.md    # 参考项目分析
├── roadmap.md               # 未来路线图
├── changelog.md             # 变更记录
├── plan/                    # 实施计划
│   ├── phase-a-b-plan.md    # Phase A/B 详细计划
│   ├── acceptance-criteria.md # 验收标准
│   └── issues.md            # 问题跟踪
└── runbook/                 # 运维手册
    ├── troubleshooting.md   # 故障排除
    └── phase-0-issues.md    # Phase 0 问题记录
```

## 2026-07-02

### Phase B 实施完成

- MarketRegimeDetector — 5 种市场状态识别
- WikiRetriever + FusionEngine — 多源融合管线
- WeightVector + SignalValidator — 权重合约架构
- 策略注册表 — @register_strategy 装饰器
- AgentCommittee — 多 Agent 规则委员会
- HealthCheck + Scheduler — 健康检查与定时调度
- 122 个单元测试全部通过

## 2026-06-03

### 安装的 Python 包 (pip install --user)

以下包通过 `pip install --user` 安装到用户目录：

- pandas, numpy, pyarrow, duckdb
- akshare (A 股数据)
- openai (LLM API)
- pydantic, rich, python-dotenv, pyyaml

以下包通过 venv 安装到 `quant-system/.venv/`：

- vectorbt (向量化回测)
- riskfolio-lib (组合优化)
- 及其依赖 (scipy, scikit-learn, matplotlib, cvxpy 等)

### 创建的虚拟环境

- `quant-system/.venv/` — Python 3.10 虚拟环境
- 激活方式: `source quant-system/.venv/bin/activate`

### Git 配置修改

之前修改了全局 git SSL 后端配置：
```
git config --global http.sslbackend gnutls
```
原因：系统不支持 openssl 后端，改为 gnutls 后可正常 clone。

### 创建的目录结构

#### quant-system/ (新项目)
```
quant-system/
├── configs/           配置文件
├── data/              数据层 (provider, storage, cleaner, aligner)
├── knowledge/         知识库 (daily, weekly, monthly, events, hypotheses, failures)
├── llm/               LLM 模块 (summarizer, extractor, report_agent)
├── monitoring/        监控 (metrics, alerts)
├── research/          研究层 (factors, backtest, evaluator)
├── risk/              风控 (risk_engine, portfolio)
├── scripts/           CLI 脚本 (daily_research, backtest, update_data, show_knowledge)
├── strategies/        策略层 (base, momentum, event_driven, sentiment, regime_switch)
├── tests/             测试
├── execution/         执行层 (broker, simulator)
├── .venv/             虚拟环境
├── README.md
└── requirements.txt
```

#### 克隆的开源项目
```
量化交易/
├── vnpy/              国内量化交易框架
├── TradingAgents/     多Agent LLM交易框架
├── qlib/              微软AI量化平台
├── FinRL/             强化学习量化
├── QuantAgent/        LLM量化智能体
├── Lean/              QuantConnect交易引擎
├── nautilus_trader/   高性能交易系统
├── OpenBB/            开源Bloomberg Terminal
├── vectorbt/          向量化回测
├── Riskfolio-Lib/     组合优化
├── FinMem-LLM-StockTrading/  LLM记忆交易
└── quant-system/      本项目 (自建)
```

### v2 更新：集成开源项目

新增 `integrations/` 目录，直接集成已有开源项目：

| 集成模块 | 目标项目 | 状态 |
|---------|---------|------|
| `integrations/qlib_engine.py` | qlib | ⚠️ 需要编译 C 扩展 |
| `integrations/vnpy_engine.py` | vnpy | ⚠️ 需要 TA-Lib C 库 |
| `integrations/trading_agents.py` | TradingAgents | ✅ 可用 |
| `integrations/openbb_data.py` | OpenBB | ⚠️ 依赖较多 |

额外安装的包 (venv)：
- setuptools-scm, redis, ruamel.yaml (qlib 依赖)
- langgraph, langchain, langchain-openai, langgraph-checkpoint-sqlite (TradingAgents 依赖)
- yfinance, stockstats (TradingAgents 数据源依赖)
- pydantic-settings

### 修改的文件

- `quant-system/.venv/` — 虚拟环境目录 (新建)
- `quant-system/integrations/` — 集成层 (新建)
- `quant-system/README.md` — 更新为 v2 架构
- `quant-system/requirements.txt` — 更新依赖
- 无其他系统文件被修改
