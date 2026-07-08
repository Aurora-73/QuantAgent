# 变更记录

## 2026-07-09

### 文档一致性修复

- **Skills 目录路径修正**：`README.md` / `README.en.md` 目录结构中 `.claude/skills/` 更正为 `skills/`（实际已于 2026-07-08 晚迁移，changelog 补记）
- **README 路线图同步**：Phase 2 Walk-forward 验证、Phase 3 全部 5 项（MCP 自动发现 / DuckDB 优化 / I/O 优化 / dry-run / 财务数据）已勾选完成；新增 Phase 4「研究平台进化」反映已完成的 scheduler→systemd、周报生成、决策闭环、备份、参数扫描、realism、ADR-0003；原 Phase 4 仿真盘与实盘顺延为 Phase 5（未来）；添加 `docs/project/roadmap.md` 权威指针
- **todo/mcp-protocol-testing.md 工具数指针化**：硬编码 "32 个工具" 改为 `--list-tools` 指针（L5 背景 / L40 待办项）；L22 历史测试记录加注当前工具数已增长

### MCP 协议测试补全

- 新建 `scripts/mcp_protocol_test.py`：通过 JSON-RPC (stdin/stdout) 自动化测试全部 48 个 MCP 工具
- 全量测试结果：**45 通过 / 3 数据缺失（非故障）/ 0 失败**
- **发现并修复 `run_factor_evaluation` bug**：成功路径缺少 return 语句，隐式返回 None 导致 FastMCP 类型校验失败
- 写工具（update_data / run_daily_research / update_financials / update_data_incremental / run_backtest / generate_higher_order_report）全部通过 `dry_run=True` 验证

### GitHub 社区建设

- 创建 `.github/ISSUE_TEMPLATE/`：bug_report.md、feature_request.md、data_source_request.md、strategy_sharing.md + config.yml（含 Discussions 链接）
- 创建 `.github/good-first-issue-data-adapter.md`：Good First Issue 文案（添加新数据源适配器），可直接发布到 GitHub
- 创建 `CONTRIBUTING.md`：贡献指南（开发流程、代码风格、新 MCP 工具/策略添加方法、目录结构速查）

### 集成测试（跨工具交叉验证）

- 重写 `tests/test_mcp_integration.py`：旧测试全部过时（期望 dict 返回、错误函数签名、错误 registry API）
- 新增 17 个集成测试，覆盖 8 个场景：Market Quick Check / Sector Screening / Factor Research / Risk Assessment / Backtest Workflow / Knowledge Exploration / Committee Chain / Registry Metadata
- 全部 396 个测试通过（含 17 个新集成测试）

### B3 Profiling 评估 → Phase 4 正式关闭

- 对 `get_sector_index` / `get_market_overview` / `run_health_check` 跑 5 轮延迟采样
- `get_sector_index` P95 ≈ 5.6s < 10s 阈值 → **不触发 B3**
- `get_market_overview` P95 ≈ 73ms < 3s 阈值 → **不触发 B3**
- 慢工具瓶颈是 AKShare API 外部 I/O，非计算密集，属于数据层优化范畴
- **Phase 4 里程碑 M0-M5 全部完成，正式关闭**

### P3.6 因子计算 I/O 优化

- `data/sectors.py`：为 `get_industry_list()` / `get_concept_list()` 添加 24h 磁盘缓存（`data/cache/sectors/`），避免每次调用都命中 AKShare API（~5.5s → ~0ms 缓存命中）
- `get_board_stocks()`：添加内存 + 磁盘双层缓存
- `build_board_index()`：重构为优先从 DuckDB 批量查询（`_load_board_data_from_db`，单次 SQL `WHERE ticker IN (...)` 替代 N 次 API 调用），仅本地无数据时回退 API（`_load_board_data_from_api`）

### P3.7 DuckDB 查询优化

- `data/storage.py`：`save_stock_daily` / `append_stock_daily` / `save_index_daily` / `append_index_daily` 的 INSERT 语句添加 `ORDER BY date`，使 DuckDB zone-map 对日期范围查询生效
- `data/optimizations.py`：`save_factors_batch` 的 INSERT 添加 `ORDER BY ticker, date, factor_name`
- `data/storage.py`：新增 `DataStorage.analyze()` 方法，批量写入后刷新统计信息
- `data/optimizations.py`：`apply_optimizations()` 初始化时 ANALYZE 所有核心表
- `scripts/update_data.py` / `scripts/compute_factors.py`：批量写入后调用 `storage.analyze()`

### P4.9 文档站点

- 创建 `mkdocs.yml`：Material 主题，深色/浅色切换，中文搜索，完整 nav 结构（10 大类，45 页）
- 创建 `requirements-docs.txt`：mkdocs + mkdocs-material 依赖
- 创建 `.github/workflows/docs.yml`：GitHub Actions 自动部署到 GitHub Pages（push to main 触发）
- 修复 `docs/getting-started/quickstart.md` 相对链接（缺少 `../` 前缀）
- 修复 `docs/plan/archive/phase-a-b-plan-legacy.md` 相对链接（`../` → `../../`）
- `mkdocs build --strict` 零警告通过，生成 45 个 HTML 页面

## 2026-07-08

### Skills 层构建

- 创建 `.claude/skills/` 目录，包含 5 个 skill 文件：`sector-screening.md`（行业选股）、`daily-workflow.md`（每日研究）、`backtest-workflow.md`（回测工作流）、`risk-assessment.md`（风险评估）、`factor-research.md`（因子研究）
- 每个 skill 文件包含 frontmatter（name/description/requires_mcp）、步骤说明、fallback 指引、常见问题
- 更新 `mcp_server/server.py`：为 20+ 个 MCP 工具的 description 添加 skill 反链（如 `参见skill:sector-screening`）
- 更新 `docs/plan/phase-3-improvement-plan.md`：将 Skills 层作为 P0 任务，修正 DuckDB 索引认知、因子计算瓶颈认知，重排任务优先级

### Skills 层补全

- 新增 `knowledge-exploration.md`：覆盖搜索事件、决策、假设、文档等 10 个知识工具
- 新增 `market-quick-check.md`：覆盖市场概况、个股行情、指数数据、日历等快速查询工具
- 强化 `sector-screening.md` 步骤 3：添加具体的相关性计算方法和综合评分代码示例
- 更新 `mcp_server/server.py`：为剩余 15 个工具添加 skill 反链，实现 35 个工具全覆盖

### 新建 Phase 3 改进计划

- 创建 `docs/plan/phase-3-improvement-plan.md`：基于六维分析（功能完整性/代码质量/性能/体验/安全/扩展）制定可执行任务卡片，含 7 项任务（P3.1-P3.7）、优先级总览表、风险与依赖、验收标准
- 更新 `docs/README.md`：索引补入 `phase-3-improvement-plan.md`

## 2026-07-07

### 文档系统性整理（10 个工作流）

- **WS1 数据去数字化**：移除 `project-status.md`、`CLAUDE.md`、`roadmap.md`、`phase-2-implementation-plan.md`、`data-quality-improvement-plan.md`、`server_runbook.md`、`data_schema.md`、`mcp-capabilities.md`、`monitoring.md` 中硬编码的行数/股票数/测试数，统一改为指针（`python -m scripts.db_stats` / `pytest tests/` / `python -m mcp_server.server --list-tools`）
- **WS2 LLM 段落删除**：移除 `cli_reference.md` 的 `--no-llm` 参数、`configuration.md` 的 LLM 配置段、`data_schema.md` 的 LLM 结构化输出段、`acceptance-criteria.md` §2.7 LLM 层验收、`monitoring.md` 的 LLM API 检查项、`security.md` 的 OPENAI_API_KEY 内部配置；重构 `verification_loop.md` 为通用预测验证（信号源由 LLM 改为外部 Agent）
- **WS3 Windows 路径修复**：将 10 个文档中的 `file:///E:/Code/...`、`/e/Code/...`、`E:\Code\...` 路径统一替换为 Linux 路径；`scheduler.md` 的 Windows Task Scheduler 示例改为 crontab 示例
- **WS4 风险参数统一**：`server_runbook.md` §6.2 风控参数对齐 `configuration.md` canonical 值（5%/20%/10%，min_daily_volume=5000万，volatility_cap=3.0）
- **WS5 文档头格式统一**：`scheduler.md`、`monitoring.md`、`risk_management.md`、`disaster_recovery.md`、`security.md`、`mcp-capabilities.md` 添加规范化 header（生成日期/最后更新/适用场景）
- **WS6 索引补全**：`docs/README.md` 索引补充 `mcp-capabilities.md`、`adr/0000-template.md`、3 个 plan 文档、archive 文件列表；修正 wiki 位置为 `docs/wiki/`
- **WS7 过时引用修复**：`acceptance-criteria.md` 修复 `crispy-wondering-petal.md`/`bug.md` 改名引用；`cli_reference.md` 移除未注册的 `reversal` 策略；`data-source-analysis.md` 更新「news 是死胡同」过时结论
- **WS8 MCP 工具数量统一**：`mcp-capabilities.md` 移除「35 个」硬编码，改为 `--list-tools` 指针
- **WS9 changelog 重构**：新增本条目
- **WS10 关键信息高亮**：`phase-0-issues.md`、`phase-a-b-plan-legacy.md` 添加归档横幅

### 收尾补遗（WS1/WS2/WS10 遗漏清理）

- **WS2 遗漏清理**：`quickstart.md`（删 API Key 段 / `--no-llm`×2 / 重写"LLM 的定位"为 MCP 边界）、`troubleshooting.md`（删 §7 LLM API 调用失败）、`strategy_development.md`（删 `--no-llm` checklist 项）、`linux-server-test-plan.md`（L30/L132-136/L281 清理 LLM 残留）、`configuration.md`（删 OPENAI_API_KEY/OPENAI_BASE_URL 表行 + LLM 配置代码 + 环境变量示例）、`cli_reference.md`（删 OPENAI_API_KEY 表行 + LLM 调用注意事项）
- **WS10 补全**：`issue-001-duckdb-index-error.md` 补归档横幅（与另 2 个归档文件一致）
- **WS1 遗漏**：`quickstart.md` 硬编码测试数 `139` 改为 `pytest tests/` 指针

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

### 文档大整理（2026-07-06 第二批次）
- 删除根目录过时文档：`介绍.md`（复制的 MCP 文档）、`提示词.md`（空文件）
- 归档 `runbook/phase-0-issues.md` → `plan/archive/`（Phase 0 已完成）
- 重写 `CLAUDE.md`：MCP Server 定位、最新数据库统计、完整命令参考
- 更新 `project-status.md`：数据库行数（452K→11.3M factors）、数据统计同步
- 创建 `docs/README.md`：文档索引 + 管理规范 + 快速导航
- 创建 `plan/phase-2-implementation-plan.md`：Phase 2 详细实施计划（5 个任务，含步骤/验收/风险）
- 重写 `project/roadmap.md`：反映 P1 完成后现状，指向 Phase 2 计划
- 修复 `health_check.py`：依赖检查异常崩溃（ImportError→Exception）
- 修复 `run_p1.sh`：过期参数 --all 和不存在的模块名

### 文档更新 + MCP 优化
- MCP 工具自动数据拉取：get_quote/get_history 缺失股票自动从 baostock获取
- 文档全面更新：CLAUDE.md（MCP 工具表+最新统计）、architecture.md（MCP 架构节）、cli_reference.md（新增7个命令文档）、project-status.md（最新DB统计）、docs/README.md（MCP引用）、quickstart.md（MCP引用）

### Phase 2 实施
- P2.1: 安装 baostock 0.9.2，数据源测试全部 PASS
- P2.2: scheduler --dry-run/--run-now 验证通过，创建 run/stop_scheduler.sh 管理脚本
- P2.3: 创建 batch_backtest.py 批量回测脚本，4 策略 10 只股票验证通过（40/40），结果写入 backtest_runs 表（32→73 条）
- P2.4: MCP 新增 2 个写工具（update_data / run_daily_research），安装 fastmcp，工具总数 30→32

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
quant-system/
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
└── QuantAgent/         本项目 (自建)
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
