"""
因子评估脚本

用法：
    python -m scripts.evaluate_factors
    python -m scripts.evaluate_factors --universe csi300 --top-n 100

对 research.factors 表中的因子进行 IC/ICIR/分组收益 评估，
结果写入 research.factor_evaluation 表。
"""
import sys
import argparse
import time
from pathlib import Path
from datetime import date, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from loguru import logger

from data.provider import DataProvider
from data.storage import DataStorage
from research.evaluator import FactorEvaluator
from risk.decay_detector import DecayDetector


def evaluate_all_factors(tickers: list[str] = None,
                          target_date: date = None) -> dict:
    """评估全部因子的 IC/ICIR，含衰减检测"""
    storage = DataStorage()
    evaluator = FactorEvaluator()
    detector = DecayDetector()
    target_date = target_date or date.today()

    if tickers is None:
        try:
            tickers = DataProvider.get_csi300_components()
        except Exception:
            tickers = []

    # 获取因子列表
    factor_result = storage.conn.execute(
        "SELECT DISTINCT factor_name FROM research.factors"
    ).fetchall()
    all_factor_names = sorted([r[0] for r in factor_result])
    if not all_factor_names:
        logger.error("research.factors 表为空，请先运行 compute_factors")
        return {"error": "no_factors", "evaluated": 0}

    logger.info(f"评估 {len(all_factor_names)} 个因子, {len(tickers)} 只股票")

    # 收集所有股票的因子数据和收盘价
    factor_panel = {}   # factor_name -> {ticker: Series}
    close_panel = {}    # ticker -> Series

    for ticker in tickers:
        df = storage.load_stock_daily(ticker)
        if df.empty or "close" not in df.columns:
            continue
        close_panel[ticker] = df["close"]

        # 从DB加载因子
        try:
            factor_df = storage.conn.execute(
                "SELECT date, factor_name, factor_value FROM research.factors "
                "WHERE ticker = ? ORDER BY date",
                [ticker],
            ).fetchdf()
            if factor_df.empty:
                continue
            for fname in all_factor_names:
                sub = factor_df[factor_df["factor_name"] == fname]
                if sub.empty:
                    continue
                sub = sub.set_index("date")["factor_value"].sort_index()
                if len(sub) > 0:
                    if fname not in factor_panel:
                        factor_panel[fname] = {}
                    factor_panel[fname][ticker] = sub
        except Exception:
            continue

    # 对每个因子进行截面评估
    all_evaluations = {}
    decay_reports = {}

    for fname in all_factor_names:
        if fname not in factor_panel or len(factor_panel[fname]) == 0:
            logger.debug(f"  {fname}: 无数据, 跳过")
            continue

        # 计算时序 IC (每个股票内部)
        ic_all = pd.Series(dtype=float)
        for ticker, series in factor_panel[fname].items():
            cs = close_panel.get(ticker)
            if cs is None or len(cs) < 30:
                continue
            aligned = pd.concat([series, cs], axis=1, join="inner").dropna()
            if len(aligned) < 30:
                continue
            fwd_ret = aligned.iloc[:, 1].pct_change(5).shift(-5)
            valid = pd.DataFrame({"f": aligned.iloc[:, 0], "r": fwd_ret}).dropna()
            if len(valid) > 30:
                ic_val = valid["f"].corr(valid["r"], method="spearman")
                idx = aligned.index[min(len(valid), len(aligned)) - 1]
                ic_all[idx] = ic_val

        # IC 统计
        if len(ic_all) >= 10:
            ic_mean = ic_all.mean()
            ic_std = ic_all.std() + 1e-8
            icir = ic_mean / ic_std
            ic_pos = (ic_all > 0).mean()
            report = {
                "factor_name": fname,
                "ic": round(ic_mean, 6),
                "icir": round(icir, 4),
                "ic_std": round(ic_std, 6),
                "ic_positive_ratio": round(ic_pos, 4),
                "n_periods": len(ic_all),
            }
        else:
            report = {
                "factor_name": fname,
                "ic": None,
                "icir": None,
                "ic_std": None,
                "ic_positive_ratio": None,
                "n_periods": len(ic_all),
            }

        # 衰减检测
        if len(ic_all) >= 20:
            decay_report = detector.check(ic=ic_all)
            report["decay_alerts"] = [
                {
                    "level": a.level.value,
                    "metric": a.metric,
                    "message": a.message,
                }
                for a in decay_report.alerts
            ]
            report["is_decaying"] = decay_report.is_decaying
            decay_reports[fname] = decay_report

            if decay_report.is_decaying:
                logger.warning(
                    f"  {fname}: 衰减! ({decay_report.max_level.value})"
                )
        else:
            report["decay_alerts"] = []
            report["is_decaying"] = False

        all_evaluations[fname] = report

        ic_str = f"{report['ic']:+.4f}" if report['ic'] is not None else "N/A"
        icir_str = f"{report['icir']:+.2f}" if report['icir'] is not None else "N/A"
        decay_flag = " ⚠衰减" if report.get("is_decaying") else ""
        logger.info(f"  {fname}: IC={ic_str} ICIR={icir_str} "
                    f"({report['n_periods']}期){decay_flag}")

    # 保存到 DB
    try:
        eval_df = pd.DataFrame([
            {
                "factor_name": fname,
                "eval_date": target_date,
                "ic": r.get("ic"),
                "icir": r.get("icir"),
                "ic_std": r.get("ic_std"),
                "ic_positive_ratio": r.get("ic_positive_ratio"),
                "n_periods": r.get("n_periods"),
                "is_decaying": r.get("is_decaying", False),
            }
            for fname, r in all_evaluations.items()
        ])
        if not eval_df.empty:
            # 确保表存在
            storage.conn.execute("""
                CREATE TABLE IF NOT EXISTS research.factor_evaluation (
                    factor_name VARCHAR,
                    eval_date DATE,
                    ic DOUBLE,
                    icir DOUBLE,
                    ic_std DOUBLE,
                    ic_positive_ratio DOUBLE,
                    n_periods INTEGER,
                    is_decaying BOOLEAN
                )
            """)
            # 删除旧数据并写入
            storage.conn.execute(
                "DELETE FROM research.factor_evaluation WHERE eval_date = ?",
                [target_date],
            )
            storage.conn.register("eval_temp", eval_df)
            storage.conn.execute(
                "INSERT INTO research.factor_evaluation SELECT * FROM eval_temp"
            )
            logger.success(f"已保存 {len(eval_df)} 条评估结果到 research.factor_evaluation")
    except Exception as e:
        logger.warning(f"保存评估结果失败: {e}")

    # 汇总
    decaying_count = sum(1 for r in all_evaluations.values() if r.get("is_decaying"))
    valid_ic = [r["ic"] for r in all_evaluations.values() if r["ic"] is not None]

    logger.info(f"{'='*60}")
    logger.info(f"因子评估完成:")
    logger.info(f"  评估因子数: {len(all_evaluations)}")
    logger.info(f"  衰减因子数: {decaying_count}")
    if valid_ic:
        logger.info(f"  IC 均值: {np.mean(valid_ic):.4f}")
        logger.info(f"  IC 正值比例: {(np.array(valid_ic) > 0).mean():.0%}")
    logger.info(f"{'='*60}")

    return {"evaluated": len(all_evaluations), "decaying": decaying_count}


def main():
    parser = argparse.ArgumentParser(description="因子评估")
    parser.add_argument("--universe", default="csi300", help="股票池")
    parser.add_argument("--top-n", type=int, default=None, help="只评估前 N 只股票")
    parser.add_argument("--date", default=None, help="评估日期 (YYYY-MM-DD)")
    args = parser.parse_args()

    target_date = date.fromisoformat(args.date) if args.date else date.today()

    try:
        tickers = DataProvider.get_csi300_components()
        if args.top_n:
            tickers = tickers[:args.top_n]
        logger.info(f"股票池: {len(tickers)} 只")
    except Exception as e:
        logger.warning(f"获取成分股失败: {e}, 使用全部")
        tickers = None

    result = evaluate_all_factors(tickers, target_date)

    if "error" in result:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
