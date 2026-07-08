# 数据质量与 MCP 能力改进计划

> 生成日期：2026-07-06
> 来源：飞书 Agent 实际使用中发现的能力缺口（半导体选股场景）
> 状态：计划阶段，待评审

---

## 一、概述

### 1.1 问题来源

Agent 在飞书上执行"半导体选股"任务时，暴露了 3 个 MCP 工具限制 + 1 个数据入库 bug：

| # | 问题 | 影响 | 发现场景 |
|---|------|------|----------|
| 1 | `pct_change` 全部为 NULL | Agent 无法直接获取涨跌幅，需自行计算 | 条件②：同向性分析 |
| 2 | 无板块/行业指数 | Agent 需手动从个股构建等权板块指数 | 条件②：无半导体指数 |
| 3 | 无分钟线数据 | 无法准确判断"开盘期间涨幅" | 条件③：只能用日线近似 |
| 4 | `search_tickers` 不支持中文 | 无法按行业中文名搜索股票 | 条件①：找半导体股 |

### 1.2 当前基线

| 指标 | 数值 |
|------|------|
| stock_daily 行数 | 426,364 |
| pct_change 为 NULL | 426,363 (100%) |
| 指数数量 | 2 个（沪深300 + 中证500） |
| 行业分类数据 | 无 |
| 分钟线数据 | 无 |
| `search_tickers` 中文搜索 | 不支持 |

---

## 二、问题详情与修复方案

---

### 任务 1：修复 `pct_change` 数据入库 Bug

**严重性：高** — Agent 最常用的基础数据字段完全不可用。

**根因**：Provider 与 Storage 列名不一致

```
provider.py L687-688：    df["pct_chg"] = df["close"].pct_change() * 100
                                ↑ 列名是 pct_chg
storage.py L457：          for col in ["open", ..., "pct_change", "turnover"]:
                                ↑ 检查的是 pct_change（不存在 → 保持 None）
```

Provider 返回的 DataFrame 包含 `pct_chg` 列，但 storage 检查的是 `pct_change` 列名，不匹配导致全部写入 NULL。

**修复步骤**：

1. 修改 `data/provider.py` L688：`"pct_chg"` → `"pct_change"`
2. 同时检查 `data/provider.py` 中其他引用 `pct_chg` 的位置（L372, L650）
3. 运行 `python -m scripts.update_data --universe csi300` 刷新数据
4. 验证修复：`SELECT COUNT(*) FROM stock_daily WHERE pct_change IS NOT NULL`

**涉及文件**：

| 文件 | 行号 | 当前内容 | 修改为 |
|------|------|----------|--------|
| `data/provider.py` | 688 | `df["pct_chg"] = ...` | `df["pct_change"] = ...` |
| `data/provider.py` | 650 | `"turn", "pct_chg"` | `"turn", "pct_change"` |
| `data/provider.py` | 134 | 注释 `pct_chg` | 同步更新注释 |
| `data/provider.py` | 372 | `_safe_float(latest.get("当日涨跌幅"))` | 确认这路正确 |

**验收标准**：
- 重新拉取数据后，`pct_change` 非空率 > 95%
- `get_history` MCP 工具返回的数据包含有效涨跌幅

**预估工作量**：1 小时

---

### 任务 2：增加行业板块分类数据

**严重性：中** — Agent 无法按行业筛选股票，需手动拼凑名单。

**现状**：
- 数据库现有 CSI300 成分股（数量以 db_stats 为准），但无行业分类信息
- `search_tickers` 不支持按行业搜索
- Agent 只能通过搜索已知龙头股来"拼凑"板块名单

**方案 A（推荐）**：引入申万行业分类

利用 AKShare 的 `ak.stock_board_industry_name_em()` 获取申万行业分类：

```python
import akshare as ak
df = ak.stock_board_industry_name_em()
# 返回：{板块名称, 成分股数量, ...}
# 然后通过 stock_board_industry_cons_em("半导体") 获取成分股
```

**实施步骤**：

1. 新增 `data/industry.py` 模块：
   - `get_industry_list()` — 获取申万行业列表
   - `get_industry_stocks(industry_name)` — 获取某行业的成分股
   - `get_industry_index(industry_name)` — 构建行业等权指数
2. 新增数据库表 `industry_stocks`（股票→行业映射）
3. 新增数据库表 `industry_daily`（行业指数日线）
4. MCP 新增工具：
   - `get_industry_list()` — 列出所有行业
   - `get_industry_stocks(industry_name)` — 获取行业成分股
   - `get_industry_index(industry_name)` — 获取行业指数

**涉及文件**：

| 文件 | 变更 |
|------|------|
| `data/industry.py` | 新建 — 行业分类数据获取 |
| `data/storage.py` | 新增 `save_industry_mapping()` + `save_industry_index()` |
| `mcp_server/tools_data.py` | 新增 3 个行业相关工具 |
| `data/provider.py` | 可选 — 添加行业数据获取方法 |

**验收标准**：
- 可获取申万全量行业列表
- 可查询"半导体"行业的成分股（预期 80-120 只）
- `get_industry_stocks("半导体")` MCP 工具返回股票列表
- `get_industry_index("半导体")` MCP 工具返回自建等权指数

**预估工作量**：3-4 小时

---

### 任务 3：增加概念板块数据

**严重性：中** — 半导体属于"概念板块"，不在申万行业分类中。

**补充说明**：
- A 股板块分类有两种体系：
  - **申万行业**（一级/二级）：如电子、计算机（偏正式分类）
  - **概念板块**（同花顺/东方财富）：如半导体、AI芯片（偏市场题材）
- "半导体"属于**概念板块**，需要用 `ak.stock_board_concept_name_em()` + `stock_board_concept_cons_em()`

**实施步骤**：

1. 扩展 `data/industry.py` 为 `data/sectors.py`，同时支持：
   - 申万行业（industry）
   - 概念板块（concept）
   - 地域板块（area）
2. 数据库新增 `concept_stocks` 表
3. MCP 工具同步扩展

**验收标准**：
- `get_sector_stocks("半导体", sector_type="concept")` 返回正确成分股
- 数据与东方财富/同花顺官网一致

**预估工作量**：2 小时（可合并到任务 2）

---

### 任务 4：分钟线数据能力评估

**严重性：低-中** — 有需求但数据量大、收益需评估。

**需求场景**：
- "开盘期间涨幅慢于板块" — 需要开盘后 30-60 分钟的数据
- Tick 级别的动量分析
- 盘中异动检测

**数据量估算**（5 分钟线，基于成分股数量级估算）：
```
成分股 × 48 根 K 线/天 × 250 交易日 ≈ 360 万行/年
```
约等于当前 stock_daily 行数的数倍，可接受。

**数据来源**：
- AKShare: `ak.stock_zh_a_hist_min_em()` 支持 1/5/15/30/60 分钟线
- pytdx: 通达信协议也有分钟线数据

**实施步骤**：

1. 评估是否真需要分钟线（与用户确认使用场景优先级）
2. 若需要：
   - 新增 `data/minute_data.py`
   - 新增数据库表 `stock_minute`（ticker, date, time, open, high, low, close, volume）
   - MCP 新增 `get_minute_data(ticker, date)` 工具
   - 注意：增量更新策略（只拉最近 5 天）

**预估工作量**：4-6 小时（含评估）

---

### 任务 5：`search_tickers` 支持中文搜索

**严重性：低** — 有绕过方案，但体验不好。

**现状**：
- `search_tickers("半导体")` 返回空
- Agent 只能通过已知龙头股的代码来查询

**修复方案**：
在 `tools_data.py` 的 `search_tickers` 中增加模糊匹配：

```python
# 当前：只查 ticker 列
WHERE ticker LIKE '%query%'

# 改进：同时查 ticker 和 name
WHERE ticker LIKE '%query%' OR name LIKE '%query%'
```

这需要：
1. 确保 `stock_daily` 或单独表存有股票名称
2. 或调用 AKShare spot 数据实时查询

**涉及文件**：`mcp_server/tools_data.py`

**预估工作量**：1 小时

---

### 任务 6：MCP 工具能力文档化

**严重性：低** — 提升 Agent 自主使用效率。

**问题**：
- Agent 在运行中才发现 MCP 工具的局限性（如无分钟线、pct_change 缺失）
- 如果 Agent 能一开始就了解工具的能力边界，可以更高效地规划策略

**实施步骤**：

1. 在 `mcp_server/readme` 或新增 `docs/mcp-capabilities.md` 中明确记录：
   - 数据粒度：仅日线（无分钟线）
   - 指数范围：仅 CSI300/500（无行业指数）
   - 字段有效性：pct_change 当前为 NULL
   - 搜索能力：仅支持代码搜索，不支持中文名搜索
   - 自动补充：数据不存在时会自动从 AKShare 拉取
2. 格式化为 Agent 易解析的结构（如表格 + 关键词标记）

**涉及文件**：

| 文件 | 变更 |
|------|------|
| `mcp_server/readme` | 追加能力边界说明 |
| `docs/mcp-capabilities.md` | 新建 — Agent 可读的能力清单 |

**预估工作量**：0.5 小时

---

## 三、优先级排序与执行顺序

```
P0 ─── 任务1 (pct_change bug) ───── 阻塞所有涨跌幅相关分析
 │
P1 ─── 任务2+3 (行业/板块数据) ──── Agent 选股的核心能力缺口
 │
P2 ─── 任务5 (中文搜索) ────────── 提升搜索体验
 │
P3 ─── 任务6 (文档化) ──────────── 辅助 Agent 了解能力边界
 │
P4 ─── 任务4 (分钟线) ──────────── 评估后决定是否实施
```

### 推荐执行路径

**第一轮（P0）**：
1. 修复 `pct_change` 列名 bug — 30 分钟
2. 重新拉取数据验证 — 30 分钟

**第二轮（P1）**：
3. 实现行业 + 概念板块数据模块 — 4 小时
4. 新增 3 个 MCP 行业工具 — 1 小时

**第三轮（P2-P3）**：
5. 改进 `search_tickers` 支持中文 — 1 小时
6. 编写 MCP 能力文档 — 0.5 小时

**第四轮（P4）**：
7. 与用户确认分钟线需求优先级
8. 按需实施

---

## 四、风险与注意事项

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 修复 pct_change 后需全量重拉数据 | 耗时约 30 分钟 | 可后台运行 |
| 申万行业分类定期更新 | 分类可能过时 | 每月同步一次 |
| 概念板块成分股变动频繁 | 数据滞后 | 实时查 AKShare，不依赖缓存 |
| 分钟线数据量快速增长 | 存储膨胀 | 设置数据保留期（如 60 天） |

---

## 五、附录：Agent 对话中暴露的详细限制

以下是从飞书 Agent 对话中提取的原始限制记录：

```
1. pct_change 字段 NaN — get_history 返回的最近数据涨跌幅缺失
2. 无板块指数 — 只能从个股自建等权指数
3. 无分钟线数据 — 条件3只能用 (close-open)/open 近似
4. search_tickers 不支持中文 — 无法直接按行业搜索
5. get_index_data 默认给沪深300 — 无其他指数可选
```
