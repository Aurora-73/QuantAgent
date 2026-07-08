# 🤖 QuantAgent: The AI-Powered Quant Research Lab

> **核心原则**：传统量化引擎做交易主干，LLM 只做研究和信息处理，不直接决定下单。
> **Where LLMs are Researchers, not Traders.**
>
> A production-ready framework integrating Qlib, vn.py, and MCP + Skill Architecture for systematic trading research.

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-active-orange.svg)](https://github.com/Aurora-73/QuantAgent)
[![GitHub Stars](https://img.shields.io/github/stars/Aurora-73/QuantAgent.svg?style=social)](https://github.com/Aurora-73/QuantAgent)
[![GitHub Forks](https://img.shields.io/github/forks/Aurora-73/QuantAgent.svg?style=social)](https://github.com/Aurora-73/QuantAgent)
[![GitHub Issues](https://img.shields.io/github/issues/Aurora-73/QuantAgent.svg)](https://github.com/Aurora-73/QuantAgent/issues)

🌐 **English Version**: [README.en.md](README.en.md)

---

**核心理念** 🔭 : 传统量化引擎负责交易执行，LLM 负责信息处理与研究辅助。**绝不让 AI 直接决定下单**，消除幻觉风险。

---

## 🎯 为什么选择 QuantAgent?

量化开发的五大痛点，一个项目解决：

| 痛点 | 解决方案 |
|------|---------|
| 📊 数据源杂乱 | 多源自动切换（AKShare/baostock/pytdx），统一数据清洗 |
| 🔬 回测难 | Qlib + VectorBT 双引擎，Walk-forward 验证 |
| 🤖 实盘接口不统一 | vn.py 统一执行接口，支持 CTP/IB |
| 🧠 AI 幻觉风险 | LLM 只做研究不做交易，严格权限分离 |
| 📝 研究流程繁琐 | 多 Agent 团队协作，自动生成日报/周报 |

---

## ✨ 核心特性

| 🛡️ Robust Infrastructure | 🧠 AI Research Team | 📈 Strategy Ready |
|--------------------------|-------------------|------------------|
| **Multi-source Data**: Auto-switch AKShare/baostock/pytdx | **Daily Reports**: Auto-generate Markdown reports (Daily/Weekly) | **Modular Strategies**: Momentum, Event-driven, Sentiment |
| **DuckDB Storage**: Lightning-fast historical data storage | **Multi-Agent Debate**: Bull vs. Bear debate modules | **Risk-First**: Circuit breaker, position sizing, concentration limits |
| **Qlib Integration**: State-of-the-art factor analysis & backtest | **Knowledge Graph**: Archive failures, events, and lessons learned | **Walk-forward**: In-sample/Out-of-sample validation |
| **MCP Protocol**: Standardized interface for external agents | **Skill Workflows**: Business process guidance for agents | **vn.py Execution**: Unified live trading interface |

---

## 🏗️ 系统架构

### Mermaid 架构图

```mermaid
flowchart TB
    subgraph User Layer
        A[User Strategy]
    end
    
    subgraph Skill Layer
        B1[sector-screening]
        B2[daily-workflow]
        B3[backtest-workflow]
        B4[risk-assessment]
        B5[factor-research]
        B6[knowledge-exploration]
        B7[market-quick-check]
    end
    
    subgraph MCP Layer
        C1[Data Tools\n14 tools]
        C2[Risk Tools\n10 tools]
        C3[Knowledge Tools\n11 tools]
    end
    
    subgraph Core Engine
        D1[Qlib\nFactor / Backtest]
        D2[vn.py\nExecution]
        D3[DuckDB\nStorage]
    end
    
    subgraph Market Data
        E1[AKShare]
        E2[baostock]
        E3[pytdx]
        E4[OpenBB]
    end
    
    A --> Skill Layer
    Skill Layer --> C1 & C2 & C3
    C1 & C2 & C3 --> D1 & D2 & D3
    D1 & D2 & D3 --> E1 & E2 & E3 & E4
    
    style A fill:#f9f,stroke:#333,stroke-width:2px
    style B1 fill:#bbf,stroke:#333,stroke-width:1px
    style B2 fill:#bbf,stroke:#333,stroke-width:1px
    style B3 fill:#bbf,stroke:#333,stroke-width:1px
    style B4 fill:#bbf,stroke:#333,stroke-width:1px
    style B5 fill:#bbf,stroke:#333,stroke-width:1px
    style B6 fill:#bbf,stroke:#333,stroke-width:1px
    style B7 fill:#bbf,stroke:#333,stroke-width:1px
    style C1 fill:#bfb,stroke:#333,stroke-width:1px
    style C2 fill:#bfb,stroke:#333,stroke-width:1px
    style C3 fill:#bfb,stroke:#333,stroke-width:1px
    style D1 fill:#fbb,stroke:#333,stroke-width:1px
    style D2 fill:#fbb,stroke:#333,stroke-width:1px
    style D3 fill:#fbb,stroke:#333,stroke-width:1px
    style E1 fill:#bbb,stroke:#333,stroke-width:1px
    style E2 fill:#bbb,stroke:#333,stroke-width:1px
    style E3 fill:#bbb,stroke:#333,stroke-width:1px
    style E4 fill:#bbb,stroke:#333,stroke-width:1px
```

### 系统上下文图

![系统上下文图](docs/images/系统上下文图.png)

### Agent 团队协作架构

![Agent 团队协作架构](docs/images/Agent团队协作架构.png)

---

## 🤖 The "Right" Place for LLMs

In QuantAgent, we enforce a strict separation of powers.

| ✅ LLM as the Analyst | ❌ LLM as the Trader |
|----------------------|---------------------|
| Technical/Fundamental Analysis | Directly generating buy/sell signals |
| News Sentiment Summarization | Managing real-time order execution |
| Generating Investment Hypotheses | Calculating precise position sizes |
| Writing Daily Research Reports | Handling risk circuit breakers |

**LLM 是研究员，不是交易员。** This ensures high productivity without compromising on safety.

---

## 🚀 One Command to Rule Them All

一键安装，自动配置虚拟环境、依赖和目录结构。

### 环境要求

- Python 3.10+
- Git

### 一键安装（推荐）

```bash
# 克隆项目
git clone https://github.com/Aurora-73/QuantAgent.git
cd QuantAgent

# 跨平台一键安装
python scripts/install.py
```

脚本会自动完成：

1. ✅ 环境检查（Python/Git）
2. ✅ 创建虚拟环境（自动检测并修复平台不匹配问题）
3. ✅ 安装核心依赖（requirements.txt）
4. ✅ 创建配置文件（configs/.env）
5. ✅ 创建必要目录（data/, logs/, knowledge/）
6. ✅ 验证安装（运行 verify_project.py）

### 手动安装

```bash
# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate    # Linux/macOS
.venv\Scripts\activate       # Windows

# 安装依赖
pip install -r requirements.txt

# 配置 API Key
cp configs/.env.example configs/.env
# 编辑 configs/.env，填入必要的 API Key
```

### 可选依赖安装

| 模块     | 命令                                 | 说明            |
| ------ | ---------------------------------- | ------------- |
| Qlib   | `pip install qlib`                 | 研究层核心，因子分析/回测 |
| vnpy   | `pip install ta-lib vnpy vnpy-ctp` | 执行引擎，实盘交易     |
| OpenBB | `pip install openbb`               | 海外数据源         |

---

## 📁 目录结构

```
quant-system/
├── QuantAgent/                # 主代码仓库
│   ├── data/                  # 数据层
│   │   ├── provider.py        # 数据获取
│   │   ├── storage.py         # DuckDB存储
│   │   └── cleaner.py         # 数据清洗
│   ├── strategies/            # 策略层
│   │   ├── base/              # 策略基类
│   │   ├── momentum/          # 动量策略
│   │   ├── event_driven/      # 事件驱动策略
│   │   └── sentiment/         # 情绪策略
│   ├── research/              # 研究层
│   │   ├── backtest.py        # 回测引擎
│   │   └── factor_eval.py     # 因子评估
│   ├── risk/                  # 风控层
│   │   ├── risk_engine.py     # 风控引擎
│   │   └── portfolio.py       # 组合优化
│   ├── knowledge/             # 记忆层
│   │   └── knowledge_base.py  # 层级记忆系统
│   ├── integrations/          # 集成层
│   │   ├── qlib_engine.py     # Qlib集成
│   │   ├── vnpy_engine.py     # vnpy集成
│   │   └── openbb_data.py     # OpenBB集成
│   ├── mcp_server/            # MCP服务端
│   │   ├── server.py          # MCP Server入口
│   │   ├── tools_data.py      # 数据工具
│   │   └── tools_risk.py      # 风险工具
│   ├── .claude/skills/        # Skill工作流
│   ├── configs/               # 配置文件
│   └── monitoring/            # 监控层
├── examples/                  # 使用示例
├── tests/                     # 单元测试
├── scripts/                   # 脚本入口
├── docs/                      # 文档
├── requirements.txt           # 依赖列表
├── pyproject.toml             # 项目配置
└── LICENSE                    # 许可证
```

---

## 🎮 运行示例

```bash
# 快速开始：获取数据并运行回测
python examples/00_quick_start.py

# 获取股票数据
python examples/01_get_data.py --ticker 600519 --start 2025-01-01

# 计算因子
python examples/02_calc_factors.py

# 运行回测
python examples/03_backtest.py --strategy momentum

# 使用知识库
python examples/04_knowledge.py
```

### 每日研究流程

```bash
# 运行每日研究
python -m scripts daily-research

# 运行回测
python -m scripts backtest --strategy momentum --ticker 600519 --start 2025-01-01

# 健康检查
python -m scripts health_check

# 列出所有 MCP 工具
python -m mcp_server.server --list-tools
```

---

## 🧪 运行测试

```bash
# 运行所有测试
pytest

# 运行指定模块测试
pytest tests/test_risk_engine.py -v

# 运行策略相关测试
pytest tests/test_momentum_strategy.py -v

# 生成覆盖率报告
pytest --cov=quant_system --cov-report=html
```

---

## 🌐 开源项目集成

| 项目                | 用途          | 集成方式        | 集成模块                             |
| ----------------- | ----------- | ----------- | -------------------------------- |
| **Qlib**          | 研究层核心       | 直接 import   | `integrations/qlib_engine.py`    |
| **vnpy**          | 执行层核心       | 直接 import   | `integrations/vnpy_engine.py`    |
| **AKShare**       | A股数据        | pip install | `data/provider.py`               |
| **OpenBB**        | 海外数据源        | pip install | `integrations/openbb_data.py`    |
| **Riskfolio-Lib** | 组合优化        | pip install | `risk/portfolio.py`              |
| **VectorBT**      | 快速回测        | pip install | `research/backtest.py`           |

---

## 📊 核心模块

### 策略接口 (每个策略必须实现)

```python
class StrategyBase(ABC):
    prepare_features()          # 准备特征
    generate_signal()           # 生成信号
    position_sizing()           # 仓位计算
    risk_check()                # 风控检查
    expected_holding_period()   # 预期持仓周期
    kill_switch_condition()     # 熔断条件
```

### MCP 工具清单

35+ 个标准化工具，支持外部 Agent 调用：

- **Data Tools** (14): get_quote, get_history, get_factors, get_sector_stocks, update_data, ...
- **Risk & Strategy Tools** (10): run_backtest, run_stress_test, run_brinson_attribution, ...
- **Knowledge Tools** (11): search_events, wiki_search, get_daily_report, ...

### Skill 工作流

7 个业务流程指引，让 Agent 知道"先做什么后做什么"：

| Skill | 用途 |
|-------|------|
| sector-screening | 行业/概念板块选股 |
| daily-workflow | 每日研究流程 |
| backtest-workflow | 策略回测流程 |
| risk-assessment | 风险评估流程 |
| factor-research | 因子研究流程 |
| knowledge-exploration | 知识探索流程 |
| market-quick-check | 市场快速检查 |

---

## 🗺️ 开发路线

### Phase 1: 研究 + 报告 + 复盘 ✅

- [x] 数据接入 (AKShare + OpenBB)
- [x] Qlib 研究引擎集成
- [x] 因子计算与评估
- [x] VectorBT 回测
- [x] 知识库 (事件/假设/教训)
- [x] 日报/周报/月报生成
- [x] Riskfolio-Lib 组合优化
- [x] 风控引擎
- [x] 监控告警

### Phase 2: 信号引擎 + 回测 ⚡

- [x] 策略插件接口
- [x] 动量策略实现
- [x] 事件驱动策略
- [x] MCP 服务端
- [x] Skills 工作流层
- [ ] Walk-forward 验证

### Phase 3: 可扩展 + 高性能 + 安全 🛡️

- [ ] MCP 工具自动发现
- [ ] DuckDB 查询优化
- [ ] 因子计算 I/O 优化
- [ ] 写工具 dry-run
- [ ] 财务数据接入

### Phase 4: 仿真盘与实盘 📈

- [ ] vnpy 模拟交易
- [ ] 滑点与成交监控
- [ ] vnpy CTP/IB 连接
- [ ] 风控熔断机制

---

## 🤝 Contributing

欢迎提交 Issue 和 Pull Request！请遵循以下规范：

### 如何贡献

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/foo`)
3. 提交更改 (`git commit -am 'Add foo'`)
4. 推送到分支 (`git push origin feature/foo`)
5. 创建 Pull Request

### 🌟 Good First Issues

**AI 不负责猜涨跌，AI 负责提高整个研究链路的效率和质量！** 🚀

这些任务非常适合新手开发者入门：

- 📊 **Add a new data source adapter** - 添加新的数据源适配器（如 Tushare、JoinQuant），参考 `data/provider.py`
- 📈 **Implement a new strategy** - 实现新策略（如反转策略、均值回归策略），参考 `strategies/base/`
- 🧪 **Add unit tests** - 为数据层或策略层添加单元测试
- 📖 **Improve documentation** - 完善 MCP 工具文档或 Skill 工作流文档
- 🔌 **Add new MCP tool** - 添加新的 MCP 工具，参考 `mcp_server/tools_data.py`

### 开发规范

- 代码格式：Black + Ruff
- 测试框架：pytest
- 提交信息：使用 Conventional Commits 格式

### Issue 模板

我们提供两种 Issue 模板：

- **Data Source Request** - 数据源请求：如果你需要接入新的数据源
- **Strategy Sharing** - 策略分享：分享你的策略思路或代码

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙋‍♂️ 交流与反馈

- 🐛 **Bug 报告**: 请提交 Issue，提供复现步骤
- 💡 **功能建议**: 请提交 Feature Request
- 📖 **文档问题**: 请提交 Issue 或直接修改 docs/ 目录
- 💬 **Discussions**: 欢迎在 GitHub Discussions 中讨论策略和使用问题

---

**AI 不负责猜涨跌，AI 负责提高整个研究链路的效率和质量！** 🚀

⭐ 如果这个项目对你有帮助，请给个 Star！你的支持是我们持续改进的动力！
