# 快速上手

> 从零开始使用 QuantAgent 量化交易系统。

---

## 一、环境要求

| 项目 | 版本要求 | 说明 |
|------|---------|------|
| Python | >= 3.10 | 推荐 3.11 |
| 操作系统 | Windows / Linux / macOS | Windows 用户注意编码问题 |
| 内存 | >= 8GB | 回测时建议 16GB+ |
| 磁盘 | >= 10GB | 数据库和缓存文件 |

---

## 二、安装步骤

### 方法 1：一键安装（推荐）

```bash
# Windows
python scripts/install_windows.ps1

# Linux / macOS
bash scripts/install.sh

# 跨平台通用
python scripts/install.py
```

### 方法 2：手动安装

#### 1. 克隆项目

```bash
git clone https://github.com/Aurora-73/QuantAgent.git
cd QuantAgent
```

#### 2. 创建虚拟环境

**Windows（PowerShell）**：
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**Linux / macOS**：
```bash
python -m venv .venv
source .venv/bin/activate
```

#### 3. 安装依赖

**推荐安装**：
```bash
pip install -r requirements.txt
```

依赖包含以下分组：

| 分组 | 包 |
|------|-----|
| Core | pandas, numpy, duckdb, pydantic, loguru, requests |
| Data | akshare, baostock |
| Research | vectorbt, riskfolio-lib |
| Monitoring | rich, schedule |

#### 4. 配置环境变量（可选）

```bash
cp configs/.env.example configs/.env
```

编辑 `configs/.env`，按需填入通知密钥（如 `SENDCHAN_SENDKEY_*`）。完整变量清单见 [`reference/configuration.md`](../reference/configuration.md)。

#### 5. 验证安装

```bash
pytest tests/ -v
```

预期结果：单元测试全部通过（以 `pytest tests/` 输出为准）。

---

## 三、快速使用

### 步骤 1：获取数据

```bash
# 更新沪深300股票池数据
python -m scripts update-data --universe csi300 --start 2024-01-01

# 或更新单只股票数据
python -m scripts update-data --ticker 600519 --start 2024-01-01
```

**输出示例**：
```
[OK] 已更新 289 只股票的日线数据
[OK] 已更新 10 个指数的日线数据
[OK] 已更新基本面数据
```

### 步骤 2：计算因子

```python
from research.factors import FactorEngine
from data.provider import DataProvider

df = DataProvider.get_stock_daily("600519", "2024-01-01")
engine = FactorEngine()
df_with_factors = engine.compute_all(df)
print(f"已计算 {len(engine.list_factors())} 个因子")
```

### 步骤 3：运行回测

```bash
python -m scripts backtest --strategy momentum --ticker 600519 --start 2024-01-01
```

**输出示例**：
```json
{
  "strategy": "momentum",
  "total_return": 0.235,
  "sharpe_ratio": 1.28,
  "max_drawdown": -0.125,
  "win_rate": 0.58,
  "trades": 45
}
```

### 步骤 4：运行每日研究

```bash
python -m scripts daily-research
```

---

## 四、核心概念

### 系统架构

```
数据层 → 研究层 → 策略层 → 风控层 → 执行层
    ↑                            │
    └───────── 层级记忆系统 ─────┘
```

### MCP 定位

> 本系统是 MCP Server：行情、因子、回测、风控、知识库能力暴露成工具，供 Claude/Codex 等外部 Agent 调用。系统内部不内置 LLM 调用，LLM 能力由调用方提供。

详见 [`adr/0001-llm-boundary.md`](../adr/0001-llm-boundary.md)。

---

## 五、每日工作流

```bash
# 每天收盘后
python -m scripts daily-research

# 周末做因子研究
python -m scripts factor-eval --all --start 2024-01-01

# 每月做策略回测
python -m scripts backtest --strategy momentum --universe csi300

# 每月做风控归因
python -m scripts brinson --universe csi300 --benchmark 000300
```

---

## 六、下一步

- [命令行参考](../reference/cli_reference.md) — 完整的命令行参数说明
- [策略开发指南](../development/strategy_development.md) — 如何编写自定义策略
- [因子开发指南](../development/factor_development.md) — 如何添加新因子
- [回测最佳实践](../research/backtesting.md) — 回测技巧和注意事项
- [服务器运维](../operations/server_runbook.md) — P1 闭环验证
- [MCP 工具能力](../mcp-capabilities.md) — MCP 工具清单与限制说明
- [故障排除](../runbook/troubleshooting.md) — 常见问题解决
