# Linux 服务器测试计划

> 创建日期：2026-07-06
> 背景：Windows 本机执行耗 CPU 任务（回测、因子计算、全流程验证）时卡死，这些任务移到 Linux 服务器上测试。
> 前置条件：将 `quant-system/` 目录同步到 Linux 服务器，已安装依赖（`pip install -r requirements.txt`），已配置 `.env`。

---

## 一、环境准备

### 1.1 代码同步
```bash
# 假设服务器目录为 ~/quant-system/QuantAgent
rsync -avz --exclude='.venv' --exclude='__pycache__' --exclude='*.pyc' \
  /home/edalab/Desktop/cme_code/quant-system/QuantAgent/ user@server:~/quant-system/QuantAgent/
```

### 1.2 依赖安装
```bash
cd ~/quant-system/QuantAgent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 1.3 配置
```bash
# 复制并编辑 .env
cp configs/.env.example configs/.env
# 填入 SENDCHAN_SENDKEY_*（如需通知）

# 验证配置
python -m scripts.health_check
```

### 1.4 数据库迁移（如需重建）
```bash
# 方案 A：直接同步 Windows 上的 DuckDB 文件（推荐，已包含 301 只股票数据）
rsync -avz data/quant.duckdb user@server:~/quant-system/QuantAgent/data/

# 方案 B：全新初始化（耗时约 30 分钟）
python -m scripts.update_data --universe csi300
```

---

## 二、耗 CPU 任务测试清单

> 这些任务在 Windows 本机执行时卡死，必须在 Linux 服务器上测试。

### 2.1 因子批量计算（P0）

**目的**：验证 29 个注册因子全部计算成功，解决"factors 表只有 26 个因子"的问题。

**命令**：
```bash
python -m scripts.compute_factors --universe csi300
```

**预期输出**：
- 成功计算 29 个因子
- `research.factors` 表新增约 300 只股票 × 1574 交易日 × 29 因子 ≈ 1,370 万行
- 耗时预估：30-60 分钟（Linux 服务器）

**验证方法**：
```bash
python -c "
import duckdb
conn = duckdb.connect('data/quant.duckdb')
# 因子数量
result = conn.execute('SELECT COUNT(DISTINCT factor_name) FROM research.factors').fetchone()
print(f'因子数量: {result[0]}')  # 预期 29
# 总行数
result = conn.execute('SELECT COUNT(*) FROM research.factors').fetchone()
print(f'总行数: {result[0]}')
# 每个因子的覆盖情况
result = conn.execute('''
    SELECT factor_name, COUNT(DISTINCT ticker) as tickers, COUNT(*) as rows
    FROM research.factors GROUP BY factor_name ORDER BY factor_name
''').fetchall()
for r in result:
    print(f'  {r[0]}: {r[1]} 只股票, {r[2]} 行')
"
```

**通过标准**：
- 29 个因子全部有数据
- 每个因子覆盖 ≥ 290 只股票
- 无 FATAL 错误

---

### 2.2 因子评估与衰减检测（P0）

**目的**：验证 IC/ICIR 评估和衰减检测流程。

**命令**：
```bash
python -m scripts.evaluate_factors
python -m scripts.detect_decay
```

**预期输出**：
- 每个因子的 IC 均值、ICIR、分组收益
- 衰减检测报告（哪些因子近期失效）

**验证方法**：
```bash
python -c "
import duckdb
conn = duckdb.connect('data/quant.duckdb')
tables = conn.execute(\"SELECT table_name FROM information_schema.tables WHERE table_schema='research'\").fetchall()
print('research schema 表:', [t[0] for t in tables])
# 检查因子评估结果
if conn.execute(\"SELECT COUNT(*) FROM research.factor_evaluation\").fetchone()[0] > 0:
    print('因子评估: ✅ 有数据')
"
```

**通过标准**：
- 无异常退出
- 评估结果写入 `research.factor_evaluation` 表

---

### 2.3 daily_research 全流程验证（P0）

**目的**：验证完整的每日研究流程（数据→因子→策略→风控→日报）。

**命令**：
```bash
python -m scripts.daily_research
```

**预期输出**：
- Step 1/5：市场快照（CSI300 指数数据）
- Step 2/5：因子计算（29 个因子）
- Step 3/5：新闻采集 + 结构化事件入库（30 条左右）
- Step 4/5：日报生成（`knowledge/daily/YYYY-MM-DD.md`）
- Step 4.5/5：预测追踪 + 决策记忆
- Step 5/5：风险检查
- 总耗时：10-30 分钟

**验证方法**：
```bash
# 1. 检查日报是否生成
ls -la knowledge/daily/ | tail -5

# 2. 检查事件表
python -c "
import duckdb
conn = duckdb.connect('data/quant.duckdb')
result = conn.execute('SELECT COUNT(*) FROM events').fetchone()
print(f'事件数: {result[0]}')
result = conn.execute(\"SELECT COUNT(*) FROM events WHERE tags LIKE '%news_cold_start%'\").fetchone()
print(f'冷启动事件: {result[0]}')
"

# 3. 检查决策记忆
python -c "
import duckdb
conn = duckdb.connect('data/quant.duckdb')
result = conn.execute('SELECT COUNT(*) FROM decision_memory').fetchone()
print(f'决策记忆: {result[0]}')
"
```

**通过标准**：
- 无 FATAL 错误，流程完整执行
- 日报文件生成且内容完整
- 事件表有新增记录
- decision_memory 有新增记录

---

### 2.4 回测验证（P1）

**目的**：验证 BacktestEngine 在完整 CSI300 数据上的回测能力。

**命令**：
```bash
# 单策略回测
python -m scripts.backtest --strategy momentum --tickers 600519,300750 --start 2024-01-01 --end 2026-06-30

# 参数扫描（更耗时）
python -m scripts.backtest --strategy momentum --scan --tickers 600519 --start 2024-01-01 --end 2026-06-30
```

**预期输出**：
- 回测权益曲线
- 夏普比率、最大回撤、年化收益等指标
- `backtest_runs` 和 `backtest_equity` 表新增记录

**验证方法**：
```bash
python -c "
import duckdb
conn = duckdb.connect('data/quant.duckdb')
result = conn.execute('SELECT COUNT(*) FROM backtest_runs').fetchone()
print(f'回测记录: {result[0]}')
result = conn.execute('SELECT COUNT(*) FROM backtest_equity').fetchone()
print(f'权益曲线点: {result[0]}')
"
```

**通过标准**：
- 回测完成无异常
- 指标合理（夏普在 -2 到 3 之间，回撤在 0-60% 之间）
- 数据正确写入 DuckDB

---

### 2.5 压力测试与 Brinson 归因（P1）

**目的**：验证风控模块在历史危机场景下的表现。

**命令**：
```bash
python -m scripts.run_stress_test --portfolio <portfolio_config>
python -m scripts.run_brinson_attribution --portfolio <portfolio_config> --benchmark 000300
```

**预期输出**：
- 4 个危机场景（2015/2018/2020/2024）的压力测试报告
- Brinson 配置效应 + 选股效应 + 交互效应

**通过标准**：
- 无异常退出
- 报告内容完整

---

### 2.6 Walk-Forward 优化（P2）

**目的**：验证滚动窗口优化流程。

**命令**：
```bash
python -m scripts.walk_forward --strategy momentum --tickers 600519 --start 2022-01-01 --end 2026-06-30
```

**通过标准**：
- 滚动窗口正确切分
- 每个窗口都有参数优化结果
- 无内存溢出

---

## 三、轻量级任务（Windows 已完成或可在 Windows 完成）

| 任务 | 状态 | 备注 |
|------|------|------|
| LLM API Key 配置 | ✅ 已完成 | .env 文件已创建，API Key 待用户填入 |
| Scheduler 配置 | ✅ 已完成 | settings.py 已补全 schedule_* 字段 |
| print→logger 替换 | ✅ 已完成 | 核心脚本已替换 |
| 股票池补齐到 CSI300 | ✅ 已完成 | 301 只股票，231,481 条记录 |
| DuckDB 索引删除 bug 修复 | ✅ 已完成 | save_index_daily/save_stock_daily 改用 DELETE+INSERT |

---

## 四、执行顺序建议

```
1. 环境准备（15 分钟）
   └─ 代码同步 + 依赖安装 + 配置

2. 数据验证（5 分钟）
   └─ health_check 确认数据完整

3. 因子批量计算（30-60 分钟）★ 耗 CPU
   └─ compute_factors --universe csi300

4. 因子评估（10 分钟）★ 耗 CPU
   └─ evaluate_factors + detect_decay

5. daily_research 全流程（10-30 分钟）★ 耗 CPU
   └─ daily_research

6. 回测验证（10-20 分钟）★ 耗 CPU
   └─ backtest --strategy momentum

7. 风控验证（10 分钟）★ 耗 CPU
   └─ stress_test + brinson

8. Scheduler 启用（5 分钟）
   └─ 配置 crontab 或 nohup 运行
```

---

## 五、风险与回滚

### 5.1 数据库备份
```bash
# 测试前备份
cp data/quant.duckdb data/quant.duckdb.backup.$(date +%Y%m%d)

# 如测试失败需回滚
mv data/quant.duckdb.backup.YYYYMMDD data/quant.duckdb
```

### 5.2 已知风险
1. **DuckDB 索引删除 bug**：已在 Windows 修复（改用 DELETE+INSERT），Linux 上需验证 DuckDB 版本行为是否一致
2. **内存占用**：因子批量计算可能占用 4-8GB 内存，确保服务器有足够内存
3. **baostock 限流**：数据拉取需 `time.sleep(0.3)`，全量更新约需 30 分钟

### 5.3 日志检查
```bash
# 实时查看日志
tail -f logs/daily_research.log

# 检查错误
grep -E "ERROR|FATAL" logs/*.log
```

---

## 六、验收标准

全部 P0 任务通过后，项目达到以下状态：

| 指标 | 目标 | 验证方法 |
|------|------|---------|
| 因子数量 | 29 个 | `SELECT COUNT(DISTINCT factor_name) FROM research.factors` |
| 因子评估 | ✅ 有数据 | `SELECT COUNT(*) FROM research.factor_evaluation` |
| 事件数量 | > 0 | `SELECT COUNT(*) FROM events` |
| 日报 | 当日生成 | `ls knowledge/daily/` |
| 决策记忆 | > 3 条 | `SELECT COUNT(*) FROM decision_memory` |
| 健康检查 | 全部 OK | `python -m scripts.health_check` |
| 回测 | 可运行 | `backtest_runs` 表有新增 |
