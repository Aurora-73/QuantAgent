# 常见问题与修复记录

> 基于真实问题记录整理，持续更新。

---

## 数据层问题

### 1. AKShare / 东方财富数据连接失败

**问题现象**：
```log
ERROR | data.provider:get_stock_daily:75 - 获取 600519 数据失败:
ProxyError: Unable to connect to proxy
```
或：
```log
ConnectionError: Remote end closed connection without response
```

**原因**：两种不同的失败场景：

| 场景 | 错误类型 | 根因 |
|------|---------|------|
| 代理阻塞 | `ProxyError` | Windows 系统代理使 `requests` 走代理访问 eastmoney，但代理不通 |
| 端点不可达 | `ConnectionError` | `push2his.eastmoney.com` 的历史 K 线 API 在某些网络环境下被 CDN 屏蔽或限流 |

**诊断方法**：
```python
import urllib.request
print(urllib.request.getproxies())

import requests
r = requests.get('https://push2.eastmoney.com/api/qt/stock/get?secid=1.600519&fields=f43',
                 timeout=10)
print(r.status_code)
```

**修复方案**：
- **方案1**：绕开系统代理，在调用 AKShare 时设置 `NO_PROXY=*`
- **方案2**：改用 `ak.stock_zh_a_daily()` 使用腾讯数据源（稳定）

**已验证的工作组合**：
| 数据源 | 端点 | 状态 |
|--------|------|------|
| AKShare 个股日线 | `ak.stock_zh_a_daily()` | ✅ 稳定（腾讯源） |
| AKShare 个股日线 | `ak.stock_zh_a_hist()` | ❌ `push2his.eastmoney.com` 不可达 |

---

### 2. stock_daily 表为 0 行

**问题现象**：运行 `update-data` 后 `stock_daily` 为空，但 `index_daily` 有数据。

**排查路径**：
1. 检查 `stock_zh_a_hist` 是否抛出异常（代理问题）
2. 检查返回的 DataFrame 是否为空（端点不可达时静默返回空）
3. 检查 `provider.py` 中列名映射（中文→英文）是否匹配实际 API 返回

**修复**：改用 `ak.stock_zh_a_daily()`，该函数返回英文列名，无需映射。

---

### 3. DuckDB 连接问题

**问题现象**：
```log
RuntimeError: Invalid Input Error: IO Error: Could not set lock on file "quant.duckdb"
```

**原因**：
- 另一个进程正在使用数据库文件
- 数据库文件被占用或权限不足

**修复方案**：
1. 关闭所有使用 DuckDB 的进程
2. 删除 `quant.duckdb.wal` 文件（如果存在）
3. 检查文件权限

---

## 计算层问题

### 4. 因子计算 NaN 问题

**问题现象**：
- `get_prediction_accuracy` 返回 `cannot convert float NaN to integer`
- 因子值出现大量 NaN

**原因**：
- DuckDB 返回 NaN 时，`int(NaN)` 崩溃
- 数据缺失或计算窗口不足

**修复方案**：
- 在 `storage.py` 中添加 NaN 守卫，NaN 时返回 0
- 确保数据完整性（至少 20 条有效观测值）

---

### 5. 回测指标异常

**问题现象**：
- `win_rate` 始终为 0.0
- `sharpe_ratio` 为 NaN

**原因**：
- `_simple_signal_backtest` 中硬编码 `"win_rate": 0.0`
- 当 returns 全为零或 std 为 NaN 时，sharpe = NaN

**修复方案**：
- 在回测循环中记录每笔交易 PnL，计算 win_rate = 盈利交易数 / 总交易数
- 添加 NaN 守卫，std < 1e-10 或为 NaN 时默认返回 0.0

---

## API 层问题

### 6. MCP 工具调用错误

**问题现象**：
- `run_stress_test` 报错：无数据: 000300
- `run_brinson_attribution` 报错：list object has no attribute get
- `get_market_overview` 报错：The truth value of a Series is ambiguous

**修复方案**：
- `run_stress_test`：默认参数改为 "600519"（贵州茅台）
- `run_brinson_attribution`：添加参数类型校验，返回清晰错误提示
- `get_market_overview`：`if prev` → `if prev is not None`

---

## 环境问题

### 8. Windows GBK 编码问题

**问题现象**：
- YAML 文件加载失败
- JSONL 文件读取乱码

**原因**：Windows 默认编码为 GBK，需显式指定 UTF-8

**修复方案**：
```python
open(file_path, encoding="utf-8")
```

---

### 9. 终端乱码

**问题现象**：Windows 终端无法显示中文日志

**原因**：Windows 终端 GBK 编码无法显示 UTF-8 中文

**修复方案**：使用 ASCII 标记 `[OK]/[!]` 替代 emoji

---

### 10. 依赖缺失

**问题现象**：
```log
ModuleNotFoundError: No module named 'loguru'
ModuleNotFoundError: No module named 'requests'
```

**修复方案**：依赖已拆分为三档：
```bash
pip install -r requirements-research.txt
```

---

## 回测问题

### 11. 参数验证缺失

**问题现象**：空策略/无效策略/空股票/无效股票/日期颠倒/未来日期均无报错

**修复方案**：`tools_risk.py run_backtest` 已添加参数验证：
- 策略名和股票代码不能为空
- 开始日期/结束日期格式校验
- 开始日期不能晚于结束日期
- 开始日期不能是未来日期
- 空输出时返回明确错误

---

### 12. 因子评估数据不足

**问题现象**：`TEST_AAPL` 返回 `IC=null, ICIR=null`

**修复方案**：添加有效观测值计数检查（< 20 条给出警告），IC/ICIR 均为 null 时返回 warning 字段

---

## 通用诊断流程

```
1. 检查日志 → 定位错误模块
2. 检查数据 → 确认数据完整性
3. 检查配置 → 确认 .env 和 app.yaml
4. 检查依赖 → 确认 requirements 已安装
5. 运行健康检查 → python -m scripts health_check
6. 搜索 issues.md → 查看是否已有解决方案
```

---

**快速命令**：
```bash
# 健康检查
python -m scripts health_check

# 验证环境
python examples/00_quick_start.py

# 查看数据库统计
python -m scripts show_knowledge --type stats
```
