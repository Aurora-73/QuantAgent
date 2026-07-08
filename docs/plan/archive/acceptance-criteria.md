# 量化交易系统 — 项目验收计划

> 版本：v1.0  
> 日期：2026-07-03  
> 范围：quant-system 全部模块  
> 前置文档：`docs/plan/phase-a-b-plan.md`（架构方案）、`docs/plan/issues.md`（缺陷跟踪）

---

## 一、验收范围

| 层级 | 模块 | 说明 |
|------|------|------|
| 数据 | data/ | AKShare 数据采集、DuckDB 存储、行情查询 |
| 研究 | research/ | 因子引擎（25+ 因子）、回测引擎（VectorBT + 简化版） |
| 策略 | strategies/ | 4 个插件化策略（momentum / event_driven / sentiment / regime_switch） |
| 风险 | risk/ | 压力测试、Brinson 归因、衰减检测、投资组合优化 |
| 知识 | knowledge/ | 层级记忆（日/周/月/季/年）、事件库、假设库、Wiki |
| MCP | mcp_server/ | MCP 工具（data / knowledge / risk 三组） |
| 执行 | execution/ | 模拟执行引擎、经纪商抽象层 |
| 监控 | monitoring/ | 指标追踪、告警管理、实盘偏差检测 |
| 集成 | integrations/ | Qlib / vnpy / OpenBB / TradingAgents 适配层 |
| 配置 | configs/ | pydantic-settings（YAML + .env + 环境变量） |
| 脚本 | scripts/ | 数据更新、日报生成、回测运行 |

---

## 二、验收标准

### 2.1 数据层

| 检查项 | 方法 | 通过标准 |
|--------|------|----------|
| AKShare 数据源连通 | 运行 `python -m scripts update-data` | 成功获取指定股票日线数据 |
| 数据清洗 | 检查 DataFrame 无 null OHLCV | 缺失值 < 1% |
| DuckDB 持久化 | 查询 `stock_daily` 表行数 | 每只股票 > 200 条 |
| 交易日历推断 | `get_calendar()` | 返回当年交易日列表，count > 200 |
| 因子数据存储 | 查询 `factors` 表 | 至少 1 只股票有预计算因子 |
| 市场概况 | `get_market_overview()` | 3 个指数均有最新收盘价 |

### 2.2 研究层

| 检查项 | 方法 | 通过标准 |
|--------|------|----------|
| 因子引擎计算 | `get_factors("600519")` | 返回 ≥ 20 条因子值 |
| 因子评估 | `run_factor_evaluation("600519", "momentum_20d")` | IC / ICIR 不为空 |
| 信号回测 | `run_backtest("momentum", "600519")` | 返回完整指标（total_return / sharpe_ratio / win_rate / trade_count） |
| 组合回测 | 直接调用 BacktestEngine.portfolio_backtest | 返回 equity_curve |
| Walk-Forward | `scripts.backtest.run_walk_forward()` | 平均夏普 > -1.0 |
| 因子分组回测 | factor_backtest() | group_returns 非空 |

### 2.3 策略层

| 检查项 | 方法 | 通过标准 |
|--------|------|----------|
| 策略注册表 | `list_strategies()` | 返回 4 个已注册策略 |
| 策略创建 | `create_strategy("momentum")` | 返回 StrategyBase 实例 |
| 特征准备 | `MomentumStrategy.prepare_features()` | 生成动量/RSI/趋势强度特征 |
| 信号生成 | `MomentumStrategy.generate_signal()` | 返回 Signal 列表 |
| 仓位管理 | `MomentumStrategy.position_sizing()` | 返回 TradeOrder 列表 |
| 风险检查 | `MomentumStrategy.risk_check()` | 有效风险检查结果 |

### 2.4 风险层

| 检查项 | 方法 | 通过标准 |
|--------|------|----------|
| 压力测试（4 场景） | `run_stress_test("600519")` | 4 个场景均有结果，all_survived 布尔值正确 |
| Brinson 归因 | `run_brinson_attribution()` | 三效应之和 ≈ 超额收益 |
| 衰减检测 | `run_decay_detection("600519")` | 返回 alerts 列表，is_decaying |
| 综合风险报告 | `get_risk_report("600519")` | 同时包含 stress_test + decay_detection |
| 健康检查 | `run_health_check()` | 返回 total/passed/warnings/failed |

### 2.5 知识层

| 检查项 | 方法 | 通过标准 |
|--------|------|----------|
| Wiki 搜索 | `wiki_search("动量突破")` | 返回 ≥ 1 条结果，含 title / content / score |
| 知识库统计 | `get_knowledge_stats()` | 返回文档数 / 事件数 / 假设数 |
| 事件搜索 | `search_events("600519")` | 按股票/类型/时间过滤返回事件 |
| 决策记忆 | `get_recent_decisions()` | 返回近期决策记录 |
| 预测准确率 | `get_prediction_accuracy()` | 正确转换，无 NaN 崩溃 |
| 日报获取 | `get_daily_report("2026-07-03")` | 返回 OKF 8 段格式或明确"无日报" |

### 2.6 MCP 服务层

| 检查项 | 方法 | 通过标准 |
|--------|------|----------|
| 服务启动 | `python -m mcp_server.server` | 启动成功，无 import 错误 |
| 工具列表 | MCP 客户端列出工具 | 可见全部 MCP 工具 |
| 行情工具 | 调用 get_quote / get_history | 返回 json，pct_change 正确计算 |
| 因子工具 | 调用 get_factors / run_factor_evaluation | 返回因子值或友好提示 |
| 风险工具 | 调用 run_stress_test / run_backtest | 参数验证正常工作 |
| 知识工具 | 调用 wiki_search / get_recent_events | 数据正确序列化 |
| 错误处理 | 传入无效参数 | 返回 error 字段，不崩溃 |
| 边界情况 | 空数据 / 未来日期 / 无效股票 | 返回友好错误提示 |
| 编码 | 中文参数 | 正常返回，无乱码 / UnicodeEncodeError |

### 2.7 执行层

| 检查项 | 方法 | 通过标准 |
|--------|------|----------|
| 模拟回放 | ExecutionSimulator.run() | 以时间顺序回放并记录成交 |
| 经纪商接口 | BrokerBase 子类 | 实现 connect / place_order / get_positions |

### 2.8 配置与日志

| 检查项 | 方法 | 通过标准 |
|--------|------|----------|
| 配置加载 | settings 实例化 | 从 YAML + .env 正确合并 |
| 日志输出 | loguru 写入文件 | 按天轮转，JSONL 结构化 |
| 关键参数 | 回测参数 / 策略阈值 | 可通过 .env 覆盖 |

---

## 三、测试流程

### 阶段 1：启动验证（5 分钟）

```
1. cd quant-system
2. python -m mcp_server.server        # 确认无 import 错误
3. python -c "from data.storage import DataStorage; s=DataStorage(); print(s.stats())"
```

### 阶段 2：MCP 工具冒烟（10 分钟）

依次调用以下工具，确认均返回有效 JSON：

```
基础：get_quote → get_history → get_market_overview → get_universe → get_calendar
因子：get_factors → run_factor_evaluation
知识：wiki_search → get_knowledge_stats → get_recent_decisions
风险：run_stress_test → run_decay_detection → run_health_check
回测：run_backtest → list_strategies
```

### 阶段 3：边界测试（10 分钟）

```
空策略：  run_backtest(strategy="")
无效股票：run_backtest(ticker="INVALID")
未来日期：run_backtest(start_date="2099-01-01)
颠倒日期：run_backtest(start_date="2026-07-01", end_date="2025-01-01")
数据不足：run_factor_evaluation(ticker="TEST_AAPL")
```

### 阶段 4：数据完整性（5 分钟）

```
get_db_stats()          → 确认各表行数合理
get_prediction_accuracy() → 确认无 NaN 崩溃
compare_backtest_runs() → 确认返回历史记录
```

### 阶段 5：回归验证

修复后需验证：
1. 原 bug 未重现
2. 相邻工具未受影响（如修改 run_backtest 后需检查 list_strategies）

---

## 四、质量门禁

| 门禁 | 要求 | 阻断性 |
|------|------|--------|
| G1: 服务启动 | `python -m mcp_server.server` 无报错退出 | 阻断 |
| G2: Import | 所有工具模块 import 无异常 | 阻断 |
| G3: 工具列表 | MCP 客户端可见全部 MCP 工具 | 阻断 |
| G4: 核心工具 | 行情 + 因子 + 回测 + Wiki 工具返回有效数据 | 阻断 |
| G5: 错误处理 | 无效参数返回 error 字段，不崩溃 | 非阻断，P2 |
| G6: 中文编码 | 中文输入输出无乱码 | 非阻断，P1 |
| G7: NaN 守卫 | 无数据场景不返回 NaN/崩溃 | 阻断 |
| G8: 参数验证 | run_backtest 验证策略名/股票/日期 | 非阻断，P1 |
| Q1: 文档完整 | README / MCP readme / issues.md 存在且准确 | 非阻断，P2 |

---

## 五、已知问题与风险

### 5.1 已知限制

| 问题 | 影响 | 状态 |
|------|------|------|
| VectorBT 在 Python 3.13 下 import 挂起 | 回测退化为简化版（无 VectorBT 加速） | 已绕过，HAS_VECTORBT=False |
| Riskfolio-Lib 在 Python 3.13 下 import 挂起 | 投资组合优化不可用 | 已绕过，HAS_RISKFOLIO=False |
| AKShare 需直连国内服务器，不能用代理 | 配置时需注意代理切换 | 已在 CLAUDE.md 记录 |
| Claude MCP 不支持 cwd | 配置时需用 PYTHONPATH 替代 | 已在 mcp_server/readme 记录 |

### 5.2 风险

| 风险 | 可能性 | 影响 | 缓解 |
|------|--------|------|------|
| 因子引擎对低流动性股票计算不稳定 | 中 | 中 | 因子评估有数据量下限检查 |
| 回测假设与实盘偏差 | 高 | 高 | 简化回测仅为参考，实盘需独立验证 |
| MCP JSON 序列化遗漏特殊类型 | 低 | 中 | 工具函数统一 ensure_ascii=False |

---

## 六、签署标准

项目通过验收当且满足：

- [ ] G1-G4 全部通过（服务启动 + Import + 工具列表 + 核心工具）
- [ ] G5 + G7 全部通过（错误处理 + NaN 守卫）
- [ ] 阶段 1-3 冒烟测试完成，无阻断性 bug
- [ ] 所有已知 bug 已记录在 issues.md
- [ ] MCP 客户端可稳定调用全部 MCP 工具

---

## 附录：工具清单

### tools_data.py（6 个）
get_quote / get_history / get_factors / get_index_data / get_universe / get_market_overview / search_tickers / get_calendar / run_factor_evaluation

### tools_knowledge.py（10 个）
get_daily_report / search_events / wiki_search / get_knowledge_stats / get_recent_events / get_decision_accuracy / get_recent_decisions / get_prediction_accuracy / get_db_stats / get_social_sentiment / search_hypotheses

### tools_risk.py（12 个）
run_stress_test / run_brinson_attribution / run_decay_detection / get_risk_report / list_strategies / get_strategy_config / run_backtest / compare_backtest_runs / run_health_check / get_market_regime
