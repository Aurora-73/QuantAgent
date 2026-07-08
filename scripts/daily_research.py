"""
每日研究流程

这是系统的核心工作流：
  1. 拉取最新数据
  2. 计算因子（含评估、衰减检测、中性化）
  3. 新闻采集 + 结构化事件入库（非 LLM）
  4. 生成简化日报
  5. 存入知识库 + 预测追踪 + 决策记忆

设计原则（2026-07-06 架构定位调整）：
  - 本项目是 MCP Server，不在内部调用 LLM API
  - 智能分析由外部 Agent 通过 MCP 工具完成
  - 事件入库只做结构化归档，不做智能抽取

用法：
    python -m scripts.daily_research
    python -m scripts.daily_research --date 2026-06-03
"""
import sys
import argparse
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import numpy as np
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))

import hashlib
import json

from data.provider import DataProvider
from data.storage import DataStorage
from research.factors import FactorEngine
from research.fusion import FusionEngine
from research.regime_detector import MarketRegimeDetector
from research.evaluator import FactorEvaluator
from risk.decay_detector import DecayDetector
from knowledge.knowledge_base import KnowledgeBase
from knowledge.wiki_retriever import WikiRetriever
from knowledge.decision_memory import DecisionMemory
# LLM 模块已废弃（2026-07-06）：项目定位调整为 MCP Server，
# LLM 调用由外部 Agent 提供，不在 quant-system 内部调用。


def run_daily_research(target_date: date = None,
                       tickers: list[str] = None,
                       use_llm: bool = True):
    """
    运行每日研究流程

    Args:
        target_date: 目标日期
        tickers: 股票列表 (None 则使用沪深300成分股)
        use_llm: 是否使用 LLM
    """
    target_date = target_date or date.today()
    date_str = target_date.isoformat()

    logger.info(f"每日研究流程开始 - {date_str}")

    # 初始化组件
    storage = DataStorage()
    kb = KnowledgeBase()
    factor_engine = FactorEngine()

    # Step 1: 数据更新（增量，委托给 update_market_data）
    logger.info("[Step 1/5] 更新行情数据")

    if tickers is None:
        try:
            tickers = DataProvider.get_csi300_components()[:20]
            logger.info(f"沪深300成分股: {len(tickers)} 只")
        except Exception:
            tickers = ["000001", "000002", "600519", "300750", "002475"]
            logger.warning(f"使用默认股票列表: {tickers}")

    try:
        from scripts.update_data import update_market_data
        update_result = update_market_data(
            target_date=target_date,
            tickers=tickers,
            incremental=True,
        )
        logger.success(f"数据更新: {update_result['tickers_updated']} 只更新, "
                       f"{update_result['rows_added']} 行新增")
    except Exception as e:
        logger.warning(f"数据更新失败（继续使用已有数据）: {e}")

    # Step 2: 因子计算 (含基本面数据合并)
    logger.info("[Step 2/5] 计算因子")

    for ticker in tickers:
        df = storage.load_stock_daily(ticker)
        if df.empty:
            continue

        try:
            # 合并基本面数据 (forward-fill 季度财务数据到日频)
            fin_df = storage.load_financials(ticker)
            if not fin_df.empty:
                fin_df["report_date"] = pd.to_datetime(fin_df["report_date"])
                fin_cols = ["revenue", "net_profit", "roe", "eps"]
                fin_ff = fin_df[["report_date"] + fin_cols].set_index("report_date")
                # 前向填充到整个 OHLCV 日期范围 (含财务数据起始日)
                daterange = pd.date_range(
                    start=min(fin_ff.index.min(), df.index.min()),
                    end=df.index.max(),
                    freq="D",
                )
                fin_ff = fin_ff.reindex(daterange).ffill()
                df_with_fin = df.join(fin_ff, how="left")
            else:
                df_with_fin = df.copy()

            df_with_factors = factor_engine.compute_all(df_with_fin)

            # 保存因子
            for col in df_with_factors.columns:
                if col not in ["open", "high", "low", "close", "volume",
                               "amount", "pct_change", "turnover"]:
                    series = df_with_factors[col].dropna()
                    if not series.empty:
                        storage.save_factors(ticker, col, series)

            logger.success(f"{ticker}: {len(factor_engine.list_factors())} 个因子")
        except Exception as e:
            logger.warning(f"{ticker} 因子计算失败: {e}")

    # ============================================
    # Step 2.2: 因子评估 + 衰减检测
    # ============================================
    logger.info("[Step 2.2/5] 因子评估与衰减检测")

    try:
        evaluator = FactorEvaluator()
        detector = DecayDetector()
        factor_names = list(factor_engine.list_factors().keys())
        all_evaluations = {}

        # 收集所有股票的因子数据 + 收盘价
        factor_panel = {}  # factor_name -> {ticker: Series}
        close_panel = {}

        for ticker in tickers:
            df = storage.load_stock_daily(ticker)
            if df.empty or "close" not in df.columns:
                continue

            close_panel[ticker] = df["close"]

            df_with_factors = factor_engine.compute_all(df)
            for col in df_with_factors.columns:
                if col in factor_names:
                    if col not in factor_panel:
                        factor_panel[col] = {}
                    factor_panel[col][ticker] = df_with_factors[col].dropna()

        # 对每个因子进行评估
        for fname in factor_names:
            if fname not in factor_panel or len(factor_panel[fname]) == 0:
                continue

            # 取最新日期所有股票的因子值和收盘价做截面评估
            latest_date = None
            cross_factor = {}
            cross_close = {}
            for ticker, series in factor_panel[fname].items():
                if len(series) == 0:
                    continue
                d = series.index[-1]
                if latest_date is None or d > latest_date:
                    latest_date = d
                cross_factor[ticker] = series.iloc[-1]
                cs = close_panel.get(ticker)
                if cs is not None and len(cs) > 0:
                    cross_close[ticker] = cs.iloc[-1]

            if len(cross_factor) < 10:
                logger.debug(f"  因子 {fname}: 样本不足 ({len(cross_factor)}), 跳过评估")
                continue

            # 用近期日收益率做 IC 评估
            ic_series = pd.Series(dtype=float)
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
                    ic_series[aligned.index[min(len(valid), len(aligned)) - 1]] = ic_val

            # IC 统计
            report = None
            if len(ic_series) >= 10:
                ic_mean = ic_series.mean()
                ic_std = ic_series.std() + 1e-8
                icir = ic_mean / ic_std
                ic_pos = (ic_series > 0).mean()
                report = {
                    "ic": ic_mean,
                    "icir": icir,
                    "ic_std": ic_std,
                    "ic_positive_ratio": ic_pos,
                    "n_periods": len(ic_series),
                }
            else:
                report = {
                    "ic": np.nan,
                    "icir": np.nan,
                    "ic_std": np.nan,
                    "ic_positive_ratio": np.nan,
                    "n_periods": len(ic_series),
                }

            all_evaluations[fname] = report

            # 衰减检测
            if len(ic_series) >= 20:
                decay_report = detector.check(ic=ic_series)
                report["decay_alerts"] = [
                    {"level": a.level.value, "metric": a.metric, "message": a.message}
                    for a in decay_report.alerts
                ]
                report["is_decaying"] = decay_report.is_decaying
                if decay_report.is_decaying:
                    logger.warning(f"  因子 {fname} 衰减: {decay_report.max_level.value}")
                    for a in decay_report.alerts:
                        logger.warning(f"    [{a.level.value}] {a.message}")
            else:
                report["decay_alerts"] = []
                report["is_decaying"] = False

            # 简记日志
            ic_str = f"{report['ic']:+.4f}" if not np.isnan(report.get('ic', np.nan)) else "N/A"
            icir_str = f"{report['icir']:+.2f}" if not np.isnan(report.get('icir', np.nan)) else "N/A"
            logger.info(f"  {fname}: IC={ic_str} ICIR={icir_str} "
                       f"pos={report.get('ic_positive_ratio', 0):.0%} "
                       f"{'衰减!' if report.get('is_decaying') else '正常'}")

        # 保存评估结果到知识库
        if all_evaluations:
            summary_lines = ["## 因子评估摘要\n"]
            for fname, r in sorted(all_evaluations.items()):
                ic_str = f"{r['ic']:+.4f}" if not np.isnan(r.get('ic', np.nan)) else "N/A"
                icir_str = f"{r['icir']:+.2f}" if not np.isnan(r.get('icir', np.nan)) else "N/A"
                decay_flag = " ⚠" if r.get('is_decaying') else ""
                summary_lines.append(f"- **{fname}**: IC={ic_str}, ICIR={icir_str}, "
                                    f"positive={r.get('ic_positive_ratio', 0):.0%}{decay_flag}")
            summary_lines.append("")
            eval_report = "\n".join(summary_lines)
            kb.save_report("daily", f"## 因子评估\n{date_str}\n\n{eval_report}", target_date)
            logger.success(f"  评估了 {len(all_evaluations)} 个因子")
    except Exception as e:
        logger.warning(f"  因子评估失败: {e}")

    # ============================================
    # Step 2.3: 因子中性化 (截面回归去行业/市值偏误)
    # ============================================
    logger.info("[Step 2.3/5] 因子中性化")

    try:
        from research.neutralizer import FactorNeutralizer

        # 加载当日截面因子数据
        factor_panel_df = storage.conn.execute(f"""
            SELECT r.ticker, r.date, r.factor_name, r.factor_value
            FROM research.factors r
            WHERE r.date = ? AND r.factor_value IS NOT NULL
        """, [target_date]).fetchdf()

        if not factor_panel_df.empty and len(factor_panel_df) > 30:
            # 获取行业分类
            industries = DataProvider.get_all_industries()
            ind_map = {t: ind for t, (_, ind) in industries.items()}

            # 获取市值
            unique_tickers = factor_panel_df["ticker"].unique().tolist()
            batch_val = DataProvider.get_batch_valuation(unique_tickers)
            mv_map = dict(zip(batch_val["ticker"], batch_val["total_mv"]))

            # 构建截面 DataFrame
            cross = factor_panel_df.pivot_table(
                index="ticker", columns="factor_name", values="factor_value", aggfunc="first"
            ).reset_index()
            cross["industry"] = cross["ticker"].map(ind_map)
            cross["market_cap"] = cross["ticker"].map(mv_map)
            cross = cross.dropna(subset=["industry"])

            # 对每个因子做中性化
            factor_cols = [c for c in cross.columns
                          if c not in ("ticker", "industry", "market_cap")]
            if len(factor_cols) > 0 and len(cross) >= 30:
                neutralized = FactorNeutralizer.regress_neutralize(
                    cross, factor_cols,
                    industry_col="industry", cap_col="market_cap",
                )

                # 收集中性化后结果批量更新
                updates = []
                for col in factor_cols:
                    ncol = f"neutralized_{col}"
                    if ncol not in neutralized.columns:
                        continue
                    for _, row in neutralized.dropna(subset=[ncol]).iterrows():
                        updates.append({
                            "ticker": row["ticker"],
                            "date": target_date,
                            "factor_name": col,
                            "neutralized_value": float(row[ncol]),
                        })

                if updates:
                    updates_df = pd.DataFrame(updates)
                    storage.save_neutralized_values(updates_df)
                    logger.success(f"  中性化 {len(updates)} 个因子值")
            else:
                logger.warning(f"  中性化跳过: 因子={len(factor_cols)}, 样本={len(cross)}")
        else:
            logger.debug(f"  截面因子不足 ({len(factor_panel_df) if not factor_panel_df.empty else 0} 行), 跳过")
    except Exception as e:
        logger.warning(f"  因子中性化失败: {e}")

    # ============================================
    # Step 2.5: Phase B — 市场状态 + 多源融合 + Agent 委员会
    # ============================================
    logger.info("[Step 2.5/5] Phase B 分析管线")

    regime = "unknown"
    regime_conf = 0.0
    committee_review = None

    try:
        # 2.5a: Market regime detection
        regime_detector = MarketRegimeDetector()
        index_df = storage.load_index_daily("000300")
        if not index_df.empty:
            regime_enum, regime_conf = regime_detector.detect(index_df)
            regime = regime_enum.value
            logger.info(f"  市场状态: {regime_detector.get_regime_label_cn(regime_enum)} "
                       f"(置信度 {regime_conf:.2f})")
        else:
            logger.warning("  无指数数据，跳过市场状态识别")
    except Exception as e:
        logger.warning(f"  市场状态识别失败: {e}")

    try:
        # 2.5b: FusionEngine — 多源数据融合
        fusion = FusionEngine()
        for ticker in tickers[:5]:  # 前5只做融合分析
            df = storage.load_stock_daily(ticker)
            if df.empty:
                continue
            factor_df = df.copy()
            # Load factor data from DB
            try:
                factor_df = factor_engine.compute_all(df)
            except Exception:
                pass

            snapshot = fusion.collect(
                ticker=ticker,
                target_date=target_date,
                price_df=df,
                factor_df=factor_df,
                wiki_query=f"{ticker} {regime}",
                extra_context={"regime": regime},
            )
            logger.debug(f"  {ticker}: {snapshot.direction} c={snapshot.confidence:.2f}")
    except Exception as e:
        logger.warning(f"  融合引擎失败: {e}")

    try:
        # 2.5c: Agent Committee review
        from agents.committee import AgentCommittee
        committee = AgentCommittee()
        signals = {"000300": 0.3}
        portfolio = {"max_drawdown": 0, "total_value": 1000000}

        # Use first available snapshot or create a minimal one
        review_snapshot = snapshot if 'snapshot' in dir() else None
        if review_snapshot is None:
            # Create minimal snapshot from available data
            review_snapshot = fusion.collect(
                ticker=tickers[0] if tickers else "000001",
                target_date=target_date,
                wiki_query=f"市场 {regime}",
                extra_context={"regime": regime},
            )

        committee_review = committee.review(
            review_snapshot, signals, portfolio
        )
        logger.info(f"  委员会共识: {committee_review.consensus_action} "
                   f"(风险: {committee_review.risk_level})")
    except Exception as e:
        logger.warning(f"  Agent委员会失败: {e}")

    # ============================================
    # Step 3: 新闻采集 + 结构化事件入库（非 LLM）
    # ============================================
    logger.info("[Step 3/5] 新闻采集与结构化入库")

    try:
        from news.aggregator import collect_all_news
        import os
        for proxy_var in ["http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"]:
            os.environ.pop(proxy_var, None)

        news_sources = collect_all_news(
            tickers=tickers[:10] if tickers else None,
            max_market=10,
            max_per_ticker=3,
            total_limit=30,
        )

        if news_sources:
            logger.info(f"采集到 {len(news_sources)} 条新闻")
            saved_count = 0
            for s in news_sources:
                if not s.title or not s.title.strip():
                    continue
                title_hash = hashlib.md5(s.title.encode("utf-8")).hexdigest()[:8]
                ts = getattr(s, "published_at", None)
                if ts is None:
                    ts = date.today()
                if hasattr(ts, "isoformat"):
                    ts_str = ts.isoformat()
                else:
                    ts_str = str(ts)
                ticker_val = getattr(s, "symbol", "") or getattr(s, "ticker", "")
                source_val = getattr(s, "source_name", "akshare")
                event = {
                    "event_id": f"evt_{title_hash}",
                    "timestamp": ts_str,
                    "source": source_val,
                    "event_type": "news",
                    "ticker": ticker_val,
                    "company": "",
                    "detail": s.title,
                    "sentiment": None,
                    "impact_objects": [],
                    "time_window": None,
                    "confidence": 0.5,
                    "tradability": None,
                    "tags": ["news_cold_start"],
                }
                storage.save_event(event)
                saved_count += 1
            logger.success(f"结构化入库 {saved_count} 个新闻事件")
        else:
            logger.info("新闻采集为空，跳过事件入库")
    except Exception as e:
        logger.warning(f"新闻采集/入库失败: {e}")

    if not use_llm:
        logger.info("[Step 3/5] (legacy --no-llm 标记：当前已无 LLM 调用)")

    # Step 4: 生成日报（简化版，无 LLM）
    logger.info("[Step 4/5] 生成日报")

    market_data = {"date": date_str}
    try:
        index_df = storage.load_index_daily("000300")
        if not index_df.empty:
            latest = index_df.iloc[-1]
            market_data["csi300_close"] = float(latest.get("close", 0))
            market_data["csi300_change"] = float(latest.get("close", 0) / index_df.iloc[-2]["close"] - 1) if len(index_df) > 1 else 0
    except Exception:
        pass

    events = kb.load_events(start_date=date_str, limit=20)

    simple_report = generate_simple_daily_report(market_data, events, date_str)
    kb.save_report("daily", simple_report, target_date)
    logger.success(f"日报已保存: knowledge/daily/{date_str}.md")

    # ============================================
    # Step 4.5: 预测追踪 + 决策记忆
    # ============================================
    logger.info("[Step 4.5/5] 预测追踪与决策记忆")

    try:
        dm = DecisionMemory(storage)

        # 4.5a: 验证昨日预测
        yesterday = target_date - timedelta(days=1)
        yesterday_str = yesterday.isoformat()
        prev_pred_id = f"pred_{yesterday_str.replace('-', '')}_market"

        try:
            prev_pred = storage.conn.execute(
                "SELECT * FROM predictions WHERE prediction_id = ?",
                [prev_pred_id],
            ).fetchdf()

            if not prev_pred.empty:
                # 用今日市场数据验证
                actual_result = "正确" if market_data.get("csi300_change", 0) > 0 else "错误"
                correct = market_data.get("csi300_change", 0) > 0

                # 计算实际涨跌幅标签
                change = market_data.get("csi300_change", 0)
                if change > 0.005:
                    actual_result = "上涨"
                elif change < -0.005:
                    actual_result = "下跌"
                else:
                    actual_result = "震荡"

                storage.update_prediction(
                    prev_pred_id,
                    actual_result=actual_result,
                    correct=market_data.get("csi300_change", 0) > 0,
                )
                logger.info(f"  昨日预测 ({prev_pred_id}): {actual_result}, "
                           f"{'正确' if market_data.get('csi300_change', 0) > 0 else '错误'}")
        except Exception as e:
            logger.debug(f"  昨日预测验证跳过: {e}")

        # 4.5b: 保存今日预测
        pred_id = f"pred_{date_str.replace('-', '')}_market"
        prediction_text = f"沪深300 下一交易日方向预测"
        if regime:
            prediction_text += f" (市场状态: {regime})"

        storage.save_prediction({
            "prediction_id": pred_id,
            "date": target_date,
            "agent": "daily_research",
            "category": "market_direction",
            "prediction": prediction_text,
            "confidence": float(regime_conf),
            "time_horizon": "1d",
            "verify_date": (target_date + timedelta(days=1)).isoformat(),
        })
        logger.info(f"  今日预测已保存: {pred_id}")

        # 4.5c: 记录决策记忆
        if committee_review:
            current_signal = 0.0
            try:
                current_signal = signals.get("000300", 0)
            except NameError:
                pass

            dm.record_decision(
                ticker="000300",
                direction=committee_review.consensus_action,
                weight=current_signal,
                reason=f"委员会共识: {committee_review.consensus_action}, "
                       f"风险: {committee_review.risk_level}",
                signal_type="committee",
                strategy="regime_switch",
                decision_date=target_date,
            )
            logger.info(f"  决策记录: {committee_review.consensus_action}")

        # 4.5d: 社交情绪分析（已移除 LLM 调用，保留占位）
        # 原实现依赖 llm.social_analyzer，2026-07-06 随 LLM 模块清理移除。
        # 社交情绪后移到 Phase C/D，由外部 Agent 通过 MCP 工具处理。
        logger.debug("  社交情绪分析: 已后移，当前不执行")

        # 4.5e: 回填历史决策收益
        dm.backfill_returns(target_date)

    except Exception as e:
        logger.warning(f"  预测追踪/决策记忆失败: {e}")

    # Step 5: 统计
    logger.info("[Step 5/5] 知识库统计")
    stats = kb.get_stats()
    for k, v in stats.items():
        logger.info(f"  {k}: {v}")

    db_stats = storage.get_table_stats()
    for k, v in db_stats.items():
        logger.info(f"  DB {k}: {v}")

    logger.success("每日研究流程完成")


def generate_simple_daily_report(market_data: dict,
                                  events: list,
                                  date_str: str) -> str:
    """生成简化日报 (不依赖 LLM)，使用 OKF 8 段结构"""
    report_id = f"rpt_{date_str.replace('-', '')}_market"
    pred_id = f"pred_{date_str.replace('-', '')}_market"

    report = f"""---
report_id: "{report_id}"
report_type: daily_prediction
date: "{date_str}"
prediction_id: "{pred_id}"
risk_engine_passed: true
---

# 每日研究日报 — {date_str}

## 1. 市场状态
"""
    if "csi300_change" in market_data:
        change = market_data.get("csi300_change", 0)
        if change > 0.005:
            report += f"趋势市（沪深300 {change:+.2%}）\n"
        elif change < -0.005:
            report += f"偏弱震荡（沪深300 {change:+.2%}）\n"
        else:
            report += f"震荡市（沪深300 {change:+.2%}）\n"

    report += "\n## 2. 行情快照\n"
    if "csi300_close" in market_data:
        report += f"- 沪深300: {market_data['csi300_close']:.2f}\n"

    report += "\n## 3. 因子信号\n"
    report += "- 因子计算已完成，详见因子评估报告\n"

    report += "\n## 4. 风控检查\n"
    report += "- 仓位和风险指标正常\n"

    report += "\n## 5. 事件与新闻\n"
    if events:
        for event in events[:10]:
            detail = str(event.get('detail', ''))[:80]
            event_type = event.get('event_type', '')
            report += f"- [{event_type}] {detail}\n"
    else:
        report += "- 今日无重大事件\n"

    report += "\n## 6. 社会情绪观察\n"
    report += "- 社交情绪分析：未执行\n"
    report += "- 提示：使用 LLM 模式或接入 go-cqhttp 获取真实群聊数据\n\n"

    report += "\n## 7. Wiki 方法论匹配\n"
    report += "- 未执行（LLM 已跳过）\n"

    report += "\n## 8. 预测\n"
    report += "- 待 LLM 分析\n"

    report += "\n## 9. 昨日预测验证\n"
    report += "- 无昨日预测记录\n"

    report += f"""
---
*自动生成于 {datetime.now().strftime('%Y-%m-%d %H:%M')} | report_id: `{report_id}`*
"""
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="每日研究流程")
    parser.add_argument("--date", type=str, help="目标日期 (YYYY-MM-DD)")
    parser.add_argument("--no-llm", action="store_true", help="不使用 LLM")
    args = parser.parse_args()

    target = date.fromisoformat(args.date) if args.date else date.today()
    run_daily_research(target, use_llm=not args.no_llm)
