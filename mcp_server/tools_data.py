"""
MCP Data Tools — market data, quotes, history, factors, indices.
"""
from __future__ import annotations

import json
from datetime import date, timedelta

import pandas as pd

from data.storage import DataStorage
from research.factors import FactorEngine


def _resolve_ticker(ticker: str) -> str:
    """补齐6位股票代码（去掉 .SS/.SZ 后缀）"""
    t = ticker.strip().upper().replace(".SS", "").replace(".SZ", "")
    return t.zfill(6)


def _load_or_fetch(ticker: str, days: int = 365) -> pd.DataFrame:
    """先从 DB 加载，没有则自动从数据源拉取并保存。返回空 DataFrame 表示完全不可获取。"""
    storage = DataStorage()
    start = (date.today() - timedelta(days=days)).isoformat()
    df = storage.load_stock_daily(ticker, start_date=start)
    if not df.empty:
        return df
    # 自动从数据源拉取
    try:
        from data.provider import DataProvider
        from data.cleaner import DataCleaner
        df_new = DataProvider.get_stock_daily(ticker, start_date=start)
        if not df_new.empty:
            df_new = DataCleaner.clean_ohlcv(df_new)
            storage.save_stock_daily(ticker, df_new)
            return storage.load_stock_daily(ticker, start_date=start)
    except Exception:
        pass
    return pd.DataFrame()


def get_quote(ticker: str) -> str:
    """获取指定股票的最新行情数据（自动从数据源拉取）"""
    try:
        ticker = _resolve_ticker(ticker)
        df = _load_or_fetch(ticker, days=60)
        if df.empty:
            return json.dumps({"error": f"无数据: {ticker}"}, ensure_ascii=False)
        latest = df.iloc[-1]
        # compute pct_change on-the-fly
        closes = df["close"]
        pct = float((closes.iloc[-1] / closes.iloc[-2] - 1)) if len(closes) >= 2 else 0.0
        return json.dumps({
            "ticker": ticker,
            "date": str(latest.name.date()) if hasattr(latest.name, 'date') else str(latest.name),
            "close": float(latest.get("close", 0)),
            "open": float(latest.get("open", 0)),
            "high": float(latest.get("high", 0)),
            "low": float(latest.get("low", 0)),
            "volume": int(latest.get("volume", 0)),
            "pct_change": round(pct, 6),
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def get_history(ticker: str, days: int = 60) -> str:
    """获取股票历史行情数据（自动从数据源拉取）"""
    try:
        ticker = _resolve_ticker(ticker)
        df = _load_or_fetch(ticker, days=days)
        if df.empty:
            return json.dumps({"error": f"无数据: {ticker}"}, ensure_ascii=False)
        # compute pct_change on-the-fly
        pct_series = df["close"].pct_change()
        records = []
        for idx, row in df.iterrows():
            pct = pct_series.loc[idx]
            records.append({
                "date": str(idx.date()) if hasattr(idx, 'date') else str(idx),
                "close": float(row.get("close", 0)),
                "volume": int(row.get("volume", 0)),
                "pct_change": round(float(pct), 6) if pct is not None and not (isinstance(pct, float) and pct != pct) else 0.0,
            })
        return json.dumps({"ticker": ticker, "count": len(records), "data": records[-days:]},
                          ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def get_factors(ticker: str = "", factor_name: str = "") -> str:
    """获取已注册的因子列表或指定因子的数值"""
    try:
        fe = FactorEngine()
        all_factors = fe.list_factors()
        if not ticker:
            return json.dumps({
                "count": len(all_factors),
                "factors": [{"name": k, "description": v} for k, v in all_factors.items()],
            }, ensure_ascii=False)
        storage = DataStorage()
        df = storage.load_factors(ticker=ticker, factor_name=factor_name if factor_name else None)
        if df.empty:
            # Fallback: compute factors on-the-fly from stock daily data
            price_df = storage.load_stock_daily(ticker)
            if price_df.empty or "close" not in price_df.columns:
                return json.dumps({"error": f"无因子数据: {ticker}"}, ensure_ascii=False)
            df_factors = fe.compute_all(price_df)
            if factor_name:
                if factor_name not in df_factors.columns:
                    return json.dumps({"error": f"因子 {factor_name} 不存在"}, ensure_ascii=False)
                series = df_factors[factor_name].dropna()
                records = [{"date": str(k.date()) if hasattr(k, 'date') else str(k), "factor_name": factor_name, "value": round(float(v), 6)} for k, v in series.tail(20).items()]
            else:
                records = []
                for col in df_factors.columns:
                    if col in ("open", "high", "low", "close", "volume"):
                        continue
                    series = df_factors[col].dropna()
                    for k, v in series.tail(5).items():
                        records.append({"date": str(k.date()) if hasattr(k, 'date') else str(k), "factor_name": col, "value": round(float(v), 6)})
            return json.dumps({"ticker": ticker, "count": len(records), "data": records, "source": "computed_live"}, ensure_ascii=False)
        latest = df.iloc[-20:]
        records = []
        for _, row in latest.iterrows():
            records.append({
                "date": str(row.get("date", "")),
                "factor_name": str(row.get("factor_name", "")),
                "value": float(row.get("factor_value", 0)),
            })
        return json.dumps({"ticker": ticker, "count": len(records), "data": records},
                          ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def get_index_data(index_code: str = "000300", days: int = 30) -> str:
    """获取指数行情数据（默认沪深300）"""
    try:
        storage = DataStorage()
        start = (date.today() - timedelta(days=days)).isoformat()
        df = storage.load_index_daily(index_code, start_date=start)
        if df.empty:
            return json.dumps({"error": f"无数据: {index_code}"}, ensure_ascii=False)
        records = []
        for idx, row in df.iterrows():
            records.append({
                "date": str(idx.date()) if hasattr(idx, 'date') else str(idx),
                "close": float(row.get("close", 0)),
                "volume": int(row.get("volume", 0)),
            })
        return json.dumps({"index_code": index_code, "count": len(records), "data": records},
                          ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def get_universe() -> str:
    """获取系统跟踪的股票列表"""
    try:
        storage = DataStorage()
        df = storage.conn.execute(
            "SELECT DISTINCT ticker, COUNT(*) as days FROM stock_daily GROUP BY ticker ORDER BY days DESC"
        ).fetchdf()
        if df.empty:
            return json.dumps({"count": 0, "tickers": []}, ensure_ascii=False)
        tickers = []
        for _, row in df.iterrows():
            tickers.append({"ticker": row["ticker"], "days": int(row["days"])})
        return json.dumps({"count": len(tickers), "tickers": tickers}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def get_market_overview() -> str:
    """获取市场概况（指数最新数据 + 涨跌统计）"""
    try:
        storage = DataStorage()
        result = {"indices": {}}
        for code, name in [("000300", "沪深300"), ("000905", "中证500"), ("000688", "科创50")]:
            df = storage.load_index_daily(code)
            if not df.empty:
                latest = df.iloc[-1]
                prev = df.iloc[-2] if len(df) > 1 else None
                change = (float(latest.get("close", 0)) / float(prev.get("close", 1)) - 1) if prev is not None else 0
                result["indices"][name] = {
                    "close": float(latest.get("close", 0)),
                    "change": round(change, 4),
                }
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def search_tickers(query: str) -> str:
    """搜索股票代码或名称（支持中文名称模糊搜索）"""
    try:
        storage = DataStorage()
        # 1. 优先按代码搜索 DB
        df = storage.conn.execute(
            "SELECT DISTINCT ticker FROM stock_daily WHERE ticker LIKE ? LIMIT 20",
            [f"%{query}%"],
        ).fetchdf()
        tickers = [row["ticker"] for _, row in df.iterrows()]

        # 2. 如果代码匹配不足，尝试通过 AKShare spot 按名称搜索
        if len(tickers) < 3:
            try:
                from data.provider import HAS_AKSHARE, _no_proxy
                import akshare as ak
                if HAS_AKSHARE:
                    with _no_proxy():
                        spot_df = ak.stock_zh_a_spot_em()
                    if not spot_df.empty:
                        # 中文模糊匹配名称
                        name_col = "名称" if "名称" in spot_df.columns else (
                            spot_df.columns[1] if len(spot_df.columns) > 1 else None
                        )
                        code_col = "代码" if "代码" in spot_df.columns else (
                            spot_df.columns[0] if len(spot_df.columns) > 0 else None
                        )
                        if name_col and code_col:
                            query_lower = query.lower()
                            for _, row in spot_df.iterrows():
                                name = str(row.get(name_col, ""))
                                code = str(row.get(code_col, ""))
                                if query_lower in name.lower() or query_lower in code.lower():
                                    if code not in tickers:
                                        tickers.append(code)
                            tickers = tickers[:20]
            except Exception:
                pass  # AKShare 不可用时静默回退

        return json.dumps({"query": query, "count": len(tickers), "tickers": tickers},
                          ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def get_calendar(year: int = 0) -> str:
    """获取交易日历"""
    try:
        storage = DataStorage()
        import datetime
        y = year if year > 0 else date.today().year
        # Infer trading days from stock_daily data
        df = storage.conn.execute(
            "SELECT DISTINCT date FROM stock_daily WHERE strftime('%Y', date) = ? ORDER BY date",
            [str(y)],
        ).fetchdf()
        if df.empty:
            return json.dumps({"year": y, "count": 0, "trading_days": []}, ensure_ascii=False)
        days = [str(row["date"]) for _, row in df.iterrows()]
        return json.dumps({"year": y, "count": len(days), "trading_days": days}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def run_factor_evaluation(ticker: str = "600519", factor_name: str = "momentum_20d") -> str:
    """运行因子评估（IC/ICIR/分组收益）"""
    try:
        import math
        from research.factors import FactorEngine
        from research.evaluator import FactorEvaluator
        storage = DataStorage()
        df = storage.load_stock_daily(ticker)
        if df.empty or "close" not in df.columns:
            return json.dumps({"error": f"无数据: {ticker}"}, ensure_ascii=False)
        fe = FactorEngine()
        df_factors = fe.compute_all(df)
        if factor_name not in df_factors.columns:
            return json.dumps({"error": f"因子 {factor_name} 不存在"}, ensure_ascii=False)
        series = df_factors[factor_name].dropna()
        if len(series) < 20:
            return json.dumps({
                "ticker": ticker,
                "factor": factor_name,
                "warning": f"数据不足: 仅 {len(series)} 个有效观测值，至少需要 20 个",
                "ic": None,
                "icir": None,
                "overall_score": 0,
                "grade": "N/A",
            }, ensure_ascii=False)
        close = df["close"]
        report = FactorEvaluator.full_report(series, close)
        ic_val = report["ic"].get("ic")
        icir_val = report["ic"].get("icir")
        ic = round(float(ic_val), 6) if ic_val is not None and not math.isnan(float(ic_val)) else None
        icir = round(float(icir_val), 4) if icir_val is not None and not math.isnan(float(icir_val)) else None
        if ic is None and icir is None:
            return json.dumps({
                "ticker": ticker,
                "factor": factor_name,
                "warning": "因子数据不足以计算有效的 IC/ICIR",
                "ic": None,
                "icir": None,
                "overall_score": report["overall_score"],
                "grade": report["grade"],
            }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def update_data(universe: str = "csi300", start_date: str = "") -> str:
    """更新行情数据。注意：此操作会从数据源拉取数据并写入数据库，耗时 15-30 分钟。"""
    from scripts.update_data import update_data as _update_data
    import io
    from contextlib import redirect_stdout

    start = start_date or "20200101"
    buf = io.StringIO()
    with redirect_stdout(buf):
        try:
            _update_data(universe=universe, start_date=start)
            success = True
        except Exception as e:
            success = False
            error = str(e)
    stdout = buf.getvalue()
    return json.dumps({
        "success": success,
        "message": "数据更新完成" if success else f"数据更新失败: {error}",
        "stdout": stdout[:2000],
    }, ensure_ascii=False)


# ============================================================
# 行业 / 概念板块工具 (P1)
# ============================================================

def get_sector_list(sector_type: str = "concept") -> str:
    """
    获取行业板块或概念板块列表

    Args:
        sector_type: "industry" (申万行业) 或 "concept" (概念板块，默认)
    """
    try:
        from data.sectors import SectorData
        if sector_type == "industry":
            boards = SectorData.get_industry_list()
        else:
            boards = SectorData.get_concept_list()
        return json.dumps({
            "sector_type": sector_type,
            "count": len(boards),
            "boards": boards,
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def get_sector_stocks(sector_name: str, sector_type: str = "concept") -> str:
    """
    获取指定板块的成分股列表

    Args:
        sector_name: 板块名称，如 "半导体"、"AI芯片"
        sector_type: "industry" 或 "concept"（默认）

    Example:
        get_sector_stocks("半导体") → 返回半导体概念板块的成分股
    """
    try:
        from data.sectors import SectorData
        stocks = SectorData.get_board_stocks(sector_name, sector_type)
        if not stocks:
            # 尝试搜索匹配
            matches = SectorData.search_board(sector_name, sector_type)
            if matches:
                first_match = matches[0]["name"]
                stocks = SectorData.get_board_stocks(first_match, sector_type)
                return json.dumps({
                    "sector_name": first_match,
                    "sector_type": sector_type,
                    "count": len(stocks),
                    "stocks": stocks,
                    "note": f"精确匹配失败，使用最接近的板块: {first_match}",
                }, ensure_ascii=False)
            return json.dumps({
                "sector_name": sector_name,
                "sector_type": sector_type,
                "count": 0,
                "stocks": [],
                "error": f"未找到板块 '{sector_name}'",
            }, ensure_ascii=False)
        return json.dumps({
            "sector_name": sector_name,
            "sector_type": sector_type,
            "count": len(stocks),
            "stocks": stocks,
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def get_sector_index(sector_name: str, sector_type: str = "concept", days: int = 60) -> str:
    """
    构建并返回板块等权指数日线数据

    从成分股日线数据构建等权平均指数，含 open/high/low/close/volume/pct_change。

    Args:
        sector_name: 板块名称，如 "半导体"
        sector_type: "industry" 或 "concept"（默认）
        days: 返回最近多少天的数据

    Note: 首次调用需从数据源拉取所有成分股日线，耗时较长（30s-2min）
    """
    try:
        import datetime
        from data.sectors import SectorData
        start = (datetime.date.today() - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
        df = SectorData.build_board_index(sector_name, sector_type, start_date=start)
        if df.empty:
            return json.dumps({
                "sector_name": sector_name,
                "sector_type": sector_type,
                "count": 0,
                "data": [],
                "error": "无法构建板块指数，可能是数据源不可用或无成分股数据",
            }, ensure_ascii=False)
        records = []
        for idx, row in df.tail(days).iterrows():
            records.append({
                "date": str(idx.date()) if hasattr(idx, 'date') else str(idx),
                "close": round(float(row.get("close", 0)), 2),
                "open": round(float(row.get("open", 0)), 2) if row.get("open") else None,
                "high": round(float(row.get("high", 0)), 2) if row.get("high") else None,
                "low": round(float(row.get("low", 0)), 2) if row.get("low") else None,
                "volume": int(row.get("volume", 0)),
                "pct_change": round(float(row.get("pct_change", 0)), 4) if pd.notna(row.get("pct_change")) else 0.0,
                "stock_count": int(row.get("stock_count", 0)),
            })
        return json.dumps({
            "sector_name": sector_name,
            "sector_type": sector_type,
            "count": len(records),
            "data": records,
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def run_daily_research(target_date: str = "") -> str:
    """运行每日研究流程。注意：此操作会更新数据、计算因子、采集新闻、生成日报，耗时 5-15 分钟。"""
    from scripts.daily_research import run_daily_research as _run_dr
    from datetime import date
    import io
    from contextlib import redirect_stdout

    target = date.fromisoformat(target_date) if target_date else date.today()
    buf = io.StringIO()
    with redirect_stdout(buf):
        try:
            _run_dr(target_date=target, use_llm=False)
            success = True
        except Exception as e:
            success = False
            error = str(e)
    stdout = buf.getvalue()
    return json.dumps({
        "success": success,
        "message": "每日研究流程完成" if success else f"运行失败: {error}",
        "stdout": stdout[:2000],
    }, ensure_ascii=False)
