# 贡献指南

感谢你对 QuantAgent 的兴趣！无论是修 bug、加功能、写策略还是改文档，都非常欢迎。

## 快速上手

```bash
# 1. Fork & clone
git clone https://github.com/<你的用户名>/QuantAgent.git
cd QuantAgent

# 2. 一键安装（自动创建 .venv、装依赖、建目录）
python scripts/install.py

# 3. 激活环境
source .venv/bin/activate

# 4. 跑测试，确保环境正常
pytest tests/ -q
```

## 找任务

- 看 [Good First Issues](docs/project/good-first-issues.md) — 适合新手的入门任务
- 在 GitHub Issues 中找 `good first issue` / `help wanted` 标签

## 开发流程

1. **建分支**: `git checkout -b feat/your-feature`（或 `fix/...`、`docs/...`）
2. **写代码**: 遵循现有代码风格
3. **写测试**: 新功能必须有测试，`pytest tests/ -q` 全绿
4. **提交**: 用 [Conventional Commits](https://www.conventionalcommits.org/) 格式
   ```
   feat: 添加 Tushare 数据源适配器
   fix: 修复 get_sector_index 在无成分股时的空指针
   docs: 补充 factor-research skill 示例
   ```
5. **发 PR**: 描述改动和测试结果

## 代码风格

| 工具 | 用途 |
|------|------|
| [Black](https://github.com/psf/black) | 代码格式化 |
| [Ruff](https://github.com/astral-sh/ruff) | Lint 检查 |
| pytest | 测试框架 |

```bash
black . && ruff check . --fix
```

## 添加新 MCP 工具

用 `@register_mcp_tool` 装饰器自动注册，无需手动改 server.py：

```python
from mcp_server.registry import register_mcp_tool

@register_mcp_tool(
    name="get_dividend_history",
    description="获取分红历史",
    read_only=True,
    skill="factor-research",
)
def get_dividend_history(ticker: str) -> str:
    ...
```

## 添加新策略

1. 在 `strategies/` 下新建目录
2. 实现 `StrategyBase` 接口（参考 `strategies/momentum/`）
3. 在 `strategies/registry.py` 中注册
4. 写测试

详见 [策略开发文档](docs/development/strategy_development.md)。

## 提问与交流

- **使用问题 / 策略讨论** → [GitHub Discussions](https://github.com/Aurora-73/QuantAgent/discussions)
- **Bug 报告** → [Issue](https://github.com/Aurora-73/QuantAgent/issues)（用 Bug 模板）
- **数据源请求** → Issue（用"数据源请求"模板）

## 目录结构速查

```
data/           数据层（provider, cleaner, storage, sectors）
research/       研究层（factors, backtest, walk_forward, risk_engine, ...）
strategies/     策略插件（momentum, event_driven, sentiment, regime_switch）
mcp_server/     MCP 工具（tools_data, tools_risk, tools_knowledge, tools_committee）
skills/         Skill 工作流（指导 Agent 如何编排 MCP 工具）
docs/           文档（adr, plan, project, getting-started, development, ...）
tests/          测试
```
