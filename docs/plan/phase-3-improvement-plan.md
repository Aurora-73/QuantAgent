# Phase 3 改进计划

> 生成日期：2026-07-08 | 最后更新：2026-07-08
> 基线版本：文档已系统性整理完成（WS1-WS10），MCP 工具闭环可用，Skills 层已初步构建
> 前置条件：Phase 2 已完成（baostock 数据源、scheduler、批量回测、MCP 写工具）

---

## 一、总览

### 1.1 目标

从"可验证"推进到"可扩展 + 高性能 + 安全"，**优先解决"能不能用对"的问题**：

1. **Skills 层构建** — Skill 定义业务流程，MCP 提供执行能力，打通两者关联
2. **补齐可扩展性基础设施** — MCP 工具自动发现（保留元数据）、DuckDB 查询优化
3. **性能优化** — 因子计算 I/O 优化（而非向量化）
4. **安全加固** — 写工具 dry-run
5. **功能完整性** — 财务数据接入、LLM 残留清理、因子参数化
6. **稳定性修复** — venv 路径硬编码修复

### 1.2 当前基线（文档整理后快照）

| 指标 | 说明 |
|------|------|
| MCP 工具 | 约 35 个（以 `python -m mcp_server.server --list-tools` 为准） |
| Skills | 5 个（sector-screening、daily-workflow、backtest-workflow、risk-assessment、factor-research） |
| 单元测试 | 全部通过（以 `pytest tests/` 输出为准） |
| 健康检查 | 通过（以 `python -m scripts.health_check` 输出为准） |
| 文档状态 | WS1-WS10 已完成，指针化/格式统一/归档横幅齐全 |
| 技术债 | 42 个 TODO/FIXME/HACK 跨 20 文件 |

### 1.3 依赖关系

```
Skills 层 ──→ MCP 自动发现 ──→ 安全加固
       │                              │
       └──→ I/O 优化 ←── 因子参数化 ──┘
              │
              └──→ 财务数据接入
```

---

## 二、任务详情

---

### 任务 P3.0：Skills 层构建（已完成）

**目的**：解决纯 MCP 工具缺乏业务流程指引的问题，让 Agent 知道"先做什么后做什么"。

**背景**：纯 MCP 只是给 Agent 提供"工具箱"，缺乏"菜谱"指引。35 个工具平铺展示，Agent 需要 15+ 轮来回试错才能找到正确调用顺序。

**已完成内容**：

#### Step 1：创建 Skills 目录

创建 `.claude/skills/` 目录，放置 5 个 skill 文件：

| Skill | 覆盖工具 | 用途 |
|-------|---------|------|
| [sector-screening.md](file:///home/edalab/Desktop/cme_code/quant-system/QuantAgent/.claude/skills/sector-screening.md) | get_sector_stocks, get_sector_index, get_history, search_tickers, get_market_overview | 行业/概念板块选股四步筛选法 |
| [daily-workflow.md](file:///home/edalab/Desktop/cme_code/quant-system/QuantAgent/.claude/skills/daily-workflow.md) | update_data, run_daily_research, get_daily_report, get_market_overview | 每日收盘后标准研究流程 |
| [backtest-workflow.md](file:///home/edalab/Desktop/cme_code/quant-system/QuantAgent/.claude/skills/backtest-workflow.md) | list_strategies, get_strategy_config, run_backtest, compare_backtest_runs | 策略回测标准流程 |
| [risk-assessment.md](file:///home/edalab/Desktop/cme_code/quant-system/QuantAgent/.claude/skills/risk-assessment.md) | run_stress_test, run_brinson_attribution, get_risk_report | 策略风险评估标准流程 |
| [factor-research.md](file:///home/edalab/Desktop/cme_code/quant-system/QuantAgent/.claude/skills/factor-research.md) | get_factors, run_factor_evaluation, run_decay_detection | 因子研究标准流程 |

每个 skill 文件包含：
- **frontmatter**：`name`、`description`、`requires_mcp`（依赖的 MCP 工具列表）
- **步骤说明**：清晰的执行顺序和参数示例
- **Fallback 指引**：失败时的备选方案
- **常见问题**：Q&A 形式的 troubleshooting

#### Step 2：MCP 工具添加 Skill 反链

在 [server.py](file:///home/edalab/Desktop/cme_code/quant-system/QuantAgent/mcp_server/server.py) 中，为 20+ 个工具的 description 添加 skill 引用：

```python
mcp.tool(
    name="get_sector_stocks",
    description="获取指定板块的成分股列表。用于行业选股，参见skill:sector-screening",
    annotations={"readOnlyHint": True},
)(tools_data.get_sector_stocks)
```

**验证标准**：
- [x] `.claude/skills/` 目录下有 5 个 skill 文件
- [x] MCP 工具 description 包含 skill 引用（如 `参见skill:sector-screening`）
- [x] `python -m mcp_server.server --list-tools` 工具数不变

---

### 任务 P3.1：MCP 工具自动发现

**目的**：解决 MCP 工具手动注册问题（`mcp_server/server.py` 约 36 处手动注册），新增工具无需改入口文件。

**背景**：当前每个工具需在 `server.py` 中手动添加 `mcp.tool(...)` 调用，扩展性差。

**关键修正**：原计划的 `register_mcp_tool()` 装饰器只存了函数引用，**丢失了 description 和 readOnlyHint 元数据**。正确做法是在 decorator 上支持完整元数据。

**实施步骤**：

#### Step 1：定义工具装饰器（保留元数据）

编辑 `mcp_server/tools_base.py`（新建）：

```python
import inspect
from dataclasses import dataclass
from typing import Callable, Optional

@dataclass
class MCPClientTool:
    name: str
    func: Callable
    description: Optional[str] = None
    read_only: bool = True

_TOOL_REGISTRY = {}

def register_mcp_tool(name: str = None, description: str = None, read_only: bool = True):
    def decorator(func: Callable):
        tool_name = name or func.__name__
        _TOOL_REGISTRY[tool_name] = MCPClientTool(
            name=tool_name,
            func=func,
            description=description or func.__doc__,
            read_only=read_only
        )
        return func
    return decorator

def get_registered_tools():
    return _TOOL_REGISTRY

def discover_tools_from_modules(prefix: str = "mcp_server.tools_"):
    import importlib
    import pkgutil
    import mcp_server
    for _, mod_name, is_pkg in pkgutil.walk_packages(mcp_server.__path__, mcp_server.__name__ + "."):
        if mod_name.startswith(prefix) and not is_pkg:
            importlib.import_module(mod_name)
```

#### Step 2：改造现有工具文件

在 `mcp_server/tools_data.py`、`tools_risk.py`、`tools_knowledge.py` 中，将 `mcp.tool(...)` 注册改为 `@register_mcp_tool()` 装饰器：

```python
@register_mcp_tool(name="get_sector_stocks", 
                   description="获取指定板块的成分股列表。用于行业选股，参见skill:sector-screening",
                   read_only=True)
def get_sector_stocks(sector_name: str, sector_type: str = "concept") -> dict:
    ...
```

#### Step 3：改造 server.py

编辑 `mcp_server/server.py`，移除所有手动注册，改为：

```python
from mcp_server.tools_base import discover_tools_from_modules, get_registered_tools

def setup_tools(mcp):
    discover_tools_from_modules()
    for name, tool_info in get_registered_tools().items():
        mcp.tool(
            name=tool_info.name,
            description=tool_info.description,
            annotations={"readOnlyHint": tool_info.read_only},
        )(tool_info.func)
```

**验证标准**：
- [ ] `python -m mcp_server.server --list-tools` 工具数不变
- [ ] 工具的 description 和 readOnlyHint 完整保留
- [ ] 新增工具只需在 `tools_*.py` 中定义，无需改 `server.py`
- [ ] 所有工具功能正常（调用任意 3 个工具验证）

**预计耗时**：1 小时

---

### 任务 P3.2：DuckDB 查询优化

**目的**：利用 DuckDB 列式存储特性优化查询性能，而非传统 B-tree 索引。

**背景修正**：DuckDB 是列式存储，min-max index 是自动的。`CREATE INDEX` 不是用来加速 `WHERE ticker = 'xxx'` 的。真正的优化方向是：合理分区、合理排序插入数据、利用 DuckDB 的自动统计信息。

**实施步骤**：

#### Step 1：分析现有数据布局

编辑 `scripts/analyze_db_layout.py`（新建）：

```python
import duckdb

def analyze_layout(db_path="data/quant.duckdb"):
    with duckdb.connect(db_path) as conn:
        print("=== 表统计 ===")
        tables = conn.execute("SHOW TABLES").fetchall()
        for (table,) in tables:
            row_count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"{table}: {row_count} 行")
        
        print("\n=== stock_daily 表布局 ===")
        result = conn.execute("""
            SELECT ticker, COUNT(*) as cnt 
            FROM stock_daily 
            GROUP BY ticker 
            ORDER BY cnt DESC 
            LIMIT 10
        """).fetchdf()
        print(result)

if __name__ == "__main__":
    analyze_layout()
```

#### Step 2：排序插入优化

编辑 `data/storage.py`，确保数据按 ticker + date 排序后插入：

```python
def save_stock_daily(self, ticker: str, df: pd.DataFrame):
    """保存股票日线数据（排序后插入）"""
    if not df.empty:
        df = df.sort_values("date")
        # 写入逻辑...
```

#### Step 3：表重建优化（可选）

如需优化已有数据的查询性能，可定期重建表并排序：

```python
def rebuild_table_sorted(self):
    """重建表并按 ticker + date 排序，提升查询性能"""
    self.conn.execute("""
        CREATE TABLE stock_daily_sorted AS 
        SELECT * FROM stock_daily 
        ORDER BY ticker, date
    """)
    self.conn.execute("""
        DROP TABLE IF EXISTS stock_daily
    """)
    self.conn.execute("""
        ALTER TABLE stock_daily_sorted RENAME TO stock_daily
    """)
```

**注意**：表重建会中断服务，建议在低峰期执行，或使用 `CREATE TABLE ... AS SELECT` 创建排序副本后再切换。

**验证标准**：
- [ ] 数据按 ticker + date 有序存储
- [ ] 单股票查询 `SELECT * FROM stock_daily WHERE ticker = 'xxx'` 耗时降低
- [ ] `EXPLAIN ANALYZE` 显示利用了有序性

**预计耗时**：1 小时

---

### 任务 P3.3：因子计算 I/O 优化

**目的**：解决因子计算耗时过长问题（30-60 min），通过 I/O 优化而非 CPU 向量化。

**背景修正**：实际瓶颈是 **I/O**（AKShare 每只股票 0.3s 限流，300 只 = 15 分钟纯等待），不是 CPU。用 ProcessPoolExecutor 不会解决 API 限流问题，反而可能触发更严格的限流。

**实施步骤**：

#### Step 1：本地缓存复用

编辑 `scripts/compute_factors.py`，优先使用本地缓存数据：

```python
def compute_factors_for_universe(universe):
    """计算因子（优先使用本地缓存）"""
    storage = DataStorage()
    for ticker in universe:
        df = storage.load_stock_daily(ticker)
        if df.empty:
            print(f"跳过 {ticker}：无本地数据")
            continue
        # 计算因子...
```

#### Step 2：批量数据源探索

编辑 `data/provider.py`，探索批量拉取接口：

```python
def get_batch_stock_daily(tickers, start_date, end_date):
    """批量拉取多只股票数据（如果 AKShare 支持）"""
    import akshare as ak
    results = {}
    for ticker in tickers:
        try:
            df = ak.stock_zh_a_hist(symbol=ticker, period="daily", 
                                   start_date=start_date, end_date=end_date)
            results[ticker] = df
        except Exception as e:
            print(f"拉取 {ticker} 失败: {e}")
            time.sleep(0.3)  # 限流等待
    return results
```

#### Step 3：增量更新策略

编辑 `scripts/compute_factors.py`，支持增量计算：

```python
def compute_factors_incremental(last_computed_date):
    """只计算新增日期的因子"""
    storage = DataStorage()
    new_dates = storage.get_new_dates(last_computed_date)
    for date in new_dates:
        # 只计算该日期的因子...
```

**验证标准**：
- [ ] 本地缓存数据优先使用，无需重复拉取
- [ ] 增量更新只计算新增日期数据
- [ ] 首次全量计算后，每日增量计算耗时 ≤5 min

**预计耗时**：2 小时

---

### 任务 P3.4：安全加固 — 写工具 Dry-Run

**目的**：为写操作添加安全屏障，支持 dry-run 预览。

**背景修正**：SQL 参数化审计用 AST 解析太脆弱（假阳性多）。DuckDB 的 Python 绑定已经走 prepared statement，风险较低。dry-run 是真正的亮点。

**实施步骤**：

#### Step 1：写工具添加 dry-run 参数

编辑 `mcp_server/tools_data.py`：

```python
def update_data(universe: str = "csi300", dry_run: bool = False) -> dict:
    """更新行情数据"""
    if dry_run:
        return {
            "status": "dry_run",
            "details": f"将从 AKShare/baostock 更新 {universe} 的行情数据",
            "estimated_time": "15-30 分钟"
        }
    # 实际执行...
```

编辑 `mcp_server/tools_risk.py`：

```python
def run_backtest(strategy: str, ticker: str, date_start: str, date_end: str, 
                 dry_run: bool = False) -> dict:
    """运行回测"""
    if dry_run:
        return {
            "status": "dry_run",
            "details": f"将对 {ticker} 运行 {strategy} 策略回测",
            "date_range": f"{date_start} 至 {date_end}"
        }
    # 实际执行...
```

#### Step 2：dry-run 参数传递链

确保 dry_run 参数传递到底层执行函数。

**验证标准**：
- [ ] `update_data(dry_run=True)` 不实际写入数据库
- [ ] `run_backtest(dry_run=True)` 不实际写入回测结果
- [ ] 所有写工具（update_data, run_daily_research, run_backtest）支持 `dry_run` 参数

**预计耗时**：30 分钟

---

### 任务 P3.5：功能完整性 — 财务数据接入与 LLM 残留清理

**目的**：补齐 Phase 2 遗留的财务数据流水线，清理 llm/ 移除后的残留引用。

**背景**：baostock 财务 API 已就绪（`data/provider.py`），但未接入 daily_research；`llm/` 已移除，可能有残留导入。

**实施步骤**：

#### Step 1：接入财务数据到 daily_research

编辑 `scripts/daily_research.py`，在数据更新步骤后增加：

```python
print("[Step 1.5/5] 更新财务数据...")
from data.provider import DataProvider
provider = DataProvider()
provider.update_financial_reports(universe)
```

#### Step 2：清理 LLM 残留导入

```bash
grep -rn "from llm\|import llm" --include="*.py" .
```

清理 quickstart.md 依赖表（移除 openai/langchain/langgraph）。

**验证标准**：
- [ ] `daily_research.py` 执行后 `research.financials` 表有数据增长
- [ ] `grep -rn "from llm\|import llm"` 无结果
- [ ] quickstart.md 依赖表无 LLM 行

**预计耗时**：30 分钟

---

### 任务 P3.6：因子参数化

**目的**：支持因子参数的灵活配置和 CLI 参数扫描。

**背景修正**：`settings.py` 里已经有 `momentum_lookback` 等因子参数（L116-126），但 CLI 参数扫描（`--params '{"momentum": {"lookback": 10}}'`）是新的、有价值的。

**实施步骤**：

#### Step 1：从配置读取因子参数

编辑 `research/factors.py`：

```python
from configs.settings import settings

@register_factor("momentum")
def momentum_factor(df, params=None):
    lookback = params.get("lookback", settings.momentum_lookback) if params else settings.momentum_lookback
    return df["close"].pct_change(lookback)
```

#### Step 2：CLI 支持参数扫描

编辑 `scripts/compute_factors.py`：

```python
def compute_factors_with_params(universe, factor_params):
    """使用指定参数计算因子"""
    for ticker in universe:
        df = get_stock_daily(ticker)
        for factor_name, params in factor_params.items():
            result = compute_factor(df, factor_name, params)
            store_factor(ticker, factor_name, result)
```

**验证标准**：
- [ ] 因子参数可从配置读取
- [ ] CLI 支持 `--params '{"momentum": {"lookback": 10}}'`
- [ ] 参数扫描结果可对比（不同 lookback 值）

**预计耗时**：1 小时

---

### 任务 P3.7：venv 路径硬编码修复

**目的**：修复 `.venv` 路径硬编码问题，确保环境稳定性。

**背景**：pip 脚本指向旧路径（如 `量化交易2/`），导致虚拟环境路径错误。

**实施步骤**：

#### Step 1：检查 venv 路径

```bash
ls -la .venv/bin/python
```

#### Step 2：修复硬编码路径

编辑 `.venv/bin/python` 和 `.venv/bin/pip` 中的路径引用。

**验证标准**：
- [ ] `.venv/bin/python` 路径正确
- [ ] `pip list` 正常工作

**预计耗时**：15 分钟

---

## 三、任务优先级总览

| 优先级 | 任务 | 模块 | 预计耗时 | 说明 |
|--------|------|------|---------|------|
| **P0** | P3.0 Skills 层构建 | `.claude/skills/` / `mcp_server/server.py` | 已完成 | 解决"能不能用对"的核心问题 |
| **P1** | P3.5 财务数据接入 + LLM 清理 | `scripts/daily_research.py` / `docs/` | 0.5h | 快赢任务，半小时完成 |
| **P1** | P3.4 写工具 dry-run | `mcp_server/tools_data.py` / `tools_risk.py` | 0.5h | 实用安全功能 |
| **P1** | P3.7 venv 路径修复 | `.venv/` | 0.25h | 环境稳定性必需 |
| **P2** | P3.1 MCP 工具自动发现 | `mcp_server/` | 1h | 实现方案需保留元数据 |
| **P2** | P3.6 因子参数化 CLI | `research/factors.py` / `scripts/` | 1h | settings 已有基础参数 |
| **P3** | P3.3 因子计算 I/O 优化 | `scripts/compute_factors.py` / `data/provider.py` | 2h | 重设计为 I/O 优化而非向量化 |
| **P3** | P3.2 DuckDB 查询优化 | `data/storage.py` / `scripts/` | 1h | 重设计为分区/排序优化而非索引 |

---

## 四、风险与依赖

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| MCP 自动发现破坏现有工具注册 | 工具列表丢失或元数据不全 | 备份 `server.py`，对比 `--list-tools` 输出，确保 description/readOnlyHint 完整 |
| 因子 I/O 优化触发 API 限流 | 数据拉取失败 | 使用本地缓存优先，控制请求频率 |
| dry-run 参数传递链断裂 | dry-run 无效 | 单元测试覆盖 dry-run 路径 |
| venv 路径修复影响现有环境 | 环境不可用 | 先备份，修复后验证 `pip list` |

---

## 五、验收标准

- [ ] P3.0 已完成（Skills 层构建）
- [ ] P3.5-P3.7 全部完成并通过验证标准
- [ ] P3.1-P3.2 完成（P2/P3 任务）
- [ ] `python -m scripts.health_check` 通过
- [ ] `pytest tests/` 全部通过
- [ ] MCP 工具数不变（以 `--list-tools` 为准）
- [ ] Skills 与 MCP 工具互相引用完整
