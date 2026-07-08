# 文档中心

> QuantAgent 量化交易研究系统 — 文档目录与规范
> 最后更新: 2026-07-08

---

## 文档体系

```
docs/
├── README.md                    ← 本文档（文档索引）
├── mcp-capabilities.md          MCP 工具能力与限制说明
├── adr/                         ← 架构决策记录
│   ├── 0000-template.md         ADR 模板
│   ├── 0001-llm-boundary.md     LLM 边界决策：传统量化 vs LLM 职责划分
│   └── 0002-duckdb-storage.md   DuckDB 存储架构设计
├── getting-started/             ← 快速上手
│   └── quickstart.md            从零开始安装和运行
├── development/                 ← 开发指南
│   ├── architecture.md          系统架构设计
│   ├── factor_development.md    因子引擎开发指南
│   └── strategy_development.md  策略插件开发指南
├── operations/                  ← 运维手册
│   ├── server_runbook.md        服务器运行手册（P1 闭环验证）
│   ├── scheduler.md             定时调度器说明
│   ├── monitoring.md            监控告警配置
│   ├── risk_management.md       风控系统文档
│   └── disaster_recovery.md     灾难恢复方案
├── project/                     ← 项目管理
│   ├── project-status.md        项目现状报告（含数据统计）
│   ├── roadmap.md               路线图与优先级
│   ├── changelog.md             变更记录
│   └── security.md              安全说明
├── reference/                   ← 参考手册
│   ├── cli_reference.md         命令行接口参考
│   ├── configuration.md         配置参数完整参考
│   └── reference-projects.md    参考项目分析（_reference/ 下 19 个开源项目）
├── research/                    ← 研究层文档
│   ├── backtesting.md           回测最佳实践
│   ├── data_schema.md           数据契约（核心数据类型）
│   └── verification_loop.md     验证闭环设计
├── plan/                        ← 实施计划
│   ├── acceptance-criteria.md         验收标准
│   ├── issues.md                      待解决问题跟踪
│   ├── data-source-analysis.md        数据源分析报告
│   ├── phase-2-implementation-plan.md Phase 2 实施计划
│   ├── phase-3-improvement-plan.md    Phase 3 改进计划（可扩展+高性能+安全）
│   ├── data-quality-improvement-plan.md 数据质量改进计划
│   ├── linux-server-test-plan.md      Linux 服务器测试计划
│   └── archive/                       ← 已归档的历史计划
│       ├── issue-001-duckdb-index-error.md  DuckDB 索引错误（已修复）
│       ├── phase-0-issues.md                Phase 0 问题记录
│       └── phase-a-b-plan-legacy.md         Phase A/B 历史计划
├── runbook/                     ← 故障排除
│   └── troubleshooting.md       常见问题与排查
└── wiki/                        ← 交易方法论库
    ├── entities/                实体策略（突破/趋势）
    ├── scenarios/               场景应对（熊市/牛市）
    ├── sources/                 策略来源（海龟等）
    └── synthesis/               综合比较
```

---

## 文档规范

### 1. 文件命名

- 全部使用英文 kebab-case（小写字母 + 连字符）
- 例如：`server_runbook.md`、`factor_development.md`
- 禁用中文文件名、空格、驼峰

### 2. 文档头信息

每个文档应以 `# 标题` 开头，第二行可选 `> 元数据行`：

```markdown
# 文档标题

> 生成日期：YYYY-MM-DD | 最后更新：YYYY-MM-DD | 适用场景：[说明]
```

### 3. 内容结构

- 使用 `---` 分隔章节
- 使用 `##` / `###` 级联标题
- 表格式数据用 Markdown 表格
- 代码示例用代码块标注语言
- 文件路径用 `code` 或 `[链接](filepath)` 引用

### 4. 交叉引用

引用其他文档使用相对路径链接：

```markdown
详见 [`project-status.md`](../project/project-status.md)
```

### 5. 版本可追溯

- 每次文档修改更新 `changelog.md`
- 文档内元数据行更新 `最后更新` 日期
- ADR 文档通过序号追踪（0001、0002…）

### 6. 文档维护

- 过时文档移入 `plan/archive/` 而非直接删除
- 内容重复的文档合并后，源文件标注重定向
- 每次 Phase 完成更新 `project-status.md` 中的数据库统计

---

## 快速导航

| 你要做什么 | 先看哪个文档 |
|-----------|------------|
| 首次部署运行 | `getting-started/quickstart.md` |
| 在服务器上跑 P1 | `operations/server_runbook.md` |
| 了解系统架构 | `development/architecture.md` |
| 查看当前状态 | `project/project-status.md` |
| 开发新策略 | `development/strategy_development.md` |
| 开发新因子 | `development/factor_development.md` |
| 查看 MCP 工具清单 | 运行 `python -m mcp_server.server --list-tools`（能力与限制见 `mcp-capabilities.md`） |
| 查看所有 CLI 命令 | `reference/cli_reference.md` |
| 修改配置参数 | `reference/configuration.md` |
| 排查问题 | `runbook/troubleshooting.md` |
| 了解参考项目 | `reference/reference-projects.md` |
