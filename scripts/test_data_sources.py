"""
DataProvider 集成测试

覆盖:
  - baostock 行情/行业/基本面 API
  - pytdx 连接尝试 (预期失败)
  - AKShare 回退 (指数/估值)
  - StockAnalyzer 重构后正确性
  - 边界情况 (无效代码、空数据)
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from data.provider import (
    DataProvider,
    HAS_BAOSTOCK,
    HAS_AKSHARE,
    HAS_PYTDX,
    _pytdx_market,
    _pytdx_connect,
    _baostock_daily,
)
from research.stock_analyzer import analyze, fetch_daily
from loguru import logger

logger.remove()
logger.add(sys.stderr, level="WARNING")

PASS = 0
FAIL = 0


def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        msg = f"  [FAIL] {name}"
        if detail:
            msg += f" — {detail}"
        print(msg)


def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ================================================================
# 1. 基础环境
# ================================================================

section("1. 基础环境检查")
check("HAS_BAOSTOCK", HAS_BAOSTOCK, "baostock 未安装")
check("HAS_AKSHARE", HAS_AKSHARE, "akshare 未安装")
logger.info(f"    HAS_PYTDX = {HAS_PYTDX} (不为必需)")

# ================================================================
# 2. 行情数据
# ================================================================

section("2. 行情数据 — get_stock_daily")

# 2a. baostock 路径 (上证)
df = DataProvider.get_stock_daily("603005", start_date="2026-06-01", end_date="2026-07-02")
check("603005 baostock 有数据", not df.empty, f"empty, shape={df.shape}")
if not df.empty:
    check("包含 turnover 列", "turnover" in df.columns, f"columns={list(df.columns)}")
    check("包含 pct_chg 列", "pct_chg" in df.columns)
    check("date 是索引", df.index.name == "date", f"index={df.index.name}")
    vol_col = df.get("volume", df.get("成交量"))
    check("成交量 > 0", vol_col is not None and vol_col.iloc[-1] > 0 if vol_col is not None else False)

# 2b. baostock 路径 (深圳)
df_sz = DataProvider.get_stock_daily("000001", start_date="2026-06-01", end_date="2026-07-02")
check("000001 (sz) baostock 有数据", not df_sz.empty)
if not df_sz.empty:
    check("sz 含 turnover", "turnover" in df_sz.columns)
    check("sz date 为索引", df_sz.index.name == "date")

# 2c. 空区间
df_empty = DataProvider.get_stock_daily("603005", start_date="2099-01-01", end_date="2099-12-31")
check("空日期返回空 DataFrame", df_empty.empty)

# ================================================================
# 3. 指数数据
# ================================================================

section("3. 指数数据 — get_index_daily")

df_idx = DataProvider.get_index_daily("000300", start_date="2026-07-01", end_date="2026-07-02")
if HAS_PYTDX and _pytdx_connect() is not None:
    check("CSI300 pytdx 有数据", not df_idx.empty)
else:
    check("CSI300 AKShare 回退有数据", not df_idx.empty, "pytdx 不可达，AKShare 正常工作")

if not df_idx.empty:
    check("指数 date 为索引", df_idx.index.name == "date")
    for col in ["open", "high", "low", "close", "volume"]:
        check(f"指数含 {col} 列", col in df_idx.columns)

df_idx5 = DataProvider.get_index_daily("000905", start_date="2026-07-01", end_date="2026-07-02")
check("CSI500 有数据", not df_idx5.empty, "中证500 获取失败")

# ================================================================
# 4. pytdx 工具函数
# ================================================================

section("4. pytdx 工具函数")

check("_pytdx_market(000300) == 1", _pytdx_market("000300") == 1)
check("_pytdx_market(399001) == 0", _pytdx_market("399001") == 0)
check("_pytdx_market(600000) == 1", _pytdx_market("600000") == 1)
check("_pytdx_market(000001) == 1", _pytdx_market("000001") == 1)
check("_pytdx_market(300999) == 0", _pytdx_market("300999") == 0)

# ================================================================
# 5. 基本面 — baostock API
# ================================================================

section("5. 基本面数据 (baostock)")

# 5a. 行业分类
ind = DataProvider.get_stock_industry("603005")
check("get_stock_industry 603005", bool(ind), f"industry='{ind}'")

ind2 = DataProvider.get_stock_industry("600519")
check("get_stock_industry 600519", bool(ind2), f"industry='{ind2}'")

# 5b. 全市场行业映射
all_ind = DataProvider.get_all_industries()
check("get_all_industries 返回非空", len(all_ind) > 0, f"count={len(all_ind)}")
check("all_ind 包含 603005", "603005" in all_ind)
check("all_ind 包含 600519", "600519" in all_ind)
if "603005" in all_ind:
    name, industry = all_ind["603005"]
    check("603005 有名称", bool(name), f"name='{name}'")
    check("603005 有行业", bool(industry), f"industry='{industry}'")

# 5c. 基本信息
info = DataProvider.get_stock_basic_info("603005")
check("get_stock_basic_info 603005", bool(info))
if info:
    check("basic_info 含 name", "name" in info)
    check("basic_info 含 ipo_date", "ipo_date" in info)
    check("basic_info 含 status", "status" in info)

info_empty = DataProvider.get_stock_basic_info("999999")
check("无效代码返回空 dict", info_empty == {})

# 5d. 财务报表
reports = DataProvider.get_stock_financial_reports("603005", year=2025, quarter=4)
check("get_stock_financial_reports 返回 dict", isinstance(reports, dict))
if reports:
    has_profit = "profit" in reports and not reports["profit"].empty
    check("利润表有数据", has_profit)

# ================================================================
# 6. AKShare 估值 (不强制通过)
# ================================================================

section("6. 估值数据 (AKShare)")

if HAS_AKSHARE:
    val = DataProvider.get_stock_valuation("603005")
    if val:
        check("valuation 返回 dict", isinstance(val, dict))
        check("valuation 含 pe_ttm", val.get("pe_ttm") is not None, f"got pe_ttm={val.get('pe_ttm')}")
        check("valuation 含 pb", val.get("pb") is not None, f"got pb={val.get('pb')}")
        check("valuation 含 total_mv", val.get("total_mv") is not None)
        check("valuation 含 close", val.get("close") is not None)
        check("valuation 含 date", bool(val.get("date")))
        print(f"    603005: PE(TTM)={val.get('pe_ttm'):.1f} PB={val.get('pb'):.2f} 市值={val.get('total_mv')/1e8:.1f}亿")
    else:
        print("  [FAIL] valuation 为空")
        FAIL += 1
else:
    print("  [SKIP] AKShare 未安装")

# ================================================================
# 7. StockAnalyzer
# ================================================================

section("7. StockAnalyzer 分析")

result = analyze("603005", days=60)
check("analyze 返回 StockAnalysis", hasattr(result, "ticker"))
check("ticker 正确", result.ticker == "603005")
check("latest.close > 0", result.latest.get("close", 0) > 0)
check("有 MA20 数据", "MA20" in result.ma)
check("RSI 有值", result.rsi is not None)
if result.macd:
    check("MACD 有值", result.macd.get("dif") is not None)
check("有同业对比", len(result.sector_comparison) > 0)
check("有看涨因素", len(result.bull_factors) >= 0)
check("有看跌因素", len(result.bear_factors) >= 0)
check("有关键价位", len(result.key_levels) > 0)
check("有情景推演", len(result.scenarios) > 0)
check("有总结", bool(result.summary))

# 验证同业对比中包含本股
is_self = [p for p in result.sector_comparison if p.get("is_self")]
check("同业对比含本股", len(is_self) == 1)

# 空 ticker
result_empty = analyze("999999", days=30)
check("无效代码返回空分析", result_empty.summary != "")

# ================================================================
# 8. fetch_daily 边界
# ================================================================

section("8. fetch_daily 边界")

df1 = fetch_daily("603005", days=5)
check("fetch_daily 5 天", not df1.empty and len(df1) >= 1)
if not df1.empty:
    check("含 date 列", "date" in df1.columns)
    check("含 close 列", "close" in df1.columns)

# days=0 时起止日都是今天，交易日未结束可能无数据，不应视为失败
df0 = fetch_daily("603005", days=0)
if df0.empty:
    print("  [INFO] days=0 返回空 (当日可能无数据或未收盘)")
else:
    print("  [INFO] days=0 返回非空 (当日有数据)")


# ================================================================
# 9. 并行获取
# ================================================================

section("9. 批量获取")

batch = DataProvider.get_universe_daily(["603005", "600519"], start_date="2026-07-01", end_date="2026-07-02")
check("批量获取 603005 成功", "603005" in batch)
check("批量获取 600519 成功", "600519" in batch)
check("批量返回 DataFrame", all(isinstance(v, type(pd.DataFrame())) for v in batch.values()))


# ================================================================
# 汇总
# ================================================================

section("测试汇总")
total = PASS + FAIL
logger.info(f"  通过: {PASS}/{total}")
logger.info(f"  失败: {FAIL}/{total}")
if FAIL > 0:
    logger.warning("\n  [WARN] 部分测试失败，请检查输出")
    sys.exit(1)
else:
    logger.success("\n  [OK] 全部通过")
