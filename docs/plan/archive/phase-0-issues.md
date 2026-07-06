# Phase 0 实施记录

> 日期：2026-07-02
> 状态：已完成

## 已修复问题

### 1. Windows 系统级代理阻塞数据请求

- **现象**：`akshare.stock_zh_a_hist()` 报 ProxyError
- **原因**：Windows Internet Options 注册表代理被 `urllib.request.getproxies()` 读取，无法通过环境变量清除
- **修复**：`data/provider.py` 添加 `_no_proxy()` 上下文管理器，设置 `NO_PROXY=*`
- **影响范围**：所有 akshare 调用（12+ 处）均包裹了 `_no_proxy()`

### 2. EastMoney 历史数据端点不可达

- **现象**：`push2his.eastmoney.com` TCP/TLS 连接成功但 HTTP 请求失败
- **原因**：CDN 端点被限制（IP: 14.103.188.89）
- **修复**：改用 `akshare.stock_zh_a_daily()`（腾讯数据源）
- **副作用**：需要 `sh`/`sz` 前缀，列名为英文

### 3. TradingAgents 降级路径 NameError

- **现象**：`HAS_TRADING_AGENTS=False` 时 `TradingAgentsGraph` 未定义
- **修复**：`integrations/trading_agents.py` 添加 `self.available` 标志，方法内检查

### 4. `research/__init__.py` 导出不全

- 补全了 `FusionEngine`, `MarketSnapshot`, `SourceQuality`, `MarketRegimeDetector`, `MarketRegime` 的导出

### 5. `configs/settings.py` 缺少 scheduler 字段

- 添加了 `schedule_data_update_time` 和 `schedule_research_time`

### 6. `scripts/daily_research.py` 脆弱变量检查

- `if 'snapshot' in dir()` 改为显式 `snapshot = None` 初始化

### 7. print()→logger 残留

- `research/factors.py`, `research/backtest.py`, `scripts/backtest.py`, `scripts/daily_research.py` 共 ~20 处已替换

## 未解决问题

### 1. `logs/` 目录不存在

- `utils/logging.py` 期望日志目录存在，但当前未创建
- 建议：在 `daily_research.py` 或 `scheduler.py` 启动时 `os.makedirs("logs", exist_ok=True)`
- 优先级：P3（当前日志输出到控制台可用）

### 2. OPENAI_API_KEY 未设置

- 健康检查中标记为 `[!!]`，但属于已知状态
- 用户需要时自行配置 `.env`

### 3. 仅 25 只股票有数据

- 健康检查在 `stock_daily` 表发现 25 只股票（少于 30 触发告警）
- 这是 `daily_research.py` 默认限制 `[:20]` 加上测试用 5 只的总和
- 需在 Phase C 增加全量更新命令

### 4. RequestsDependencyWarning

- `urllib3 (2.7.0) or chardet (7.4.3)/charset_normalizer (3.4.1) doesn't match a supported version!`
- 非阻塞，但影响输出整洁度
- 解决：固定 urllib3 版本或忽略 warning

## 验证记录

| 检查项 | 结果 | 数据 |
|--------|------|------|
| stock_daily 行数 | ✅ 通过 | 29,362 行 |
| 因子数 | ✅ 通过 | 675,662 行 |
| 今日日报 | ✅ 生成 | `knowledge/daily/2026-07-02.md` |
| 健康检查 | ✅ 通过 | 6 OK, 2 WARNING, 0 FAILURE |
| research 导出 | ✅ 通过 | 8 个类全部可导入 |
| 沪深300指数 | ✅ 5,940 行 | |
