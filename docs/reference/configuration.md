# 配置文档

> Quant System 统一配置管理说明。

---

## 配置加载顺序

配置按以下优先级加载（后加载的覆盖先加载的）：

1. `configs/app.yaml` — 结构化配置（YAML文件）
2. `configs/.env` — 环境变量（键值对）
3. 系统环境变量 — 最高优先级

**示例**：如果 `app.yaml` 中设置了 `max_single_position: 0.05`，而 `.env` 中设置了 `MAX_SINGLE_POSITION=0.10`，最终生效的是 `0.10`。

---

## 配置文件

### 1. .env 文件

用于存储敏感信息和简单配置：

```bash
# 复制模板创建
cp configs/.env.example configs/.env
```

**环境变量**（均可选）：

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `SENDCHAN_SENDKEY_ME` | ServerChan 发送密钥（个人） | 无 |
| `SENDCHAN_SENDKEY_DAISEN` | ServerChan 发送密钥（备用） | 无 |
| `HTTP_PROXY` | HTTP 代理 | 无 |
| `HTTPS_PROXY` | HTTPS 代理 | 无 |

### 2. app.yaml 文件

用于存储结构化配置：

```yaml
risk:
  max_single_position: 0.05
  max_sector_exposure: 0.20
  max_drawdown_stop: -0.05

strategy:
  momentum:
    lookback: 20
    entry_threshold: 0.05
    exit_threshold: -0.02

backtest:
  init_cash: 1000000
  fees: 0.001
  slippage: 0.001
```

---

## 配置参数详解

### 路径配置

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `db_path` | str | `data/quant.duckdb` | DuckDB 数据库路径 |
| `knowledge_dir` | str | `knowledge` | 知识库目录 |
| `log_dir` | str | `logs` | 日志目录 |
| `log_level` | str | `INFO` | 日志级别（DEBUG/INFO/WARNING/ERROR） |
| `reference_dir` | str | `../_reference` | 参考数据目录 |

### 数据配置

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `default_start_date` | str | `20200101` | 默认开始日期 |
| `default_universe` | str | `csi300` | 默认股票池 |
| `data_request_sleep` | float | `0.3` | 数据请求间隔（秒） |
| `default_index_code` | str | `000300` | 默认指数代码（沪深300） |

### 通知配置

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `sendchan_sendkey_me` | str | None | ServerChan 发送密钥 |
| `sendchan_sendkey_daisen` | str | None | ServerChan 备用密钥 |
| `sendchan_api_url` | str | `https://sctapi.ftqq.com/{sendkey}.send` | API地址 |

### 风控配置

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `max_single_position` | float | `0.05` | 单只股票最大仓位（5%） |
| `max_sector_exposure` | float | `0.20` | 单行业最大敞口（20%） |
| `max_total_exposure` | float | `1.00` | 总敞口上限（100%） |
| `max_daily_turnover` | float | `0.10` | 每日最大换手率（10%） |
| `max_drawdown_stop` | float | `-0.05` | 回撤熔断阈值（-5%） |
| `daily_loss_limit` | float | `-0.02` | 每日亏损限制（-2%） |
| `min_daily_volume` | float | `50_000_000` | 最小日成交量（5000万） |
| `volatility_cap` | float | `3.0` | 波动率上限（3倍） |
| `consecutive_losses_limit` | int | `5` | 连续亏损次数限制 |
| `risk_free_rate` | float | `0.02` | 无风险利率（2%） |

**风控参数调优建议**：

| 策略类型 | max_single_position | max_sector_exposure | max_drawdown_stop |
|---------|---------------------|---------------------|-------------------|
| 动量策略 | 0.05-0.10 | 0.20-0.30 | -0.05 ~ -0.10 |
| 事件驱动 | 0.03-0.05 | 0.15-0.25 | -0.03 ~ -0.05 |
| 情绪策略 | 0.02-0.05 | 0.15-0.20 | -0.03 ~ -0.05 |
| 市场中性 | 0.02-0.03 | 0.10-0.15 | -0.03 ~ -0.05 |

### 动量策略默认配置

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `momentum_lookback` | int | `20` | 回看周期（天数） |
| `momentum_entry_threshold` | float | `0.05` | 入场阈值（5%） |
| `momentum_exit_threshold` | float | `-0.02` | 出场阈值（-2%） |
| `momentum_rsi_overbought` | int | `70` | RSI超买阈值 |
| `momentum_rsi_oversold` | int | `30` | RSI超卖阈值 |
| `momentum_max_position_pct` | float | `0.05` | 单只股票最大仓位 |
| `momentum_target_positions` | int | `10` | 目标持仓数量 |
| `momentum_holding_min_days` | int | `3` | 最小持仓天数 |
| `momentum_holding_max_days` | int | `20` | 最大持仓天数 |
| `momentum_holding_typical_days` | int | `10` | 典型持仓天数 |

### 回测配置

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `backtest_init_cash` | float | `1_000_000` | 初始资金（100万） |
| `backtest_fees` | float | `0.001` | 交易费用（0.1%） |
| `backtest_slippage` | float | `0.001` | 滑点（0.1%） |
| `backtest_freq` | str | `B` | 回测频率（B=交易日） |
| `backtest_train_window` | int | `252` | 训练窗口（一年交易日） |
| `backtest_test_window` | int | `63` | 测试窗口（一个季度） |
| `backtest_step` | int | `21` | 步长（一个月） |
| `backtest_topk` | int | `50` | 持仓数量上限 |
| `backtest_n_drop` | int | `5` | 每期换股数量 |

**回测费用模型**：
```
总费用 = 手续费(0.001) + 滑点(0.001) + 印花税(0.001)
```

### 调度配置

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `schedule_data_update_time` | str | `15:30` | 数据更新时间 |
| `schedule_research_time` | str | `16:00` | 研究运行时间 |

### 因子评估配置

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `factor_ic_min_samples` | int | `30` | IC计算最小样本数 |
| `factor_ic_rolling_window` | int | `60` | IC滚动窗口 |
| `factor_group_count` | int | `5` | 分组数量 |
| `factor_decay_max_lag` | int | `20` | 衰减最大滞后 |
| `factor_decay_min_samples` | int | `30` | 衰减最小样本数 |
| `factor_holding_period` | int | `5` | 持仓周期 |
| `factor_lookahead_period` | int | `5` | 前瞻周期 |

### 新闻/事件配置

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `news_tier1_weight` | float | `1.0` | Tier1新闻权重 |
| `news_tier2_weight` | float | `0.8` | Tier2新闻权重 |
| `news_tier3_weight` | float | `0.6` | Tier3新闻权重 |
| `news_tier4_weight` | float | `0.4` | Tier4新闻权重 |
| `news_confidence_boost_per_source` | float | `0.1` | 多源置信度加成 |
| `news_confidence_boost_cap` | float | `0.3` | 置信度加成上限 |
| `news_dedup_time_window_hours` | int | `24` | 去重时间窗口 |
| `news_dedup_similarity_threshold` | float | `0.8` | 去重相似度阈值 |
| `news_high_confidence_threshold` | float | `0.7` | 高置信度阈值 |
| `news_multi_source_threshold` | int | `2` | 多源验证阈值 |

### Qlib 集成配置

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `qlib_provider_uri` | str | `~/.qlib/qlib_data/cn_data` | Qlib数据路径 |
| `qlib_lgbm_loss` | str | `mse` | LightGBM损失函数 |
| `qlib_lgbm_early_stopping` | int | `50` | 早停轮数 |
| `qlib_lgbm_num_boost` | int | `1000` | 迭代次数 |
| `qlib_lstm_hidden_size` | int | `64` | LSTM隐藏层大小 |
| `qlib_lstm_num_layers` | int | `2` | LSTM层数 |
| `qlib_lstm_epochs` | int | `200` | LSTM训练轮数 |
| `qlib_lstm_lr` | float | `0.001` | LSTM学习率 |
| `qlib_train_start` | str | `2020-01-01` | 训练开始日期 |
| `qlib_train_end` | str | `2023-12-31` | 训练结束日期 |
| `qlib_limit_threshold` | float | `0.095` | 涨停阈值 |
| `qlib_open_cost` | float | `0.0005` | 开仓成本 |
| `qlib_close_cost` | float | `0.0015` | 平仓成本 |
| `qlib_min_cost` | int | `5` | 最低成本 |

---

## 使用配置

### Python API

```python
from configs.settings import settings

# 获取风控参数
max_position = settings.max_single_position
max_drawdown = settings.max_drawdown_stop

# 获取策略参数
lookback = settings.momentum_lookback
entry_threshold = settings.momentum_entry_threshold

# 获取回测配置
init_cash = settings.backtest_init_cash
fees = settings.backtest_fees
```

### 环境变量覆盖

在运行前设置环境变量：

```bash
# Linux / macOS
export MAX_SINGLE_POSITION=0.10
python -m scripts backtest

# Windows PowerShell
$env:MAX_SINGLE_POSITION="0.10"
python -m scripts backtest
```

---

## 配置验证

运行健康检查验证配置：

```bash
python -m scripts health_check
```

检查内容：
- 数据库连接是否正常
- API Key 是否配置
- 配置参数是否合理
- 目录是否存在

---

## 配置迁移

### 从旧版本迁移

如果从早期版本升级，需要更新配置文件：

1. 复制新的 `.env.example` 模板
2. 合并旧配置到新文件
3. 检查新增配置项

### 配置备份

```bash
# 备份配置文件
cp configs/.env configs/.env.backup
cp configs/app.yaml configs/app.yaml.backup

# 恢复配置
cp configs/.env.backup configs/.env
cp configs/app.yaml.backup configs/app.yaml
```

---

## 安全注意事项

1. **不要将 `.env` 文件提交到版本控制**
2. **API Key 应使用环境变量或密钥管理服务**
3. **配置文件权限应设置为 600（仅所有者可读）**
4. **敏感配置不应打印到日志中**
