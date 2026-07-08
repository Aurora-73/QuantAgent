# 数据源分析报告

> 日期: 2026-07-03 | 目的: 评估 A 股量化数据源，确定系统最佳数据策略

---

## 一、系统数据流现状 (2026-07-03 更新)

```
## 行情数据
baostock (优先) ──> get_stock_daily() ──> DataCleaner ──> DuckDB
                     (OHLCV+turnover+pctChg)
AKShare (回退)  ──> get_stock_daily()   ──> 同上 (缺 turnover)

## 指数数据
pytdx (尝试)    ──> get_index_daily()   ──> ❌ 本机网络不可达
AKShare (实际)  ──> get_index_daily()   ──> DuckDB (仍为单点故障)

## 基本面数据
baostock (新增) ──> get_stock_industry()    ──> DataProvider (行业分类)
baostock (新增) ──> get_stock_basic_info()   ──> DataProvider (上市信息)
baostock (新增) ──> get_stock_financial_reports() ──> DataProvider (财务报表)
AKShare         ──> get_stock_valuation()    ──> PE/PB/PS (唯一来源)

## 行情分析
StockAnalyzer   ──> DataProvider (baostock→AKShare) ──> 已重构，消除重复 baostock 调用

## 市场数据
AKShare (唯一)  ──> get_sector/concept_data ──> 临时使用 (未存储)
AKShare (唯一)  ──> 北向资金/融资融券      ──> 正常

## 新闻
AKShare 东方财富+财联社 ──> AKShareCollector ──> events 表 (已接入)
```

## 二、系统数据缺口 (更新)

| 缺口 | 影响 | 严重度 | 状态 |
|------|------|--------|------|
| **指数数据单点故障** — 仅 AKShare | MarketRegimeDetector 失效 | **高** | ⏳ pytdx 本机不可达，仍需 AKShare |
| **无实时行情** — baostock 仅历史 | 无法盘中决策 | **中** | ⏳ 待解决 |
| ~~**news 是死胡同**~~ | EventDrivenStrategy 可用 | **高** | ✅ 已解决（2026-07-06，AKShare 新闻接入 events 表） |
| **财务数据可获取但未存储** | 无法计算 ROE 等因子 | **中** | ✅ baostock 财务 API 可用，需接入流水线 |
| **行业分类已可用** | FactorNeutralizer 截面去偏 | **低** | ✅ baostock get_all_industries() 已就绪 |
| **AKShare 回退缺乏 turnover** | baostock 宕机时换手率丢失 | **中** | 未解决 |

## 三、候选数据源全景

### 3.1 A 股行情 (OHLCV)

| 数据源 | 类型 | 实时 | 历史深度 | 稳定性 | 费用 |
|--------|------|------|---------|--------|------|
| **baostock** | 自有服务器 | ❌ | 2006~ | ★★★★★ | 免费 |
| **pytdx** | 通达信协议直连 | ✅ <1s | 1990~ | ★★★★☆ | 免费 |
| **AKShare** | 爬虫(东方财富) | ⚠️ 分钟级 | 1990~ | ★★☆☆☆ | 免费 |
| **Tushare Pro** | 商业 API | ✅ 秒级 | 1990~ | ★★★★★ | ~500元/年 |

> 注: pytdx 已验证**本机网络不可达** (connect 返回 False)，需代理或换网络环境才能使用。

### 3.2 财务/基本面

| 数据源 | 内容 | 质量 | 费用 |
|--------|------|------|------|
| **baostock query_stock_basic()** | 名称、IPO/退市日、类型、状态 | ★★★★ | 免费 |
| **baostock 财务 APIs** | 利润表、资产负债表、现金流量表 | ★★★★ | 免费 |
| **AKShare stock_a_lg_indicator()** | PE/PB/PS/市值 | ★★★ | 免费 |
| **Tushare Pro** | 专业清洗财务 + 因子库 | ★★★★★ | ~500元/年 |

> 注: baostock 的 `query_stock_basic()` 返回的是基本信息，**不包含 PE/PB/市值**（我之前分析有误）。PE/PB 仍需 AKShare 或 Tushare Pro。

### 3.3 Tushare Pro 详细评估

| 评估项 | 说明 |
|--------|------|
| **费用** | 基础积分 100 元 (注册送)，完整权限约 500 元/年 |
| **实时行情** | 秒级延迟，支持 stocks/指数/ETF |
| **财务数据** | 专业清洗，含利润表、资产负债表、现金流、财务指标 |
| **因子数据** | 提供日线因子 (20+ 技术因子) |
| **行业分类** | 申万行业分类 (业界标准) |
| **新闻/公告** | 上市公司公告、新闻快讯 |
| **另类数据** | 龙虎榜、股东、IPO 等 |
| **接入难度** | 需 token，有频率限制 (200次/分钟) |
| **最大优势** | 统一数据源替代 baostock + AKShare + pytdx 的组合 |
| **最大劣势** | 付费，且高级接口需额外积分 |

### 3.4 新闻/事件

| 数据源 | 类型 | 可行性 |
|--------|------|--------|
| **OpenBB (yfinance)** | 英文新闻聚合 | 依赖 openbb 包安装 |
| **yfinance** | 英文新闻 | 已实现，需配置 |
| **AKShare** 东方财富新闻 | A 股新闻 | 可用但需换接口 |
| **巨潮资讯 (cninfo)** | A 股官方公告(Tier 1) | 需自实现爬虫 |
| **Tushare Pro** | 新闻/公告 | 高质量但付费 |

## 四、实施进展

### ✅ 已完成 (Step 1-3)

| 项目 | 文件 | 说明 |
|------|------|------|
| `DataProvider.get_stock_industry()` | provider.py | baostock query_stock_industry() |
| `DataProvider.get_all_industries()` | provider.py | 全市场行业映射 {ticker: (name, industry)} |
| `DataProvider.get_stock_basic_info()` | provider.py | baostock query_stock_basic() |
| `DataProvider.get_stock_financial_reports()` | provider.py | baostock 5 种财务报表 API |
| `get_index_daily()` pytdx 优先 | provider.py | 已接入但不可达, 回退 AKShare |
| StockAnalyzer 重构 | stock_analyzer.py | 消除重复 baostock 调用，改用 DataProvider |

### ⚠️ pytdx 不可达

从本机测试 7 个 TDX 服务器均无法连接 (connect 返回 False)。
**不影响现有功能** — 代码回退到 AKShare。如果后续需要 TDX 数据，需要：
1. 通过代理服务器连接
2. 换用其他网络环境
3. 使用 Tushare Pro 替代

### 📋 待实施

| 优先级 | 项目 | 依赖 |
|--------|------|------|
| ~~**P0**~~ | ~~解决新闻源问题，让 EventDrivenStrategy 可用~~ | ✅ 已解决（AKShare 新闻接入） |
| **P1** | 将 baostock 财务/行业数据接入 daily_research 流水线 | 已完成 API |
| **P2** | FactorNeutralizer 接入截面数据 (行业+市值) | 行业数据已就绪 |
| **P3** | 评估 Tushare Pro / 替代 pytdx | 无 |

## 五、关于 Tushare Pro 的结论

### 如果预算允许 (~500元/年)

Tushare Pro 是目前最佳的统一数据后端方案，优势明显：
1. **单数据源替代 3 个** — 不再需要 baostock + AKShare + pytdx 的组合
2. **数据质量最高** — 专业清洗，错误率低
3. **覆盖全面** — 行情 + 财务 + 行业 + 新闻 + 另类数据
4. **接口稳定** — 商业 SLA，不会突然断掉

### 如果不预算

当前 baostock + AKShare 的组合已经够用：
- 行情: baostock (足够稳定)
- 指数: AKShare (目前工作正常)
- 财务/行业: baostock API 已就绪 (新增)
- PE/PB: AKShare (唯一依赖)

### 推荐

**现阶段不建议购买 Tushare Pro**。原因：
1. 当前组合覆盖 90% 需求
2. 用户系统是盘后分析，不需要实时行情
3. 新闻问题 Tushare Pro 也解决不了 (A 股新闻没有好方案)
4. 等 pytdx 确实需要 / AKShare 真的挂了再考虑

## 六、架构调整方案 (最新)

```python
# DataProvider 当前架构
class DataProvider:
    # Tier 1 — baostock (核心，已完成)
    get_stock_daily()            ✅ baostock -> AKShare fallback
    get_stock_list()             ✅ baostock -> AKShare fallback
    get_csi300_components()      ✅ baostock -> AKShare fallback
    get_stock_industry()         ✅ baostock query_stock_industry() (NEW)
    get_all_industries()         ✅ baostock query_stock_industry() (NEW)
    get_stock_basic_info()       ✅ baostock query_stock_basic() (NEW)
    get_stock_financial_reports()✅ baostock 5 种财务 API (NEW)

    # Tier 2 — pytdx (已尝试，本机不可达)
    get_index_daily()            ⚠️ pytdx -> AKShare (pytdx 不工作)

    # Tier 3 — AKShare (补充，保留)
    get_index_daily()            ✅ AKShare fallback (实际主力)
    get_stock_valuation()        ✅ AKShare (PE/PB/PS，无免费替代)
    get_stock_financial()        ✅ AKShare (财务指标，可备选)
    get_sector_data()            ✅ AKShare (独家)
    get_concept_data()           ✅ AKShare (独家)
    get_north_flow()             ✅ AKShare (独家)
    get_margin_data()            ✅ AKShare (独家)
```
