"""
StockAnalyzer — 个股多维分析

功能:
  - 行情 + 技术指标 (MA/RSI/MACD/波动率)
  - 换手率 + 量能分析
  - 同业横向对比
  - 结构化多空清单
  - 关键价位情景推演

数据源: 通过 DataProvider 统一获取 (baostock 优先 -> AKShare/pytdx 回退)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd
from loguru import logger


# ── 数据获取 ──────────────────────────────────────────────────────

def fetch_daily(ticker: str, days: int = 365) -> pd.DataFrame:
    """获取日线数据 (通过 DataProvider 统一获取)"""
    from data.provider import DataProvider
    start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    end = datetime.now().strftime("%Y-%m-%d")
    df = DataProvider.get_stock_daily(ticker, start_date=start, end_date=end)
    if not df.empty:
        df = df.reset_index()
        df = df.sort_values("date").reset_index(drop=True)
    return df


# ── 技术指标 ──────────────────────────────────────────────────────

def calc_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """RSI (相对强弱指标)"""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calc_macd(series: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    """MACD (指数平滑异同平均)"""
    ema12 = series.ewm(span=12).mean()
    ema26 = series.ewm(span=26).mean()
    dif = ema12 - ema26
    dea = dif.ewm(span=9).mean()
    bar = 2 * (dif - dea)
    return dif, dea, bar


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """批量添加技术指标"""
    c = df["close"]
    df["MA5"] = c.rolling(5).mean()
    df["MA10"] = c.rolling(10).mean()
    df["MA20"] = c.rolling(20).mean()
    df["MA60"] = c.rolling(60).mean()
    df["MA120"] = c.rolling(120).mean()
    df["RSI"] = calc_rsi(c)
    df["DIF"], df["DEA"], df["MACD_BAR"] = calc_macd(c)
    df["ret"] = c.pct_change()
    df["volatility"] = df["ret"].rolling(20).std() * (252 ** 0.5)
    # 量比 (20日 vs 60日)
    df["vol_ma20"] = df["volume"].rolling(20).mean()
    df["vol_ma60"] = df["volume"].rolling(60).mean()
    return df


# ── 结构化分析 ────────────────────────────────────────────────────

@dataclass
class StockAnalysis:
    """个股分析结果"""
    ticker: str
    data_date: str = ""
    latest: dict = field(default_factory=dict)
    ma: dict = field(default_factory=dict)
    rsi: Optional[float] = None
    macd: dict = field(default_factory=dict)
    volatility: Optional[float] = None
    turnover_rate: Optional[float] = None
    volume_ratio: Optional[float] = None
    ytd_return: Optional[float] = None
    sector_comparison: list = field(default_factory=list)
    bull_factors: list = field(default_factory=list)
    bear_factors: list = field(default_factory=list)
    key_levels: dict = field(default_factory=dict)
    scenarios: list = field(default_factory=list)
    summary: str = ""


def analyze(ticker: str, days: int = 365) -> StockAnalysis:
    """全量分析入口"""
    result = StockAnalysis(ticker=ticker)

    df = fetch_daily(ticker, days)
    if df.empty:
        result.summary = f"{ticker} 无可用数据"
        return result

    df = add_indicators(df)
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest
    result.data_date = str(latest["date"].date()) if hasattr(latest["date"], "date") else str(latest["date"])

    # ── 最新行情 ──
    result.latest = {
        "close": round(float(latest["close"]), 2),
        "open": round(float(latest["open"]), 2),
        "high": round(float(latest["high"]), 2),
        "low": round(float(latest["low"]), 2),
        "volume": int(latest["volume"]),
        "amount": round(float(latest.get("amount", 0)), 2),
        "pct_chg": round(float(latest.get("pct_chg" if "pct_chg" in latest.index else "pctChg", (latest["close"] / prev["close"] - 1) * 100)), 2),
        "turnover_rate": round(float(latest["turnover"]) / 100, 4) if "turnover" in latest.index and pd.notna(latest["turnover"]) else None,
        "high_low_pct": round((float(latest["high"]) / float(latest["low"]) - 1) * 100, 2),
    }

    v = result.latest

    # ── 均线 ──
    for ma in ["MA5", "MA10", "MA20", "MA60", "MA120"]:
        if ma in df.columns and pd.notna(latest.get(ma)):
            val = float(latest[ma])
            dist = (v["close"] / val - 1) * 100
            result.ma[ma] = {"value": round(val, 2), "dist_pct": round(dist, 2)}

    # ── RSI ──
    if pd.notna(latest.get("RSI")):
        result.rsi = round(float(latest["RSI"]), 1)

    # ── MACD ──
    if pd.notna(latest.get("DIF")):
        result.macd = {
            "dif": round(float(latest["DIF"]), 3),
            "dea": round(float(latest["DEA"]), 3),
            "bar": round(float(latest["MACD_BAR"]), 3),
        }

    # ── 波动率 ──
    if pd.notna(latest.get("volatility")):
        result.volatility = round(float(latest["volatility"]), 4)

    # ── 换手率与量比 ──
    result.turnover_rate = v["turnover_rate"]
    if "vol_ma20" in df.columns and "vol_ma60" in df.columns:
        v20 = float(latest["vol_ma20"])
        v60 = float(latest["vol_ma60"])
        if v60 > 0:
            result.volume_ratio = round(v20 / v60, 2)

    # ── 年初至今 ──
    ytd = df[df["date"] >= f"{date.today().year}-01-01"]
    if len(ytd) > 1:
        result.ytd_return = round((float(ytd["close"].iloc[-1]) / float(ytd["close"].iloc[0]) - 1) * 100, 2)

    # ── 同业对比 ──
    result.sector_comparison = _sector_compare(ticker, df)

    # ── 多空清单 ──
    result.bull_factors, result.bear_factors = _bull_bear_factors(result, df)

    # ── 关键价位 + 情景 ──
    result.key_levels = _key_levels(result, df)
    result.scenarios = _scenarios(result, df)

    # ── 总结 ──
    result.summary = _summary(result)

    return result


def _sector_compare(ticker: str, df: pd.DataFrame) -> list:
    """同业横向对比 (通过 DataProvider 获取行业分类)"""
    from data.provider import DataProvider
    peers = []
    try:
        # 一次获取全市场行业映射
        all_industries = DataProvider.get_all_industries()
        if not all_industries:
            return []

        info = all_industries.get(ticker)
        if not info:
            logger.info(f"{ticker} 无行业信息")
            return []

        ticker_name, ticker_industry = info
        if not ticker_industry:
            return []

        # 同行业取 3 只 (排除自身)
        same_industry = [c for c, (n, ind) in all_industries.items()
                         if ind == ticker_industry and c != ticker][:3]

        # 本股近 20 日涨幅
        bs_df = fetch_daily(ticker, 30)
        this_ret = _recent_return(bs_df, 20)

        for pid in same_industry:
            p_df = fetch_daily(pid, 30)
            p_ret = _recent_return(p_df, 20)
            p_name = all_industries.get(pid, (pid, ""))[0]
            peers.append({
                "ticker": pid,
                "name": p_name,
                "recent_20d_ret": p_ret,
                "close": round(float(p_df["close"].iloc[-1]), 2) if not p_df.empty else None,
            })

        peers.sort(key=lambda x: x.get("recent_20d_ret", 0) or 0, reverse=True)

        result = [
            {"ticker": ticker, "name": ticker_name,
             "recent_20d_ret": this_ret, "is_self": True,
             "close": round(float(df["close"].iloc[-1]), 2) if not df.empty else None}
        ]
        result.extend(peers)
        return result

    except Exception as e:
        logger.warning(f"同业对比失败: {e}")
        return []


def _get_stock_name(ticker: str) -> str:
    """获取股票简称 (通过 DataProvider)"""
    from data.provider import DataProvider
    info = DataProvider.get_stock_basic_info(ticker)
    return info.get("name", ticker)


def _recent_return(df: pd.DataFrame, days: int = 20) -> Optional[float]:
    """最近 days 天的涨幅"""
    if df.empty or len(df) < 2:
        return None
    recent = df.tail(min(days, len(df)))
    ret = (float(recent["close"].iloc[-1]) / float(recent["close"].iloc[0]) - 1) * 100
    return round(ret, 2)


def _bull_bear_factors(result: StockAnalysis, df: pd.DataFrame) -> tuple[list, list]:
    """结构化多空因素"""
    bull = []
    bear = []
    v = result.latest
    c = float(v["close"])

    # ── 均线角度 ──
    ma20_val = result.ma.get("MA20", {}).get("value")
    ma60_val = result.ma.get("MA60", {}).get("value")
    if ma20_val and ma60_val and ma20_val > ma60_val:
        bull.append(f"MA20({ma20_val}) > MA60({ma60_val})，中期多头排列")
    elif ma20_val and ma60_val:
        bear.append(f"MA20({ma20_val}) < MA60({ma60_val})，中期空头排列")

    # ── 价格相对均线 ──
    for ma_name, label in [("MA5", "5日线"), ("MA10", "10日线"), ("MA20", "20日线")]:
        info = result.ma.get(ma_name)
        if info:
            dist = info["dist_pct"]
            if dist > 1:
                bear.append(f"价格高于{label} {dist:.1f}%，短线偏离较大")
            elif dist < -1:
                bear.append(f"价格跌破{label} {abs(dist):.1f}%，短线转弱")

    for ma_name, label in [("MA20", "20日线"), ("MA60", "60日线")]:
        info = result.ma.get(ma_name)
        if info and info["dist_pct"] > 0:
            bull.append(f"价格站稳{label}上方 (+{info['dist_pct']:.1f}%)")

    # ── RSI ──
    if result.rsi is not None:
        if result.rsi > 70:
            bear.append(f"RSI({result.rsi}) 进入超买区 (>70)，有回调压力")
        elif result.rsi < 30:
            bull.append(f"RSI({result.rsi}) 进入超卖区 (<30)，可能有反弹机会")
        elif result.rsi > 50:
            bull.append(f"RSI({result.rsi}) 处于强势区 (>50)")
        else:
            bear.append(f"RSI({result.rsi}) 处于弱势区 (<50)")

    # ── MACD ──
    macd = result.macd
    if macd:
        if macd.get("bar", 0) > 0:
            bull.append(f"MACD 红柱 ({macd['bar']})，动能向上")
        elif macd.get("bar", 0) < 0 and abs(macd.get("bar", 0)) > 0.5:
            bear.append(f"MACD 绿柱 ({macd['bar']})，动能向下")
        if macd.get("dif", 0) > macd.get("dea", 0):
            bull.append("DIF > DEA，MACD 金叉状态")
        else:
            bear.append("DIF < DEA，MACD 死叉状态")

    # ── 量能 ──
    vr = result.volume_ratio
    last_vol = v.get("volume", 0)
    avg_vol = df["volume"].tail(60).mean() if len(df) >= 60 else df["volume"].mean()
    if vr is not None:
        if vr > 1.5 and v.get("pct_chg", 0) < 0:
            bear.append(f"放量下跌 (量比 {vr})，抛压大")
        elif vr > 1.5 and v.get("pct_chg", 0) > 0:
            bull.append(f"放量上涨 (量比 {vr})，资金入场")
        elif vr < 0.6:
            bear.append(f"明显缩量 (量比 {vr})，市场关注度低")

    # ── 换手率 ──
    tr = result.turnover_rate
    if tr is not None:
        if tr > 0.10:
            bear.append(f"换手率 {tr:.1%}，筹码松动，短期分歧大")
        elif tr > 0.05:
            pass  # 活跃但正常
        elif tr < 0.01:
            bear.append(f"换手率仅 {tr:.2%}，交投冷清")

    # ── K 线形态 (近期 pattern) ──
    if len(df) >= 5:
        d1, d2, d3 = df.iloc[-1], df.iloc[-2], df.iloc[-3]
        c1, c2, c3 = float(d1["close"]), float(d2["close"]), float(d3["close"])
        o1, o2, o3 = float(d1["open"]), float(d2["open"]), float(d3["open"])
        h1, l1 = float(d1["high"]), float(d1["low"])

        # 涨停次日收阴
        if c2 and c3 and c2 / c3 > 1.095 and c1 < o1 and c1 < c2 * 0.98:
            bear.append("涨停次日收阴，追高意愿弱，获利盘出逃")
        # 长上影线
        if h1 - max(c1, o1) > (h1 - l1) * 0.6 and (h1 - l1) > 0:
            bear.append(f"长上影线 (上影 {(h1 - max(c1, o1)):.2f})，上方抛压重")
        # 连续上涨后放量滞涨
        if len(df) >= 5:
            last5 = df.tail(5)
            up_days = (last5["close"] > last5["close"].shift(1)).sum()
            if up_days >= 4 and vr and vr > 1.3 and c1 <= o1:
                bear.append("连续上涨后放量滞涨，可能短期见顶")

    # 去重、截断
    bull = _dedup(bull)[:5]
    bear = _dedup(bear)[:5]
    return bull, bear


def _key_levels(result: StockAnalysis, df: pd.DataFrame) -> dict:
    """关键支撑/阻力位"""
    c = float(result.latest["close"])
    levels = {}
    recent = df.tail(60)

    # 近期低点/高点
    recent_high = float(recent["high"].max())
    recent_low = float(recent["low"].min())

    levels["recent_high"] = round(recent_high, 2)
    levels["recent_low"] = round(recent_low, 2)

    # 均线位
    for ma_name in ["MA5", "MA10", "MA20", "MA60"]:
        info = result.ma.get(ma_name)
        if info:
            levels[f"support_{ma_name}"] = round(info["value"], 2)

    # 心理关口
    psychological = round(c / 10) * 10
    if psychological > 0:
        levels["psychological"] = psychological

    return levels


def _scenarios(result: StockAnalysis, df: pd.DataFrame) -> list:
    """情景推演"""
    c = float(result.latest["close"])
    levels = result.key_levels
    scenarios = []

    # 看多情景
    bull_triggers = []
    if "support_MA20" in levels:
        bull_triggers.append(f"守住 MA20 ({levels['support_MA20']})")
    if result.rsi is not None and result.rsi < 30:
        bull_triggers.append("RSI 超卖反弹")
    if bull_triggers:
        scenarios.append({
            "scenario": "看多",
            "condition": " 且 ".join(bull_triggers),
            "target": f"上看 {levels.get('recent_high', '前高')}",
            "probability": "中" if result.macd.get("dif", 0) > result.macd.get("dea", 0) else "低",
        })

    # 看空情景
    bear_triggers = []
    if "support_MA20" in levels:
        bear_triggers.append(f"跌破 MA20 ({levels['support_MA20']})")
    if result.rsi is not None and result.rsi > 70:
        bear_triggers.append("RSI 超买回调")
    if bear_triggers:
        scenarios.append({
            "scenario": "看空",
            "condition": " 或 ".join(bear_triggers),
            "target": f"下看 {levels.get('support_MA60', '前低')}",
            "probability": "高" if result.rsi is not None and result.rsi > 70 else "中",
        })

    # 震荡情景
    scenarios.append({
        "scenario": "震荡",
        "condition": f"在 {levels.get('recent_low', '支撑')} ~ {levels.get('recent_high', '阻力')} 区间整理",
        "target": f"区间操作，高抛低吸",
        "probability": "中",
    })

    return scenarios


def _summary(result: StockAnalysis) -> str:
    """生成总结"""
    v = result.latest
    parts = [f"{result.ticker} ({result.data_date}) 收盘 {v['close']}，涨幅 {v['pct_chg']:+.2f}%"]

    if result.ytd_return is not None:
        parts.append(f"年初至今 +{result.ytd_return}%" if result.ytd_return > 0 else f"年初至今 {result.ytd_return}%")

    if result.rsi is not None:
        rsi_note = "超买" if result.rsi > 70 else "超卖" if result.rsi < 30 else "中性"
        parts.append(f"RSI({result.rsi}) {rsi_note}")

    if result.volume_ratio is not None:
        vol_note = "放量" if result.volume_ratio > 1.2 else "缩量" if result.volume_ratio < 0.8 else "均量"
        parts.append(f"量比 {result.volume_ratio} ({vol_note})")

    if result.turnover_rate is not None:
        parts.append(f"换手 {result.turnover_rate:.1%}")

    if result.bull_factors and result.bear_factors:
        if len(result.bull_factors) > len(result.bear_factors) * 1.5:
            parts.append("偏多")
        elif len(result.bear_factors) > len(result.bull_factors) * 1.5:
            parts.append("偏空")
        else:
            parts.append("多空均衡")

    return " | ".join(parts)


def _dedup(items: list) -> list:
    """简单去重"""
    seen = set()
    out = []
    for item in items:
        key = item.split("，")[0] if "，" in item else item[:20]
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


# ── 格式化输出 ────────────────────────────────────────────────────

def format_text(analysis: StockAnalysis, verbose: bool = True) -> str:
    """格式化为可读文本"""
    lines = []
    v = analysis.latest

    lines.append(f"## {analysis.ticker} 分析报告 ({analysis.data_date})")
    lines.append("")
    lines.append(f"**收盘 {v['close']} | 涨跌幅 {v['pct_chg']:+.2f}% | 开盘 {v['open']} 最高 {v['high']} 最低 {v['low']}**")
    lines.append("")

    # 基础指标
    items = []
    if analysis.ytd_return is not None:
        items.append(f"年初至今: {analysis.ytd_return:+.2f}%")
    if analysis.volatility is not None:
        items.append(f"年化波动: {analysis.volatility:.2%}")
    if analysis.turnover_rate is not None:
        items.append(f"换手率: {analysis.turnover_rate:.2%}")
    if analysis.volume_ratio is not None:
        items.append(f"量比(20/60): {analysis.volume_ratio}")
    if analysis.rsi is not None:
        items.append(f"RSI: {analysis.rsi}")
    if items:
        lines.append(" | ".join(items))
        lines.append("")

    # 均线
    lines.append("**均线:**")
    for ma_name in ["MA5", "MA10", "MA20", "MA60"]:
        info = analysis.ma.get(ma_name)
        if info:
            arrow = "+" if info["dist_pct"] > 0 else "-"
            lines.append(f"  {ma_name}={info['value']}  {arrow} {info['dist_pct']:+.2f}%")
    lines.append("")

    # MACD
    if analysis.macd:
        m = analysis.macd
        bar_color = "红" if m["bar"] > 0 else "绿"
        lines.append(f"**MACD:** DIF {m['dif']}  DEA {m['dea']}  柱 {m['bar']} ({bar_color})")
        lines.append("")

    # 同业对比
    if analysis.sector_comparison:
        lines.append("**同业对比 (近20日):**")
        for peer in analysis.sector_comparison:
            ret = peer.get("recent_20d_ret")
            ret_str = f"{ret:+.2f}%" if ret is not None else "N/A"
            mark = "<- 本股" if peer.get("is_self") else ""
            lines.append(f"  {peer.get('name', peer['ticker']):8s} 收盘 {peer.get('close', 'N/A')}  近20日 {ret_str} {mark}")
        lines.append("")

    # 多空清单
    if verbose:
        if analysis.bull_factors:
            lines.append("**看涨因素:**")
            for i, f in enumerate(analysis.bull_factors, 1):
                lines.append(f"  [OK] {f}")
            lines.append("")
        if analysis.bear_factors:
            lines.append("**看跌因素:**")
            for i, f in enumerate(analysis.bear_factors, 1):
                lines.append(f"  [!] {f}")
            lines.append("")

    # 关键价位
    if analysis.key_levels:
        lines.append("**关键价位:**")
        k = analysis.key_levels
        c = v["close"]
        parts = []
        for label, key in [("MA5", "support_MA5"), ("MA10", "support_MA10"),
                            ("MA20", "support_MA20"), ("MA60", "support_MA60")]:
            if key in k:
                dist = (c / k[key] - 1) * 100
                parts.append(f"{label}({k[key]}, 距离 {dist:+.1f}%)")
        if "recent_high" in k:
            dist = (c / k["recent_high"] - 1) * 100
            parts.append(f"近期高点({k['recent_high']}, 距离 {dist:+.1f}%)")
        if "recent_low" in k:
            dist = (c / k["recent_low"] - 1) * 100
            parts.append(f"近期低点({k['recent_low']}, 距离 {dist:+.1f}%)")
        lines.append("  " + " | ".join(parts))
        lines.append("")

    # 情景
    if analysis.scenarios:
        lines.append("**情景推演:**")
        for s in analysis.scenarios:
            lines.append(f"  [{s['scenario']}]({s.get('probability', '?')}) {s['condition']} → {s['target']}")
        lines.append("")

    # 总结
    lines.append("---")
    lines.append(analysis.summary)
    lines.append("")

    return "\n".join(lines)


# ── CLI ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="个股多维分析")
    parser.add_argument("ticker", help="股票代码，如 603005")
    parser.add_argument("--days", type=int, default=365, help="回溯天数")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    result = analyze(args.ticker, args.days)
    if args.json:
        import json
        print(json.dumps(result, default=vars, ensure_ascii=False, indent=2))
    else:
        print(format_text(result))
