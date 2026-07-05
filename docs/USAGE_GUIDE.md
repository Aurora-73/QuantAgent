# Quant System 使用指南

> 这是一份面向初学者的完整使用指南，从零开始教你如何使用这个量化交易系统。

---

## 目录

1. [这个系统是什么](#1-这个系统是什么)
2. [环境准备](#2-环境准备)
3. [第一个示例：获取数据](#3-第一个示例获取数据)
4. [第二个示例：计算因子](#4-第二个示例计算因子)
5. [第三个示例：回测策略](#5-第三个示例回测策略)
6. [第四个示例：LLM 分析](#6-第四个示例llm-分析)
7. [第五个示例：知识库](#7-第五个示例知识库)
8. [使用 Qlib 做研究](#8-使用-qlib-做研究)
9. [使用 vnpy 做交易](#9-使用-vnpy-做交易)
10. [每日工作流](#10-每日工作流)
11. [常见问题](#11-常见问题)

---

## 1. 这个系统是什么

这个系统是一个 **LLM 辅助的量化交易平台**，核心理念是：

```
传统量化引擎做交易主干，LLM 只做研究和信息处理，不直接决定下单。
```

它整合了多个开源项目：

| 项目 | 做什么 | 你需要关心吗 |
|------|--------|------------|
| **Qlib** | 因子计算、模型训练、回测 | ✅ 核心 |
| **vnpy** | 连接券商、执行交易 | 实盘时需要 |
| **TradingAgents** | LLM 多Agent分析 | 研究时需要 |
| **Riskfolio-Lib** | 组合优化 | ✅ 核心 |
| **VectorBT** | 快速回测 | ✅ 核心 |
| **AKShare** | A股数据 | ✅ 核心 |

---

## 2. 环境准备

### 2.1 激活虚拟环境

每次使用前，先激活虚拟环境：

```bash
cd /home/edalab/Desktop/cme_code/量化交易/quant-system
source .venv/bin/activate
```

激活后你会看到命令行前面有 `(.venv)` 标志。

### 2.2 配置代理（如果需要）

如果你的网络需要代理，在激活环境后设置：

```bash
export http_proxy="http://127.0.0.1:7890"
export https_proxy="http://127.0.0.1:7890"
```

**注意**：AKShare（获取A股数据）连接的是国内服务器，通常不需要代理。如果不需要代理就能访问国内网站，就不要设置代理。

### 2.3 配置 API Key（可选）

如果你要使用 LLM 功能（TradingAgents），需要配置 OpenAI API Key：

```bash
cp configs/.env.example configs/.env
```

然后编辑 `configs/.env`，填入你的 API Key：

```
OPENAI_API_KEY=sk-你的key
```

如果不配置，LLM 功能不可用，但其他功能（数据、因子、回测、组合优化）都可以正常使用。

### 2.4 验证环境

运行快速验证脚本：

```bash
python examples/00_quick_start.py
```

如果看到 "所有模块正常工作"，说明环境准备完成。

---

## 3. 第一个示例：获取数据

**目标**：获取贵州茅台（600519）的日线数据。

```bash
python examples/01_get_data.py
```

**代码说明**：

```python
from data.provider import DataProvider
from data.storage import DataStorage

# 从 AKShare 获取数据
df = DataProvider.get_stock_daily("600519", "2024-01-01", "2024-12-31")

# 保存到本地数据库
storage = DataStorage()
storage.save_stock_daily("600519", df)

# 从本地数据库加载
df_loaded = storage.load_stock_daily("600519", "2024-01-01", "2024-12-31")
```

**输出说明**：
- `open`: 开盘价
- `high`: 最高价
- `low`: 最低价
- `close`: 收盘价
- `volume`: 成交量
- `amount`: 成交额
- `pct_change`: 涨跌幅
- `turnover`: 换手率

**如果数据获取失败**：
- 检查网络连接
- 如果需要代理，设置 `http_proxy` 和 `https_proxy`
- AKShare 连接的是国内服务器（eastmoney.com），通常不需要代理

---

## 4. 第二个示例：计算因子

**目标**：计算贵州茅台的动量、波动率等因子。

```bash
python examples/02_calc_factors.py
```

**内置因子（25个）**：

| 类别 | 因子 | 含义 |
|------|------|------|
| 动量 | `momentum_5d/10d/20d/60d` | N日收益率 |
| 反转 | `reversal_5d/20d` | N日反转（负动量） |
| 均线 | `ma_deviation_5/20/60` | 偏离N日均线 |
| 成交量 | `volume_ratio_5d/20d` | N日量比 |
| 波动率 | `volatility_20d/60d` | N日历史波动率 |
| 技术 | `rsi_14`, `macd_diff`, `bollinger_position` | RSI、MACD、布林带 |
| 复合 | `quality_momentum`, `smart_money` | 质量动量、聪明资金 |

**如何解读因子值**：

| 因子 | 正值含义 | 负值含义 |
|------|---------|---------|
| `momentum_20d` | 上涨趋势 | 下跌趋势 |
| `reversal_5d` | 近期下跌，可能反弹 | 近期上涨，可能回调 |
| `rsi_14` | >70 超买 | <30 超卖 |
| `volume_ratio_5d` | >1 放量 | <1 缩量 |

---

## 5. 第三个示例：回测策略

**目标**：用动量策略回测贵州茅台。

```bash
python examples/03_backtest.py
```

**策略逻辑**：
- 买入条件：20日动量 > 5%（上涨趋势确认）
- 卖出条件：20日动量 < -2%（下跌趋势确认）

**结果解读**：

| 指标 | 好 | 一般 | 差 |
|------|-----|------|-----|
| 总收益 | >20% | 0-20% | <0% |
| 夏普比率 | >1.5 | 0.5-1.5 | <0.5 |
| 最大回撤 | <-10% | -10%~-20% | >-20% |

**夏普比率**：衡量风险调整后的收益。>1.5 表示每承担1单位风险，获得1.5单位超额收益。

**最大回撤**：从最高点到最低点的最大跌幅。<-10% 表示风险控制较好。

---

## 6. 第四个示例：LLM 分析

**目标**：用 TradingAgents 的多Agent系统分析一只股票。

**前提**：需要配置 `OPENAI_API_KEY`。

```bash
python examples/05_llm_analysis.py
```

**TradingAgents 的分析流程**：

```
市场分析师 → 情绪分析师 → 新闻分析师 → 基本面分析师
    ↓
多空辩论 (看多 vs 看空)
    ↓
研究经理 → 交易员
    ↓
风控辩论 (激进 vs 保守 vs 中性)
    ↓
投资组合经理 → 最终决策
```

**信号含义**：
- `Buy` = 买入 (分数 1.0)
- `Overweight` = 增持 (分数 0.5)
- `Hold` = 持有 (分数 0.0)
- `Underweight` = 减持 (分数 -0.5)
- `Sell` = 卖出 (分数 -1.0)

**注意**：每次分析需要 2-5 分钟，因为要调用 LLM API。

---

## 7. 第五个示例：知识库

**目标**：使用知识库记录和查询信息。

```bash
python examples/04_knowledge.py
```

**知识库结构**：

```
knowledge/
  daily/          日报 (Markdown)
  weekly/         周报
  monthly/        月报
  events/         事件数据库 (JSONL)
  hypotheses/     假设库
  failures/       失败案例
```

**可以存储什么**：
- **日报**：每日市场概况、持仓表现、操作记录
- **事件**：业绩预增、政策利好、行业事件等
- **假设**：待验证的投资假设（如"动量因子在A股有效"）
- **教训**：失败案例和经验总结

---

## 8. 使用 Qlib 做研究

Qlib 是微软开发的 AI 量化研究平台，功能非常强大。

### 8.1 初始化 Qlib

```python
from integrations.qlib_engine import QlibEngine

# 创建引擎
engine = QlibEngine(
    provider_uri="~/.qlib/qlib_data/cn_data",  # 数据路径
    region="cn",                                 # 中国市场
)

# 初始化（首次会下载数据）
engine.init()
```

**注意**：首次初始化会下载约 2GB 的中国市场数据，需要几分钟。

### 8.2 查询数据

```python
# 获取沪深300的收盘价
df = engine.get_features(
    instruments="csi300",
    fields=["$close", "$volume"],
    start_time="2024-01-01",
    end_time="2024-12-31",
)
print(df.head())
```

### 8.3 训练模型

```python
# 训练 LightGBM 模型
model, dataset = engine.train_model(
    model_type="lightgbm",
)

# 也可以训练 LSTM 模型
model, dataset = engine.train_model(
    model_type="lstm",
)
```

### 8.4 回测

```python
# 回测模型
result = engine.run_backtest(
    model=model,
    dataset=dataset,
    start_time="2024-01-01",
    end_time="2024-12-31",
    topk=50,      # 持仓50只股票
    n_drop=5,     # 每期换5只
    account=1e8,  # 初始资金1亿
)
```

### 8.5 使用 Qlib 内置因子

Qlib 有 158 个内置技术因子（Alpha158）：

```python
# 获取 Alpha158 因子
fields = engine.alpha158_fields()
df = engine.get_features(
    instruments="csi300",
    fields=fields,
    start_time="2024-01-01",
    end_time="2024-12-31",
)
```

### 8.6 自定义因子

```python
# 使用 Qlib 表达式定义因子
factor = engine.define_factor("$close / Ref($close, 20) - 1")  # 20日动量
factor = engine.define_factor("Mean($close, 5) / $close - 1")  # 5日均线偏离
factor = engine.define_factor("Std($close, 20)")                # 20日波动率
```

---

## 9. 使用 vnpy 做交易

vnpy 是国内最流行的量化交易框架，支持连接多种券商。

### 9.1 启动引擎

```python
from integrations.vnpy_engine import VnpyEngine

engine = VnpyEngine()
engine.start()
```

### 9.2 连接 CTP（期货）

```python
ctp_setting = {
    "用户名": "你的用户名",
    "密码": "你的密码",
    "经纪商代码": "9999",
    "交易服务器": "180.168.146.187:10201",
    "行情服务器": "180.168.146.187:10211",
    "产品名称": "",
    "授权编码": "",
    "产品信息": "",
}

engine.connect_ctp(ctp_setting)
```

### 9.3 发送订单

```python
# 买入开仓
order_id = engine.send_order(
    symbol="rb2410",      # 螺纹钢2410合约
    exchange="SHFE",      # 上期所
    direction="LONG",     # 做多
    price=3500.0,         # 价格
    volume=1,             # 1手
    order_type="LIMIT",   # 限价单
)
print(f"订单ID: {order_id}")
```

### 9.4 查询持仓和账户

```python
# 查询持仓
positions = engine.get_positions()
for p in positions:
    print(f"  {p['symbol']}: {p['volume']}手")

# 查询账户
accounts = engine.get_accounts()
for a in accounts:
    print(f"  账户余额: {a['balance']:.2f}")
    print(f"  可用资金: {a['available']:.2f}")
```

### 9.5 撤单

```python
engine.cancel_order(order_id, "rb2410", "SHFE")
```

---

## 10. 每日工作流

### 10.1 命令行方式

```bash
# 激活环境
source .venv/bin/activate

# 1. 更新数据
python -m scripts update-data --universe csi300 --start 2024-01-01

# 2. 运行每日研究（不使用LLM）
python -m scripts daily-research --no-llm

# 3. 运行回测
python -m scripts backtest --strategy momentum --ticker 600519 --start 2024-01-01

# 4. 查看知识库
python -m scripts show-knowledge --type stats
python -m scripts show-knowledge --type daily
python -m scripts show-knowledge --type events
```

### 10.2 Python 方式

```python
from datetime import date
from scripts.daily_research import run_daily_research

# 运行今日研究
run_daily_research(
    target_date=date.today(),
    tickers=["600519", "300750", "002475"],  # 指定股票
    use_llm=False,  # 不使用LLM
)
```

### 10.3 自动化（定时任务）

```bash
# 编辑 crontab
crontab -e

# 添加以下行（每天18:00运行）
0 18 * * 1-5 cd /home/edalab/Desktop/cme_code/量化交易/quant-system && .venv/bin/python -m scripts daily-research --no-llm >> /tmp/quant_daily.log 2>&1
```

---

## 11. 常见问题

### Q: 数据获取失败怎么办？

```python
# 检查网络连接
from data.provider import DataProvider
df = DataProvider.get_stock_daily("600519", "2024-01-01")
print(df.empty)  # True = 获取失败
```

如果获取失败，可能是：
1. **网络问题** → 检查是否能访问 eastmoney.com
2. **代理问题** → AKShare 连接国内服务器，通常不需要代理。如果设置了代理，尝试取消代理：
   ```bash
   unset http_proxy
   unset https_proxy
   ```
3. **AKShare 限流** → 等待几秒重试
4. **股票代码错误** → 使用正确的代码（如 "600519" 不是 "600519.SS"）

### Q: Qlib 初始化失败怎么办？

```python
# Qlib 需要下载数据
from integrations.qlib_engine import QlibEngine
engine = QlibEngine()
engine.init()  # 首次会下载约 2GB 数据
```

如果下载失败，可能需要设置代理：
```python
import os
os.environ["http_proxy"] = "http://127.0.0.1:7890"
os.environ["https_proxy"] = "http://127.0.0.1:7890"
```

### Q: TradingAgents 分析很慢怎么办？

TradingAgents 需要调用 LLM API，每次分析需要 2-5 分钟。可以：
1. 使用更快的模型（如 GPT-4o-mini）
2. 减少辩论轮数
3. 只使用部分分析师

### Q: 如何添加新策略？

在 `strategies/` 下创建新目录：

```
strategies/
  my_strategy/
    __init__.py
    config.yaml
    strategy.py
```

在 `strategy.py` 中实现 `StrategyBase` 的 6 个方法：

```python
from strategies.base import StrategyBase, Signal, TradeOrder, RiskCheckResult

class MyStrategy(StrategyBase):
    def prepare_features(self, data):
        # 计算你的因子
        ...

    def generate_signal(self, features, context=None):
        # 生成买卖信号
        ...

    def position_sizing(self, signals, portfolio, total_capital):
        # 计算仓位
        ...

    def risk_check(self, orders, portfolio):
        # 风控检查
        ...

    def expected_holding_period(self):
        return {"min_days": 1, "max_days": 10, "typical_days": 5}

    def kill_switch_condition(self):
        return {"max_drawdown": -0.05, "daily_loss_limit": -0.02}
```

### Q: 如何查看回测结果？

```python
result = BacktestEngine.signal_backtest(...)

# 查看权益曲线
equity = result["equity_curve"]
equity.plot()

# 保存到文件
equity.to_csv("backtest_result.csv")
```

### Q: 如何连接实盘？

1. 先用模拟盘测试
2. 确认策略稳定后，再接实盘
3. 初始资金建议 < 总资金的 10%

```python
# 模拟盘（CTPSimNow）
ctp_setting = {
    "用户名": "...",
    "密码": "...",
    "经纪商代码": "9999",
    "交易服务器": "180.168.146.187:10201",
    "行情服务器": "180.168.146.187:10211",
    "产品名称": "",
    "授权编码": "",
    "产品信息": "",
}
engine.connect_ctp(ctp_setting)
```

### Q: 如何使用代理？

如果你的网络需要代理才能访问外部网站：

```bash
# 设置代理
export http_proxy="http://127.0.0.1:7890"
export https_proxy="http://127.0.0.1:7890"

# 然后运行脚本
python examples/01_get_data.py
```

**注意**：AKShare 连接的是国内服务器（eastmoney.com），通常不需要代理。如果设置了代理反而连接失败，尝试取消代理：

```bash
unset http_proxy
unset https_proxy
```

---

## 附录：文件结构

```
quant-system/
├── configs/                配置文件
│   └── .env.example        API Key 模板
├── data/                   数据层
│   ├── provider.py         AKShare 数据获取
│   ├── storage.py          DuckDB 本地存储
│   ├── cleaner.py          数据清洗
│   └── aligner.py          时间对齐
├── research/               研究层
│   ├── factors.py          25个内置因子
│   ├── backtest.py         回测引擎
│   └── evaluator.py        因子评估
├── strategies/             策略层
│   ├── base/               策略基类
│   └── momentum/           动量策略
├── risk/                   风控层
│   ├── risk_engine.py      风控引擎
│   └── portfolio.py        组合优化
├── knowledge/              知识库
│   └── knowledge_base.py   知识库核心
├── llm/                    LLM 模块
│   ├── summarizer.py       文档摘要
│   ├── extractor.py        事件抽取
│   └── report_agent.py     报告生成
├── integrations/           集成层
│   ├── qlib_engine.py      Qlib 集成
│   ├── vnpy_engine.py      vnpy 集成
│   ├── trading_agents.py   TradingAgents 集成
│   └── openbb_data.py      OpenBB 集成
├── monitoring/             监控层
│   ├── metrics.py          绩效指标
│   └── alerts.py           告警管理
├── scripts/                脚本
│   ├── daily_research.py   每日研究
│   ├── backtest.py         回测工具
│   ├── update_data.py      数据更新
│   └── show_knowledge.py   知识库查询
├── examples/               示例
│   ├── 00_quick_start.py   快速验证
│   ├── 01_get_data.py      获取数据
│   ├── 02_calc_factors.py  计算因子
│   ├── 03_backtest.py      回测策略
│   ├── 04_knowledge.py     知识库
│   └── 05_llm_analysis.py  LLM分析
├── .venv/                  虚拟环境
├── README.md               项目说明
├── USAGE_GUIDE.md          本使用指南
└── requirements.txt        依赖列表
```
