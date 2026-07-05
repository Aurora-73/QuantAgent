# ADR-0002: DuckDB 分层存储

> 选择 DuckDB 作为核心存储引擎，并采用分层架构。

---

## 状态

**Accepted**

### 上下文

量化交易系统需要高效的数据存储和查询能力，同时支持：
- 时序数据存储
- 因子计算和分析
- 回测数据读写
- 轻量级部署

### 可选方案

| 方案 | 优点 | 缺点 |
|------|------|------|
| **方案A：PostgreSQL** | 成熟，支持并发，功能强大 | 部署复杂，需要独立服务，查询性能一般 |
| **方案B：SQLite** | 轻量，零部署，简单 | 并发性能差，不适合大数据量 |
| **方案C：DuckDB** | 列式存储，查询快，零部署 | 并发写入有限，生态不如 PostgreSQL |

### 最终选择

**方案C：DuckDB**

### 理由

1. **查询性能**：DuckDB 是列式存储，对于分析型查询（如因子计算、聚合）比 PostgreSQL 快 10-100 倍
2. **零部署**：嵌入式数据库，不需要独立服务，适合单机部署和研究环境
3. **数据分析能力**：内置支持复杂 SQL、窗口函数、CTE，适合量化分析
4. **Python 集成**：与 pandas/numpy 无缝集成，数据加载和导出非常方便
5. **文件格式支持**：直接支持读取 CSV、Parquet、JSON 等格式

### 分层架构

| 层级 | 说明 | 表前缀 |
|------|------|--------|
| **raw** | 原始数据，未经清洗 | `raw_*` |
| **cleaned** | 清洗后数据，统一格式 | `cleaned_*` |
| **research** | 研究数据，因子值、信号 | `research.*` |
| **published** | 发布数据，日报、回测结果 | `published.*` |

### 数据流转

```
AKShare → raw_stock_daily → cleaned_stock_daily → stock_daily
                                                      ↓
                                           FactorCalculator → factors
                                                      ↓
                                           StrategyEngine → signals
                                                      ↓
                                           BacktestEngine → backtest_runs
```

### 影响范围

- `data/storage.py`：使用 DuckDB 作为存储引擎
- `research/`：所有因子计算和分析基于 DuckDB
- `knowledge/`：日报和报告存储在文件系统，但元数据存储在 DuckDB

### 验证方法

1. 验证数据加载性能（100万行数据加载时间 < 1秒）
2. 验证因子计算性能（29个因子计算时间 < 10分钟）
3. 验证并发读取能力

### 参考

- DuckDB 官方文档
- Qlib 使用 DuckDB 作为存储引擎
- VectorBT 使用 DuckDB 进行回测数据管理
