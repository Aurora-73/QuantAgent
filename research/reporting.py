"""
高阶报告生成 — 周报/月报/季报。

从 decision_memory、factors、events、backtest_runs 聚合数据，
生成跨时间尺度的分析报告，通过 KnowledgeBase.save_report() 落地。

复用现有 KnowledgeBase 报告目录（weekly/monthly/quarterly/），
不另起存储语义。
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
from loguru import logger

from data.storage import DataStorage
from data.trading_calendar import TradingCalendar
from knowledge.knowledge_base import KnowledgeBase
from knowledge.decision_memory import DecisionMemory


def _safe_pct(val, digits=2) -> str:
    """安全格式化百分比"""
    if val is None or pd.isna(val):
        return "N/A"
    return f"{float(val):.{digits}%}"


def _safe_float(val, digits=2) -> str:
    """安全格式化浮点数"""
    if val is None or pd.isna(val):
        return "N/A"
    return f"{float(val):.{digits}f}"


def _get_trading_day_range(cal: TradingCalendar, end_date: date, n_days: int) -> list[date]:
    """获取 end_date 前 n_days 个交易日（含 end_date）"""
    start = cal.last_trading_day(end_date)
    if start is None:
        start = end_date - timedelta(days=n_days * 2)
    # 往前推足够的自然日以确保覆盖 n_days 个交易日
    search_start = start - timedelta(days=n_days * 2)
    days = cal.trading_days_between(search_start, end_date)
    return days[-n_days:] if len(days) >= n_days else days


def generate_weekly_report(target_date: date = None,
                           storage: DataStorage = None,
                           cal: TradingCalendar = None) -> str:
    """
    生成周报内容（最近 5 个交易日）。

    Returns:
        Markdown 格式的周报内容
    """
    target_date = target_date or date.today()
    storage = storage or DataStorage()
    cal = cal or TradingCalendar(storage=storage)

    trading_days = _get_trading_day_range(cal, target_date, 5)
    if not trading_days:
        return f"# 周报 {target_date}\n\n> 无交易日数据"

    start_date = trading_days[0]
    lines = [
        f"# 周报 {start_date.isoformat()} ~ {target_date.isoformat()}",
        f"\n> 生成时间: {date.today().isoformat()}",
        f"> 覆盖交易日: {len(trading_days)} 天\n",
    ]

    # 1. 数据新鲜度
    lines.append("## 数据新鲜度\n")
    for table in ["stock_daily", "index_daily", "factors"]:
        try:
            info = storage.get_freshness(table)
            lines.append(f"- **{table}**: {info['last_date']} ({info['status']})")
        except Exception:
            lines.append(f"- **{table}**: 检查失败")
    lines.append("")

    # 2. 决策准确率
    lines.append("## 决策准确率\n")
    try:
        dm = DecisionMemory(storage)
        accuracy = dm.get_accuracy(days=7)
        if accuracy and accuracy.get("total", 0) > 0:
            lines.append(f"- **本周决策**: {accuracy['total']} 条")
            lines.append(f"- **正确率**: {_safe_pct(accuracy.get('accuracy'))}")
        else:
            lines.append("- 本周无决策记录")
    except Exception as e:
        lines.append(f"- 决策数据查询失败: {e}")
    lines.append("")

    # 3. 因子表现
    lines.append("## 因子表现\n")
    try:
        factor_stats = storage.conn.execute("""
            SELECT factor_name, COUNT(*) as cnt, AVG(factor_value) as avg_val
            FROM factors
            WHERE date >= ?
            GROUP BY factor_name
            ORDER BY cnt DESC
            LIMIT 10
        """, [start_date.isoformat()]).fetchdf()
        if not factor_stats.empty:
            lines.append("| 因子 | 数据量 | 均值 |")
            lines.append("|------|--------|------|")
            for _, row in factor_stats.iterrows():
                lines.append(f"| {row['factor_name']} | {int(row['cnt'])} | {_safe_float(row['avg_val'], 4)} |")
        else:
            lines.append("- 本周无因子数据")
    except Exception as e:
        lines.append(f"- 因子数据查询失败: {e}")
    lines.append("")

    # 4. 策略回测
    lines.append("## 策略回测\n")
    try:
        runs = storage.load_backtest_runs()
        if not runs.empty:
            recent = runs.tail(5)
            lines.append("| 策略 | 标的 | 年化收益 | 夏普 | 最大回撤 |")
            lines.append("|------|------|----------|------|----------|")
            for _, row in recent.iterrows():
                lines.append(
                    f"| {row.get('strategy', '')} | {row.get('ticker', '')} | "
                    f"{_safe_pct(row.get('annual_return'))} | "
                    f"{_safe_float(row.get('sharpe_ratio'))} | "
                    f"{_safe_pct(row.get('max_drawdown'))} |"
                )
        else:
            lines.append("- 本周无回测记录")
    except Exception as e:
        lines.append(f"- 回测数据查询失败: {e}")
    lines.append("")

    # 5. 市场事件
    lines.append("## 市场事件\n")
    try:
        events = storage.conn.execute("""
            SELECT event_type, sentiment, COUNT(*) as cnt
            FROM events
            WHERE timestamp >= ?
            GROUP BY event_type, sentiment
            ORDER BY cnt DESC
            LIMIT 10
        """, [start_date.isoformat()]).fetchdf()
        if not events.empty:
            lines.append("| 事件类型 | 情绪 | 数量 |")
            lines.append("|----------|------|------|")
            for _, row in events.iterrows():
                lines.append(f"| {row['event_type']} | {row.get('sentiment', '')} | {int(row['cnt'])} |")
        else:
            lines.append("- 本周无事件数据")
    except Exception as e:
        lines.append(f"- 事件数据查询失败: {e}")
    lines.append("")

    return "\n".join(lines)


def generate_monthly_report(target_date: date = None,
                            storage: DataStorage = None,
                            cal: TradingCalendar = None) -> str:
    """
    生成月报内容（最近 20 个交易日）。

    Returns:
        Markdown 格式的月报内容
    """
    target_date = target_date or date.today()
    storage = storage or DataStorage()
    cal = cal or TradingCalendar(storage=storage)

    trading_days = _get_trading_day_range(cal, target_date, 20)
    if not trading_days:
        return f"# 月报 {target_date}\n\n> 无交易日数据"

    start_date = trading_days[0]
    month_str = f"{target_date.year}-{target_date.month:02d}"
    lines = [
        f"# 月报 {month_str}",
        f"\n> 生成时间: {date.today().isoformat()}",
        f"> 覆盖交易日: {len(trading_days)} 天 ({start_date} ~ {target_date})\n",
    ]

    # 1. 月度决策准确率
    lines.append("## 月度决策准确率\n")
    try:
        dm = DecisionMemory(storage)
        accuracy = dm.get_accuracy(days=30)
        if accuracy and accuracy.get("total", 0) > 0:
            lines.append(f"- **本月决策**: {accuracy['total']} 条")
            lines.append(f"- **正确率**: {_safe_pct(accuracy.get('accuracy'))}")
            lines.append(f"- **正确**: {accuracy.get('correct', 0)} 条")
        else:
            lines.append("- 本月无决策记录或收益未回填")
    except Exception as e:
        lines.append(f"- 决策数据查询失败: {e}")
    lines.append("")

    # 2. 因子月度排行
    lines.append("## 因子月度排行\n")
    try:
        factor_stats = storage.conn.execute("""
            SELECT factor_name, COUNT(*) as cnt, AVG(factor_value) as avg_val,
                   STDDEV(factor_value) as std_val
            FROM factors
            WHERE date >= ?
            GROUP BY factor_name
            ORDER BY cnt DESC
            LIMIT 15
        """, [start_date.isoformat()]).fetchdf()
        if not factor_stats.empty:
            lines.append("| 因子 | 数据量 | 均值 | 标准差 |")
            lines.append("|------|--------|------|--------|")
            for _, row in factor_stats.iterrows():
                lines.append(
                    f"| {row['factor_name']} | {int(row['cnt'])} | "
                    f"{_safe_float(row['avg_val'], 4)} | {_safe_float(row['std_val'], 4)} |"
                )
        else:
            lines.append("- 本月无因子数据")
    except Exception as e:
        lines.append(f"- 因子数据查询失败: {e}")
    lines.append("")

    # 3. 策略月度对比
    lines.append("## 策略月度对比\n")
    try:
        runs = storage.load_backtest_runs()
        if not runs.empty:
            lines.append(f"- **总回测次数**: {len(runs)}")
            if "annual_return" in runs.columns:
                best = runs.loc[runs["annual_return"].idxmax()]
                lines.append(f"- **最佳策略**: {best.get('strategy', '')} "
                           f"(年化 {_safe_pct(best.get('annual_return'))})")
            if "sharpe_ratio" in runs.columns:
                best_sharpe = runs.loc[runs["sharpe_ratio"].idxmax()]
                lines.append(f"- **最高夏普**: {best_sharpe.get('strategy', '')} "
                           f"(夏普 {_safe_float(best_sharpe.get('sharpe_ratio'))})")
        else:
            lines.append("- 本月无回测记录")
    except Exception as e:
        lines.append(f"- 回测数据查询失败: {e}")
    lines.append("")

    return "\n".join(lines)


def generate_quarterly_report(target_date: date = None,
                              storage: DataStorage = None,
                              cal: TradingCalendar = None) -> str:
    """
    生成季报内容（最近 60 个交易日）。

    Returns:
        Markdown 格式的季报内容
    """
    target_date = target_date or date.today()
    storage = storage or DataStorage()
    cal = cal or TradingCalendar(storage=storage)

    trading_days = _get_trading_day_range(cal, target_date, 60)
    if not trading_days:
        return f"# 季报 {target_date}\n\n> 无交易日数据"

    start_date = trading_days[0]
    quarter = (target_date.month - 1) // 3 + 1
    lines = [
        f"# 季报 Q{quarter}-{target_date.year}",
        f"\n> 生成时间: {date.today().isoformat()}",
        f"> 覆盖交易日: {len(trading_days)} 天 ({start_date} ~ {target_date})\n",
    ]

    # 1. 季度决策准确率
    lines.append("## 季度决策准确率\n")
    try:
        dm = DecisionMemory(storage)
        accuracy = dm.get_accuracy(days=90)
        if accuracy and accuracy.get("total", 0) > 0:
            lines.append(f"- **本季决策**: {accuracy['total']} 条")
            lines.append(f"- **正确率**: {_safe_pct(accuracy.get('accuracy'))}")
        else:
            lines.append("- 本季无决策记录或收益未回填")
    except Exception as e:
        lines.append(f"- 决策数据查询失败: {e}")
    lines.append("")

    # 2. 季度市场风格
    lines.append("## 季度市场风格\n")
    try:
        index_df = storage.load_index_daily("000300",
                                            start_date=start_date.isoformat())
        if not index_df.empty and "close" in index_df.columns:
            closes = index_df["close"]
            quarter_return = float(closes.iloc[-1] / closes.iloc[0] - 1) if len(closes) > 1 else 0
            max_close = float(closes.max())
            min_close = float(closes.min())
            lines.append(f"- **沪深300季度收益**: {_safe_pct(quarter_return)}")
            lines.append(f"- **最高**: {_safe_float(max_close)}")
            lines.append(f"- **最低**: {_safe_float(min_close)}")
            lines.append(f"- **波动率**: {_safe_float(closes.pct_change().std() * (252**0.5))}")
        else:
            lines.append("- 无指数数据")
    except Exception as e:
        lines.append(f"- 市场风格分析失败: {e}")
    lines.append("")

    # 3. 假设验证进展
    lines.append("## 假设验证进展\n")
    try:
        kb = KnowledgeBase()
        hypotheses = kb.load_hypotheses()
        if hypotheses:
            status_counts = {}
            for h in hypotheses:
                status = h.get("status", "unknown")
                status_counts[status] = status_counts.get(status, 0) + 1
            lines.append(f"- **总假设数**: {len(hypotheses)}")
            for status, count in sorted(status_counts.items()):
                lines.append(f"  - {status}: {count} 条")
        else:
            lines.append("- 无假设记录")
    except Exception as e:
        lines.append(f"- 假设数据查询失败: {e}")
    lines.append("")

    return "\n".join(lines)


def save_report(report_type: str,
                target_date: date = None,
                storage: DataStorage = None,
                kb: KnowledgeBase = None) -> Optional[Path]:
    """
    生成并保存高阶报告。

    Args:
        report_type: "weekly" / "monthly" / "quarterly"
        target_date: 报告日期（默认今天）
        storage: DataStorage 实例
        kb: KnowledgeBase 实例（用于测试注入；None 时用默认实例）

    Returns:
        保存的文件路径，失败返回 None
    """
    target_date = target_date or date.today()
    storage = storage or DataStorage()
    cal = TradingCalendar(storage=storage)

    generators = {
        "weekly": generate_weekly_report,
        "monthly": generate_monthly_report,
        "quarterly": generate_quarterly_report,
    }

    if report_type not in generators:
        raise ValueError(f"不支持的报告类型: {report_type}，支持: {list(generators.keys())}")

    try:
        content = generators[report_type](target_date, storage, cal)
        kb = kb or KnowledgeBase()
        path = kb.save_report(report_type, content=content, report_date=target_date)
        logger.success(f"报告已保存: {path}")
        return path
    except Exception as e:
        logger.error(f"报告生成失败 ({report_type}): {e}")
        return None


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="生成高阶报告")
    parser.add_argument("--type", required=True,
                       choices=["weekly", "monthly", "quarterly"],
                       help="报告类型")
    parser.add_argument("--date", default=None, help="报告日期 (YYYY-MM-DD)")
    args = parser.parse_args()

    report_date = date.fromisoformat(args.date) if args.date else None
    path = save_report(args.type, report_date)
    if path:
        print(f"报告已生成: {path}")
    else:
        print("报告生成失败")
