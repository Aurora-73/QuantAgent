# 待解决问题

> 已修复的问题请查看 changelog.md

---

## 环境问题

### ⚠️ Windows GBK 编码
- YAML 文件、JSONL 文件读取默认使用 GBK，需显式指定 utf-8
- 修复：open(file, encoding="utf-8")

### ⚠️ 终端乱码
- Windows 终端 GBK 编码无法显示中文日志，文件内容正确
- 修复：Summary 中使用 ASCII 标记 [OK]/[!] 替代 emoji

### ⚠️ 依赖缺失
- AKShare 未安装：venv 中无 akshare，端到端测试无实际数据但流程正常
- vectorbt 未安装：不影响核心功能，回测模块需要

---

## 待观察

### ℹ️ 2026-07-06 本次发现的非阻断性问题

**1. print 残留不是问题**
- 原 project-status.md 写 "print 残留"，但实际审计：核心模块（research/risk/data/knowledge）基本无运行时 print
- print 集中在 examples/（示例脚本，正常）、scripts/（CLI 入口输出，正常）、docstring 中（示例代码，正常）
- 处理：无需修改，文档中的描述已修正

**2. 告警模块不是完全空壳**
- 原 project-status.md 写 "告警空壳 webhook 通知是空函数 pass"
- 实际：`monitoring/alerts.py` 的 `AlertManager._send_notification` 是 pass，但 `monitoring/notifier.py` 的 `SendChanNotifier` 已完整实现（Server酱推送）
- 差距：AlertManager 未与 SendChanNotifier 对接
- 优先级：P2，scheduler 跑通后再对接

**3. scheduler 配置项缺失**
- `scripts/scheduler.py` 用 `getattr(settings, 'schedule_data_update_time', '15:30')` 读取配置
- `configs/settings.py` 中无 `schedule_*` 相关配置
- 目前走默认值可以工作，但缺少文档化配置
- 优先级：P1，启用 scheduler 时补全

**4. 注册因子 29 个 vs factors 表 26 个**
- `FactorEngine.list_factors()` 返回 29 个注册因子
- `research.factors` 表实际只有 26 个因子的数据
- 3 个因子未计算：可能是基本面因子（缺少财务数据）
- 优先级：P1，批量基本面数据补齐后自然解决

**5. DuckDB Windows 下独占文件锁**
- 同一 DuckDB 文件不能多进程同时打开（IOException）
- 影响：同时跑 update_data 和 health_check 会失败
- 处理：串行执行，DuckDB 已知限制，非 bug
- 优先级：P3，后续可考虑 WAL 模式或只读副本

**6. DuckDB 索引删除失败 bug（已解决）**
- 现象：对带索引的表执行 DELETE 时报 "Failed to delete all rows from index. Only deleted 0 out of N rows"
- 触发：`INSERT OR REPLACE` 触发索引批量删除，或 `DELETE FROM ... WHERE (ticker, date) IN (...)` 子查询删除
- 影响：数据更新流程中断，数据库 invalidated（需 DROP 表重建恢复）
- 根因：DuckDB 在 ART 索引批量删除时的已知问题，`raw.index_daily` 表数据损坏（647 行全 NULL）
- 解决方案：
  1. `save_index_daily` / `save_stock_daily` 改用 `DELETE FROM ... WHERE ticker = ?` + `INSERT`（按 ticker 删除，避免子查询）
  2. 删除损坏的 `index_daily` / `raw.index_daily` 表并重建
  3. 修复后数据更新正常，301 只股票 231,481 条记录入库成功
- 优先级：P2（已解决，Linux 上需验证 DuckDB 版本行为）

**7. PowerShell 命令行参数前导零丢失**
- 现象：`--tickers 002475,002493` 传入脚本后，ticker 变成 `2475`（前导零丢失）
- 原因：PowerShell 将 `002475` 解析为数字 2475，再去掉前导零
- 影响：深市股票（002/300/301 开头）通过命令行传入时无法正确拉取 baostock 数据
- 临时方案：在 Python 脚本中直接传入字符串列表，或用引号包裹 `--tickers "002475,002493"`
- 永久方案：在 `update_fundamentals.py` 中对 ticker 做 `zfill(6)` 补零
- 优先级：P3（Linux 上 bash 不会有此问题）

---

## 已归档问题

所有已修复的问题已归档到 `changelog.md`
