# Phase 4 改进计划：从"查询工具"到"会进化的研究平台"

> 生成日期：2026-07-09 | 最后更新：2026-07-09（按工程化反馈重写）
> **唯一执行主线**：本文档是当前唯一 active plan。Phase 2/3 已归档至 `docs/plan/archive/`，状态总览见 [`docs/project/roadmap.md`](../project/roadmap.md)。
> 核心诊断：骨架搭好了但上半身没长出来——数据有了但分析不及时，日报有了但高阶报告缺失，回测跑了但经验不积累。

---

## 〇、代码现实审计（开工前必读）

本计划基于对现有代码的审计，**不重造已有能力**。下表是每个改进方向对应的"已有什么"和"真正缺什么"，所有任务路径以本表为准。

| 方向 | 已有能力（文件路径） | 真正缺口 |
|------|---------------------|----------|
| 数据更新 | `scripts/daily_research.py` `run_daily_research()` 内含数据拉取（L70-98） | 无独立的纯增量更新任务；`scheduler.run_data_update()` 直接调 `run_daily_research`，数据更新与因子/研究耦合 |
| 交易日历 | `scripts/scheduler.py` `_MARKET_HOLIDAYS`（硬编码，注释标 "approximate"） | 无正式交易日历，不适合 systemd 自动化 |
| 数据新鲜度 | `scripts/health_check.py` `_check_data_freshness()`（L99-135，内联 raw SQL） | storage 层无通用 `get_last_date(table, ticker=None)` API；无统一健康状态枚举 |
| 高阶报告 | `knowledge/knowledge_base.py` `save_report(weekly/monthly/quarterly/annual)`（L96-144）+ 层级压缩辅助方法（L471-502） | 无报告生成逻辑；目录结构已就绪，只缺内容生产 |
| 决策记忆 | `knowledge/decision_memory.py` `record_decision()` + `backfill_returns()`；`data/storage.py` `save_decision`/`get_pending_decision_returns`/`update_decision_returns` | `scripts/backtest.py`（L130）只写 `backtest_runs`，**未**写 `decision_memory`；daily_research 已调用回填但被耦合 |
| 假设库 | `knowledge/knowledge_base.py` 假设状态机 `draft→active→verified/invalidated/obsolete/rejected`（L31-38）+ `save_hypothesis`/`set_hypothesis_status` | 无自动生成入口；假设数量 5 条 |
| 回测主链路 | `research/backtest.py` `BacktestEngine` + `scripts/backtest.py` `run_backtest()`/`run_walk_forward()` | ⚠️ 原计划写的 `strategy/backtest_engine.py` **不存在**；参数扫描在 walk-forward 模式已支持（L206 `--scan`），standard 模式未支持 |
| Agent 委员会 | `agents/committee.py`；`daily_research.py` L388-412 调用但 LLM 已废弃 → 健康检查标 skip | 半空壳，需 ADR 决定去留 |
| MCP 工具 | `mcp_server/tools_data.py` 等，`@register_mcp_tool` 自动发现 | 无缓存层；无 freshness/共线性/leaderboard 工具 |

**重要约束**：
- 假设生命周期**必须复用** `HYPOTHESIS_TRANSITIONS`（`draft/active/verified/invalidated/obsolete/rejected`），**禁止**另造 `proposed/testing/validated/deprecated` 第二套语义。
- 高阶报告**必须用** `KnowledgeBase.save_report(report_type, ...)` 落地到现有 `weekly/monthly/quarterly/annual/` 目录，**不另起** `published` schema。
- DecisionMemory 是**集成任务**不是新系统建设：核心是在 `scripts/backtest.py` 回测完成后调一次 `record_decision`，scheduler 回填已在 `daily_research.py` 存在。

---

## 一、执行顺序总览

```
P0  前置能力（~6h）← 解锁 B1，否则 B1 是空中楼阁
  ├── P0.1 拆分独立增量更新任务        2h
  ├── P0.2 正式交易日历模块            2h
  └── P0.3 storage 层 freshness API    2h

B1  关键基础设施（🔴 ~9h）
  ├── B1.1 Scheduler → systemd         3h   (依赖 P0.1 + P0.2)
  ├── B1.2 数据新鲜度 MCP 工具         2h   (依赖 P0.3)
  └── B1.3 周报/月报/季报生成          4h   (复用 KnowledgeBase)

B2  打通闭环（🟡 ~7h）
  ├── B2.1 回测→决策记忆自动写入       2h   (集成任务，复用 DecisionMemory)
  ├── B2.2 因子共线性报告              2h
  └── B2.3 假设自动生成                3h   (复用 HYPOTHESIS_TRANSITIONS)

ADR 委员会去留决策（~1h）← 提前，不拖到最后
  └── ADR-001 Agent 委员会：删或接 LLM  1h

B3  体验优化（🟠 条件触发，~6h）
  └── 仅当 profiling 证明工具延迟影响使用时启动
      ├── B3.1 慢工具缓存              2h
      ├── B3.2 便利查询工具            2h
      └── B3.3 策略 leaderboard        2h

B4  清理加固（🔵 ~5h）
  ├── B4.1 DuckDB 自动备份             1h
  ├── B4.2 standard 模式参数扫描       1h   (walk-forward 已支持)
  └── B4.3 执行 realism                2h
```

> **与原计划差异**：① 新增 P0 前置；② B4.1 委员会提前为 ADR；③ B3 改为条件触发；④ B4 参数扫描降为 1h（部分已完成）；⑤ 总工时从 32h 调整为 ~28h（P0 6h + B1 9h + B2 7h + ADR 1h + B3 6h + B4 5h）。

---

## 二、P0：前置能力（解锁 B1）

### P0.1 拆分独立增量更新任务

**问题**：`scheduler.run_data_update()`（L56-64）直接调 `run_daily_research(use_llm=False)`，数据更新与因子计算/中性化/新闻采集/日报生成全部耦合。B1.1 的 `incremental_update` 和 B1.2 的 `update_data_incremental` 在此基础上都是空中楼阁。

**方案**：从 `scripts/daily_research.py` 的 Step 1（L70-98）抽取出独立的增量更新函数。

| 步骤 | 内容 | 涉及文件 |
|------|------|----------|
| 1 | 抽取 `update_market_data(target_date, tickers)` 函数 | `scripts/update_data.py`（已存在，扩展） |
| 2 | 只拉取 `max(date)+1` 到今天的缺失数据，非全量重拉 | 同上 |
| 3 | `scheduler.run_data_update()` 改为调 `update_market_data`，不再调 `run_daily_research` | `scripts/scheduler.py` L56-64 |
| 4 | `daily_research.py` Step 1 改为调用同一函数，保持行为一致 | `scripts/daily_research.py` L70-98 |

**接口设计**：
```python
# scripts/update_data.py
def update_market_data(target_date: date = None,
                       tickers: list[str] = None,
                       incremental: bool = True) -> dict:
    """
    独立的市场数据更新任务（不含因子/研究/日报）。

    Args:
        incremental: True 时只拉 max(date)+1 到 target_date 的缺失数据

    Returns:
        {"tickers_updated": int, "rows_added": int, "skipped": list[str]}
    """
```

**验收标准**：
- [ ] `python -m scripts.update_data` 只更新行情，不触发因子计算/日报
- [ ] `incremental=True` 时单次 < 5min（20 只股票）
- [ ] `scheduler.run_data_update()` 不再调用 `run_daily_research`
- [ ] `daily_research.py` 行为不变（仍含数据更新）

**测试**：
- [ ] 单元测试：`test_update_data.py` 验证 incremental 跳过已存在日期
- [ ] 集成测试：调用后 `storage.load_stock_daily` 返回数据含今日

**回滚**：`scheduler.py` 和 `daily_research.py` 改动可独立 revert；`update_data.py` 新函数不影响旧路径。

---

### P0.2 正式交易日历模块

**问题**：`scheduler.py` L28-38 用硬编码 `_MARKET_HOLIDAYS`，注释明确写 "approximate, update yearly"。一旦上 systemd 自动化，定时报表和回填都会错日（把休市日当交易日跑，或反之）。

**方案**：新建交易日历模块，支持多数据源回退。

| 步骤 | 内容 | 涉及文件 |
|------|------|----------|
| 1 | 新建 `data/trading_calendar.py` | 新文件 |
| 2 | 主数据源：AKShare `tool_trade_date_hist_sina()`（A 股交易日历） | 同上 |
| 3 | 回退源：本地 DuckDB 缓存 + 硬编码 holidays（标注为 fallback） | 同上 |
| 4 | `scheduler.is_trading_day()` 改为调 `TradingCalendar.is_trading_day()` | `scripts/scheduler.py` L41-53 |

**接口设计**：
```python
# data/trading_calendar.py
class TradingCalendar:
    def is_trading_day(self, d: date = None) -> bool: ...
    def last_trading_day(self, d: date = None) -> date: ...
    def next_trading_day(self, d: date = None) -> date: ...
    def trading_days_between(self, start: date, end: date) -> list[date]: ...
    def refresh(self) -> None:
        """从 AKShare 拉取最新交易日历并缓存到 DuckDB"""
```

**验收标准**：
- [ ] `TradingCalendar.is_trading_day()` 与 AKShare 官方日历一致
- [ ] AKShare 不可用时回退到缓存 + 硬编码，并 logger.warning
- [ ] `scheduler.is_trading_day()` 委托给新模块，行为不变
- [ ] 缓存表 `trading_calendar` 在 DuckDB 创建

**测试**：
- [ ] 单元测试：已知节假日（春节/国庆）返回 False；周末返回 False
- [ ] 单元测试：`last_trading_day` / `next_trading_day` 边界（周五→周一、节前→节后）
- [ ] mock 测试：AKShare 失败时回退路径正常

**回滚**：`scheduler.py` 保留旧 `_MARKET_HOLIDAYS` 作为 fallback，新模块失败时自动回退。

---

### P0.3 storage 层 freshness API

**问题**：`health_check.py` L99-135 用内联 raw SQL `SELECT MAX(date) FROM stock_daily` 检查新鲜度。B1.2 的 `check_data_freshness` MCP 工具需要通用能力，但计划里还没定义每张表的 freshness 来源、允许滞后、交易日口径、失败时返回什么。

**方案**：在 `data/storage.py` 抽象 freshness API，统一所有调用方。

| 步骤 | 内容 | 涉及文件 |
|------|------|----------|
| 1 | 新增 `DataStorage.get_last_date(table, ticker=None) -> date` | `data/storage.py` |
| 2 | 新增统一健康状态枚举 `FreshnessStatus` | `data/storage.py` 或 `data/freshness.py` |
| 3 | 定义每张表的 freshness 规则（见下表） | 同上 |
| 4 | `health_check._check_data_freshness()` 改为调新 API | `scripts/health_check.py` L99-135 |

**表 freshness 规则**：

| 表 | 新鲜度来源 | 交易日口径 | 允许滞后 |
|----|-----------|-----------|----------|
| `stock_daily` | `MAX(date)` | 是 | 1 个交易日 |
| `index_daily` | `MAX(date)` | 是 | 1 个交易日 |
| `factors` | `MAX(date)` | 是 | 1 个交易日 |
| `events` | `MAX(timestamp::DATE)` | 否（新闻每日） | 1 天 |
| `financials` | `MAX(report_date)` | 否（季度） | 90 天 |

**接口设计**：
```python
class FreshnessStatus(Enum):
    FRESH = "fresh"        # 在允许滞后内
    STALE = "stale"        # 超过允许滞后但 < 2x
    OUTDATED = "outdated"  # 严重滞后

def get_last_date(self, table: str, ticker: str = None) -> Optional[date]: ...

def get_freshness(self, table: str) -> dict:
    """返回 {last_date, staleness_days, status, allowed_lag}"""
```

**验收标准**：
- [ ] `storage.get_last_date("stock_daily")` 返回最新行情日期
- [ ] `storage.get_last_date("stock_daily", ticker="600519")` 返回单只股票最新日期
- [ ] `storage.get_freshness("stock_daily")` 返回完整状态 dict
- [ ] `health_check` 改造后行为不变（pass/warn/fail 阈值一致）

**测试**：
- [ ] 单元测试：空表返回 None；有数据返回正确日期
- [ ] 单元测试：freshness 状态在交易日/非交易日口径下正确
- [ ] 集成测试：`health_check` 输出与改造前一致

**回滚**：`health_check.py` 保留旧内联 SQL 作为 fallback 分支。

---

## 三、B1：关键基础设施（🔴）

### B1.1 Scheduler → systemd service

**问题**：`scheduler.py` 存在但需手动启动，每次连上来数据滞后 2-3 天。

**依赖**：P0.1（独立增量更新）、P0.2（交易日历）

**方案**：

| 步骤 | 内容 | 涉及文件 |
|------|------|----------|
| 1 | 编写 systemd service + timer unit 文件 | `deploy/quantagent-scheduler.service` + `.timer` |
| 2 | timer 在每日收盘后（15:30）触发，仅交易日执行（由 P0.2 日历判断） | 同上 |
| 3 | `run_data_update()` 改为调 P0.1 的 `update_market_data(incremental=True)` | `scripts/scheduler.py` |
| 4 | 失败告警对接 `monitoring/notifier.py` 的 SendChanNotifier | `scripts/scheduler.py` + `monitoring/alerts.py` |
| 5 | 日志轮转由 systemd journal 自动处理 | — |

**已知问题对接**：`issues.md` 提到 `AlertManager._send_notification` 是 pass，未与 `SendChanNotifier` 对接。本任务需完成对接（issues.md 第 2 项，P2 优先级）。

**验收标准**：
- [ ] `systemctl --user status quantagent-scheduler.timer` 显示 active
- [ ] 交易日 15:30 自动执行，日志写入 journal
- [ ] 增量更新只拉缺失日期，单次 < 5min
- [ ] 失败时 SendChan 推送告警（不再是 pass）
- [ ] 非交易日不触发（由 P0.2 日历保证）

**测试**：
- [ ] 集成测试：`--dry-run` 在非交易日显示"跳过"
- [ ] 集成测试：模拟失败触发告警通知
- [ ] 手动验收：观察一个完整交易日的 journal 日志

**回滚**：`systemctl --user stop quantagent-scheduler.timer`；`scheduler.py` 改动可独立 revert。

---

### B1.2 数据新鲜度 MCP 工具

**问题**：无法通过 MCP 工具检查数据是否过期，也无法一键触发增量更新。

**依赖**：P0.3（freshness API）、P0.1（增量更新函数）

**方案**：新增 2 个 MCP 工具到 `mcp_server/tools_data.py`：

| 工具 | 功能 | read_only | 依赖 |
|------|------|-----------|------|
| `check_data_freshness` | 检查各表新鲜度，返回 staleness + 状态 | ✅ | P0.3 |
| `update_data_incremental` | 触发 P0.1 的增量更新，返回进度 | ❌ | P0.1 |

**`check_data_freshness` 返回结构**（复用 P0.3 的 `FreshnessStatus`）：
```json
{
  "stock_daily": {"last_date": "2026-07-08", "staleness_days": 1, "status": "fresh", "allowed_lag": 1},
  "factors": {"last_date": "2026-07-08", "staleness_days": 1, "status": "fresh", "allowed_lag": 1},
  "index_daily": {"last_date": "2026-07-07", "staleness_days": 2, "status": "stale", "allowed_lag": 1},
  "overall": "warning"
}
```

**验收标准**：
- [ ] 两个工具均有 `@register_mcp_tool` 装饰器，自动发现
- [ ] `check_data_freshness` 返回各表 staleness + 统一状态枚举
- [ ] `update_data_incremental` 只拉缺失日期，返回 `{tickers_updated, rows_added}`
- [ ] 非 read_only 工具需确认（与现有写工具一致）

**测试**：
- [ ] 单元测试：mock storage，验证返回结构
- [ ] 集成测试：`update_data_incremental` 后再调 `check_data_freshness`，staleness 归零

**回滚**：删除两个工具函数即可，不影响其他 MCP 工具。

---

### B1.3 周报/月报/季报生成

**问题**：34 份日报但 0 份高阶报告，系统不做跨时间尺度的模式识别。

**约束**：**必须复用** `KnowledgeBase.save_report(report_type, ...)` 落地到现有 `weekly/monthly/quarterly/annual/` 目录。**不另起** `published` schema，**不新建** `save_higher_order_report`。

**方案**：新建 `research/reporting.py`，生成周/月/季报内容，调 `kb.save_report()` 存储。

| 报告类型 | 聚合窗口 | 核心内容 | 数据来源 |
|----------|----------|----------|----------|
| 周报 | 最近 5 个交易日 | 本周 vs 上周胜率变化、因子 IC 趋势、市场风格 | `decision_memory`、`factors`、`events` |
| 月报 | 最近 20 个交易日 | 月度因子表现排行、衰减检测、策略月度对比 | 同上 + `backtest_runs` |
| 季报 | 最近 60 个交易日 | 季度市场风格切换、策略稳健性、假设验证进展 | 同上 + `hypotheses` |

**数据来源说明**：从 `decision_memory`、`backtest_runs`、`factors`、`events` 表聚合，**不依赖日报文本**（避免日报质量影响高阶报告）。

**存储方式**（复用现有 API）：
```python
kb = KnowledgeBase()
content = generate_weekly_report(target_week)
kb.save_report("weekly", content=content, report_date=target_date)
# 自动落地到 knowledge/weekly/week{WW}-{YYYY}.md
```

**Scheduler 集成**（依赖 P0.2 交易日历）：
- 每周五 16:00 生成周报（`is_trading_day` + weekday==4）
- 每月最后一个交易日 16:00 生成月报
- 每季最后一个交易日 16:00 生成季报

**MCP 工具**：`get_higher_order_report(report_type, report_date)` 调 `kb.load_report()` 查询。

**验收标准**：
- [x] `python -m research.reporting --type weekly` 生成一份周报到 `knowledge/weekly/`
- [x] 报告文件名符合 `KnowledgeBase.save_report` 规则（`week{WW}-{YYYY}.md`）
- [x] 报告包含：因子表现/趋势、策略回测对比、市场事件
- [x] MCP 工具 `get_higher_order_report` 可查历史报告
- [x] `kb.get_stats()` 显示 weekly/monthly/quarterly 计数 > 0

**测试**：
- [x] 单元测试：报告生成函数在无数据时返回合理的"数据不足"报告而非崩溃
- [x] 单元测试：`save_report` 后 `load_report` 能读回内容
- [x] 集成测试：完整流程跑通后 `kb.list_reports("weekly")` 非空

**回滚**：`research/reporting.py` 可独立删除；已生成的报告文件不影响系统。

---

## 四、B2：打通闭环（🟡）

### B2.1 回测 → 决策记忆自动写入

**问题**：73 次回测只有 9 条决策记忆，回测结果没有反馈到决策系统。

**关键认知**：这是**集成任务**，不是新系统建设。`DecisionMemory.record_decision()` 和 `backfill_returns()` 已存在；`daily_research.py` 已调用回填（L580）。缺的只是：`scripts/backtest.py` 回测完成后调一次 `record_decision`。

**真实文件路径**（⚠️ 原计划写的 `strategy/backtest_engine.py` 不存在）：
- 主链路：`research/backtest.py` `BacktestEngine` + `scripts/backtest.py` `run_backtest()`
- 持久化：`scripts/backtest.py` L121-133 已调 `storage.save_backtest_run(result)`

**方案**：

| 步骤 | 内容 | 涉及文件 |
|------|------|----------|
| 1 | `run_backtest()` 在 `save_backtest_run` 后调 `dm.record_decision()` | `scripts/backtest.py` L133 后 |
| 2 | `run_walk_forward()` 同样接入 | `scripts/backtest.py` L294 后 |
| 3 | scheduler 回填已在 `daily_research.py` L580 存在，无需新建 | — |

**decision_memory 写入字段**（复用 `record_decision` 现有签名）：
```python
dm = DecisionMemory(storage)
dm.record_decision(
    ticker=ticker,
    direction="backtest",           # 回测产生的决策标记
    weight=float(result.get("annual_return", 0)),
    reason=f"策略 {strategy_name} 回测，年化 {result.get('annual_return', 0):.2%}, "
           f"夏普 {result.get('sharpe_ratio', 0):.2f}",
    signal_type="backtest",
    strategy=strategy_name,
    decision_date=date.today(),
)
```

**验收标准**：
- [ ] 每次 `run_backtest` 自动写一条 decision_memory
- [ ] `run_walk_forward` 同样写入
- [ ] scheduler 回填（已存在）能回填这些记录的 actual_return
- [ ] `dm.get_accuracy(signal_type="backtest")` 返回有意义统计（样本 > 30）

**测试**：
- [ ] 单元测试：mock 回测，验证 `record_decision` 被调用一次
- [ ] 单元测试：`record_decision` 失败不影响回测结果持久化（`save_backtest_run` 已完成）
- [ ] 集成测试：跑一次回测后 `storage.load_decisions` 包含新记录

**回滚**：删除 `scripts/backtest.py` 中新增的 `record_decision` 调用即可；已写入的 decision_memory 记录可保留（标记为 backtest 历史）。

---

### B2.2 因子共线性报告

**问题**：29 个因子无共线性分析，可能过拟合。

**方案**：新建 `research/factor_analysis.py`：

```python
def compute_factor_correlation(ticker_list, date_range) -> pd.DataFrame:
    """计算 29 个因子的 Pearson 相关性矩阵"""

def detect_collinear_groups(threshold=0.7) -> list[list[str]]:
    """识别高相关因子组（> 0.7），建议每组保留一个"""

def generate_collinearity_report() -> dict:
    """生成完整共线性报告"""
```

**MCP 工具**：`get_factor_collinearity(threshold)`（read_only）

**验收标准**：
- [ ] 输出 29×29 相关性矩阵
- [ ] 识别高相关因子组（阈值可配）
- [ ] MCP 工具可查询
- [ ] **只报告不自动删减**，人工决策

**测试**：
- [ ] 单元测试：已知完全相关因子（如 momentum_5d vs momentum_10d 高相关）被识别
- [ ] 单元测试：阈值边界（0.69 vs 0.71）分组正确
- [ ] 性能测试：29 因子矩阵计算 < 5s

**回滚**：`research/factor_analysis.py` 和 MCP 工具可独立删除。

---

### B2.3 投资假设自动生成

**问题**：5 条假设太少，无自动生成机制。

**约束**：**必须复用** `HYPOTHESIS_TRANSITIONS`（`draft/active/verified/invalidated/obsolete/rejected`）。**禁止**另造 `proposed/testing/validated/deprecated` 第二套语义。

**方案**：新建 `research/hypothesis_generator.py`：

| 触发条件 | 生成的假设 | 初始状态 |
|----------|-----------|----------|
| IC > 0.05 的因子 | "{factor} 具有正向预测能力" | `draft`（复用 `HYPOTHESIS_INITIAL_STATUS`） |
| IC < -0.05 的因子 | "{factor} 具有反向预测能力" | `draft` |
| 回测年化 > 15% | "{strategy} 在 {market_regime} 下有效" | `draft` |

**状态流转**（复用现有状态机）：
- 自动生成 → `draft`
- 人工或定期验证后 → `active`（`kb.set_hypothesis_status(id, "active")`）
- 回测验证通过 → `verified`
- 回测证伪 → `invalidated`
- 不再适用 → `obsolete`

**存储**：调 `kb.save_hypothesis(hypothesis_dict)`，落地到 `knowledge/hypotheses/hypotheses.jsonl`。

**关联回测**：假设 dict 中记录 `validation_run_id`，关联 B2.1 写入的回测记录。

**验收标准**：
- [ ] 因子评估后自动生成假设，初始状态为 `draft`
- [ ] 假设关联验证回测的 `run_id`
- [ ] 假设数量从 5 增长到 30+
- [ ] 状态转换通过 `kb.set_hypothesis_status`，非法转换抛 `StatusError`
- [ ] **不出现** `proposed/testing/validated/deprecated` 等新状态

**测试**：
- [ ] 单元测试：IC > 0.05 触发假设生成
- [ ] 单元测试：`set_hypothesis_status("hyp_xxx", "proposed")` 抛 `StatusError`（非法状态）
- [ ] 单元测试：`draft → active → verified` 路径正常
- [ ] 集成测试：因子评估后 `kb.load_hypotheses(status="draft")` 非空

**回滚**：`research/hypothesis_generator.py` 可独立删除；已生成的假设保留为 draft，人工处理。

---

## 五、ADR-001：Agent 委员会去留（提前决策）

**问题**：`agents/committee.py` 5 个 agent 从未接 LLM，健康检查标 skip。项目定位已收到 MCP Server，内部 LLM 已废弃。继续留成半空壳会误导。

**决策**：在 B3/B4 之前先做 ADR，不拖到最后。

| 选项 | 做法 | 工作量 | 后续维护 |
|------|------|--------|----------|
| A. 接 LLM | 每个 agent 暴露为独立 MCP 工具，接 DeepSeek | 大 | 持续维护 5 个 agent |
| B. 删除 | 移除 `agents/` 目录，清理 `daily_research.py` L388-412 调用，健康检查去掉 skip | 小 | 无 |
| C. 降级为示例 | 移到 `examples/`，标注"外部编排示例"，不在主链路调用 | 中 | 低 |

**建议**：选 B（删除）或 C（降级）。若选 B，需同步清理：
- `daily_research.py` L388-412（AgentCommittee 调用）
- `daily_research.py` L555-572（committee_review → record_decision，需改为其他信号源）
- `scripts/health_check.py` 中 committee 相关检查项
- `roadmap.md` "后续待办 C-2 AICriticAgent LLM 接入"条目

**验收标准**：
- [ ] ADR 文档写入 `docs/decisions/ADR-001-agent-committee.md`
- [ ] 按决策执行（删除/降级/接 LLM）
- [ ] 健康检查不再有 skip 项（若选 B）
- [ ] `daily_research.py` 不再调用 committee（若选 B），决策记忆改用其他信号

**测试**：
- [ ] 集成测试：`daily_research.py` 跑通（若选 B，committee 部分移除后无报错）
- [ ] 健康检查输出 0 skip（若选 B）

**回滚**：删除操作可从 git 恢复；降级操作可移回原位置。

---

## 六、B3：体验优化（🟠 条件触发）

**启动条件**：仅当实际 profiling 证明工具延迟已影响使用时启动。先用 `mcp_server` 的请求日志统计 P95 延迟，确认以下任一成立：
- `get_sector_index` P95 > 10s
- `get_market_overview` P95 > 3s
- 交互式研究时用户反馈卡顿

**若不满足条件，本 Batch 不启动**，避免过度工程化。

### B3.1 慢工具缓存（条件触发）

**方案**：

| 工具 | 缓存策略 | TTL |
|------|----------|-----|
| `get_sector_index` | scheduler 每日预计算，结果缓存到 DuckDB | 1 天 |
| `get_market_overview` | 内存 LRU 缓存 | 5 min |
| `get_sector_list` | 内存 LRU 缓存 | 1 小时 |

**实现**：新建 `mcp_server/cache.py`，装饰器模式：
```python
@cached(ttl=300)
def get_market_overview(): ...
```

**验收标准**：
- [ ] `get_sector_index` 二次调用 < 1s
- [ ] scheduler 预跑后首次调用 < 1s
- [ ] 缓存失效后自动重新计算

**测试**：
- [ ] 性能测试：缓存命中 vs 未命中对比
- [ ] 单元测试：TTL 过期后重新计算

**回滚**：移除 `@cached` 装饰器即可。

---

### B3.2 便利查询工具（条件触发）

**方案**：新增 MCP 工具：

| 工具 | 功能 |
|------|------|
| `get_top_movers` | 列出最近 N 天涨幅/跌幅最大的股票 |
| `get_factor_ranking` | 获取某因子在截面的排名 |
| `get_market_breadth` | 市场广度（涨跌家数、新高新低） |
| `get_factor_performance_comparison` | 多因子同期表现对比 |

**验收标准**：
- [ ] 4 个工具可用，均有 `@register_mcp_tool`
- [ ] 每个工具 < 3s 返回

**测试**：
- [ ] 单元测试：每个工具返回结构正确
- [ ] 集成测试：MCP 自动发现包含这 4 个工具

**回滚**：删除工具函数即可。

---

### B3.3 策略 Leaderboard（条件触发）

**方案**：

| 步骤 | 内容 | 涉及文件 |
|------|------|----------|
| 1 | 新建 `get_strategy_leaderboard` MCP 工具 | `mcp_server/tools_strategy.py` |
| 2 | 从 `storage.load_backtest_runs()` 聚合，按年化/夏普/回撤排序 | 同上 |
| 3 | 支持按时间段过滤（近 1 月/3 月/全部） | 同上 |

**返回结构**：
```json
[
  {"rank": 1, "strategy": "momentum", "annual_return": 0.25, "sharpe": 1.8, "max_dd": -0.12},
  {"rank": 2, "strategy": "event_driven", "annual_return": 0.18, "sharpe": 1.2, "max_dd": -0.15}
]
```

**验收标准**：
- [ ] MCP 工具返回排序后的策略对比
- [ ] 支持时间范围过滤

**测试**：
- [ ] 单元测试：mock backtest_runs，验证排序正确
- [ ] 单元测试：时间过滤边界

**回滚**：删除工具函数即可。

---

## 七、B4：清理与加固（🔵）

### B4.1 DuckDB 自动备份

**问题**：2.6TB 磁盘无任何备份机制。

**方案**：
- 每日凌晨 2:00 用 `duckdb` 的 `EXPORT DATABASE` 导出到 `/backup/quantagent/`
- 保留最近 7 天备份
- scheduler 集成（依赖 P0.2 交易日历，非交易日也备份）

**验收标准**：
- [ ] scheduler 每日自动备份
- [ ] 旧备份自动清理（保留 7 天）
- [ ] 备份文件可恢复（`IMPORT DATABASE` 验证）

**测试**：
- [ ] 集成测试：备份后 `IMPORT DATABASE` 到临时库，数据行数一致
- [ ] 单元测试：清理逻辑保留最近 7 天

**回滚**：停止 scheduler 备份任务；已生成备份保留。

---

### B4.2 standard 模式参数扫描

**问题**：回测 standard 模式不支持网格搜索。

**已知**：walk-forward 模式已支持 `--scan`（`scripts/backtest.py` L206-265）。本任务只需把扫描能力加到 standard 模式。

**方案**：扩展 `scripts/backtest.py` `run_backtest()`：

```bash
python -m scripts.backtest --strategy momentum \
  --param-grid '{"lookback": [5, 10, 20], "threshold": [0.02, 0.05]}'
```

**输出**：JSON 格式的参数组合 × 指标矩阵。

**验收标准**：
- [ ] `--param-grid` 参数在 standard 模式可用
- [ ] 输出每组参数的年化/夏普/回撤
- [ ] walk-forward 模式 `--scan` 行为不变

**测试**：
- [ ] 单元测试：参数网格展开正确
- [ ] 集成测试：standard 模式扫描结果与单次回测一致（相同参数）

**回滚**：移除 `--param-grid` 参数处理即可。

---

### B4.3 执行 Realism

**问题**：execution 模块纯模拟，未考虑市场冲击、涨跌停、停牌。

**涉及文件**：`strategy/execution.py`（需确认是否存在；若不存在则新建）

**方案**：

| 改进 | 内容 |
|------|------|
| 涨跌停限制 | 检查目标价是否触及涨跌停，触及则拒绝成交 |
| 停牌检测 | 检查当日 volume == 0，标记为不可交易 |
| 市场冲击 | 大单（> 日成交量 5%）按 VWAP 滑点 |

**验收标准**：
- [ ] 涨跌停股不成交
- [ ] 停牌股不成交
- [ ] 大单有滑点

**测试**：
- [ ] 单元测试：构造涨跌停场景，验证拒绝成交
- [ ] 单元测试：构造停牌（volume=0）场景，验证拒绝
- [ ] 单元测试：大单滑点计算正确

**回滚**：execution 改动可独立 revert；回测主链路不受影响（realism 是可选增强）。

---

## 八、验收里程碑

| 里程碑 | 完成标志 | 预期效果 |
|--------|---------|----------|
| M0: P0 完成 | 独立增量更新 + 交易日历 + freshness API 可用 | B1 不再是空中楼阁 |
| M1: B1 完成 | scheduler 自动跑 + 周报可查 + freshness MCP 可用 | 数据不再滞后，知识金字塔有上层 |
| M2: B2 完成 | decision_memory > 50 条 + 假设 > 30 条 | 回测→决策→验证闭环打通 |
| M3: ADR 完成 | 委员会去留决策落地，健康检查 0 skip | 系统无空壳模块 |
| M4: B4 完成 | 备份可用 + 参数扫描 + realism | 系统加固完成 |
| M5: B3（条件） | 仅在 profiling 证明需要时 | 交互式研究流畅 |

---

## 九、风险与约束

| 风险 | 影响 | 缓解 |
|------|------|------|
| baostock 限流 | 增量更新失败 | 指数退避重试 + 告警 |
| AKShare 交易日历接口变更 | P0.2 失败 | 回退到缓存 + 硬编码 holidays |
| 周报依赖数据质量 | 报告结论偏差 | 周报生成前先跑 freshness 检查 |
| 因子共线性高 | 删减因子后策略变差 | **只报告不自动删减**，人工决策 |
| systemd 权限 | 可能需要 sudo | 提供 user-level service 备选 |
| DuckDB 独占锁（issues.md 第 5 项） | scheduler 与 health_check 并发失败 | 串行执行，已知限制 |
| 委员会删除影响 daily_research | 决策记忆来源缺失 | ADR 决策时同步改造 record_decision 信号源 |

---

## 十、统一测试与回滚标准

**每个任务必须满足**：

1. **单元测试**：新增/修改的函数有对应单元测试，覆盖正常 + 边界 + 异常路径
2. **集成测试**：涉及多模块的任务有集成测试，验证端到端流程
3. **回滚路径**：明确说明如何回滚（独立删除 / git revert / 配置开关）
4. **不破坏现有**：`pytest tests/` 全部通过；`python -m scripts.health_check` 无新增 fail
5. **文档同步**：改动涉及的接口在代码 docstring 中更新；本计划任务完成后勾选验收项

**项目级回归**（每个 Batch 完成后跑）：
- [ ] `pytest tests/` 全通过
- [ ] `python -m scripts.health_check` 无新增 fail/warn
- [ ] `python -m scripts.db_stats` 输出正常
- [ ] MCP 工具自动发现数量不减少

---

> **核心目标**：把知识金字塔从日报往上填满，把决策闭环打通，让系统从"好用的查询工具"变成"真正会进化的研究平台"。
> **执行原则**：基于现有代码准确改哪里，而不是想做什么。复用已有 API，不重造轮子。
