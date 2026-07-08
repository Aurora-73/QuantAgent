"""
Task scheduler — triggers daily research pipeline on trading days.

Uses the `schedule` library to run tasks at configured times.
Only executes on trading days (Mon-Fri, excluding known holidays).

Usage:
    python -m scripts.scheduler              # Start scheduler (foreground)
    python -m scripts.scheduler --run-now     # Run once immediately and exit
    python -m scripts.scheduler --dry-run     # Show schedule without executing

Configuration in configs/app.yaml:
    schedule:
      research_time: "16:00"    # Daily research trigger time
      data_update_time: "15:30" # Data update before research
"""
import sys
import time
from datetime import date, datetime
from pathlib import Path

from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))

from configs.settings import settings

# 旧版硬编码节假日（保留作为文档/回退参考，实际逻辑委托给 TradingCalendar）
# 新模块 data/trading_calendar.py 使用 AKShare 官方日历 + DuckDB 缓存 + 硬编码三级回退
_MARKET_HOLIDAYS = {
    # 2026 (approximate, 已迁移至 data/trading_calendar.py _FALLBACK_HOLIDAYS)
    "2026-01-01", "2026-01-02",   # New Year
    "2026-02-16", "2026-02-17", "2026-02-18", "2026-02-19", "2026-02-20",  # Spring Festival
    "2026-04-06",                 # Qingming
    "2026-05-01", "2026-05-04", "2026-05-05",  # Labor Day
    "2026-06-22",                 # Dragon Boat
    "2026-09-28",                 # Mid-Autumn
    "2026-10-01", "2026-10-02", "2026-10-05", "2026-10-06", "2026-10-07",  # National Day
}


def is_trading_day(d: date = None) -> bool:
    """Check if today is a trading day (delegates to TradingCalendar)."""
    from data.trading_calendar import TradingCalendar
    cal = TradingCalendar()
    try:
        return cal.is_trading_day(d)
    except Exception as e:
        # 回退到旧逻辑：周末 + 硬编码节假日
        logger.warning(f"TradingCalendar 失败，回退到硬编码: {e}")
        d = d or date.today()
        if d.weekday() >= 5:
            return False
        if d.isoformat() in _MARKET_HOLIDAYS:
            return False
        return True


def run_data_update():
    """Run incremental data update (market data only, no factors/research/reports)."""
    logger.info("定时数据更新开始（增量）")
    try:
        from scripts.update_data import update_market_data
        result = update_market_data(incremental=True)
        logger.success(f"定时数据更新完成: 更新 {result['tickers_updated']} 只, "
                       f"新增 {result['rows_added']} 行")
    except Exception as e:
        logger.error(f"定时数据更新失败: {e}")


def run_daily_pipeline():
    """Run full daily research pipeline."""
    logger.info("定时每日研究开始")
    if not is_trading_day():
        logger.info("今日非交易日，跳过")
        return

    try:
        from scripts.daily_research import run_daily_research
        # 2026-07-06: 架构定位调整为 MCP Server，不再内部调用 LLM
        run_daily_research(target_date=date.today(), use_llm=False)
        logger.success("定时每日研究完成")
    except Exception as e:
        logger.error(f"定时每日研究失败: {e}")


def run_backup():
    """Run DuckDB database backup (B4.1). Runs every calendar day."""
    logger.info("定时数据库备份开始")
    try:
        from scripts.backup import backup_database
        result = backup_database()
        logger.success(f"定时数据库备份完成: {result['backup_path']} "
                       f"({result['size_mb']} MB)")
    except Exception as e:
        logger.error(f"定时数据库备份失败: {e}")


def _get_calendar():
    """Get a TradingCalendar instance (owned by caller for cleanup)."""
    from data.trading_calendar import TradingCalendar
    return TradingCalendar()


def is_last_trading_day_of_month(cal, d: date = None) -> bool:
    """Check if d is the last trading day of its month."""
    d = d or date.today()
    if not cal.is_trading_day(d):
        return False
    nxt = cal.next_trading_day(d)
    # Last trading day of month if next trading day is in a later month (or none)
    return nxt is None or nxt.month != d.month or nxt.year != d.year


def is_last_trading_day_of_quarter(cal, d: date = None) -> bool:
    """Check if d is the last trading day of its quarter."""
    d = d or date.today()
    if not cal.is_trading_day(d):
        return False
    nxt = cal.next_trading_day(d)
    if nxt is None:
        return True
    cur_q = (d.month - 1) // 3 + 1
    nxt_q = (nxt.month - 1) // 3 + 1
    return nxt_q != cur_q or nxt.year != d.year


def run_scheduled_reports():
    """
    Generate higher-order reports when due (B1.3).

    Conditions:
      - Weekly:  every Friday that is a trading day
      - Monthly: last trading day of the month
      - Quarterly: last trading day of the quarter

    All checks use TradingCalendar; non-trading days skip entirely.
    """
    from research.reporting import save_report

    today = date.today()
    cal = None
    try:
        cal = _get_calendar()
        if not cal.is_trading_day(today):
            logger.info("今日非交易日，跳过高阶报告生成")
            return

        generated = []

        # Weekly: Friday (weekday==4)
        if today.weekday() == 4:
            try:
                path = save_report("weekly", today)
                if path:
                    generated.append(f"weekly -> {path.name}")
            except Exception as e:
                logger.error(f"周报生成失败: {e}")

        # Monthly: last trading day of month
        if is_last_trading_day_of_month(cal, today):
            try:
                path = save_report("monthly", today)
                if path:
                    generated.append(f"monthly -> {path.name}")
            except Exception as e:
                logger.error(f"月报生成失败: {e}")

        # Quarterly: last trading day of quarter
        if is_last_trading_day_of_quarter(cal, today):
            try:
                path = save_report("quarterly", today)
                if path:
                    generated.append(f"quarterly -> {path.name}")
            except Exception as e:
                logger.error(f"季报生成失败: {e}")

        if generated:
            logger.success(f"高阶报告已生成: {', '.join(generated)}")
        else:
            logger.info("今日无需生成高阶报告")
    finally:
        if cal is not None:
            cal.close()


def start_scheduler():
    """Start the scheduler loop (blocking)."""
    try:
        import schedule
    except ImportError:
        logger.error("schedule 库未安装: pip install schedule")
        return

    # Schedule jobs
    data_time = getattr(settings, 'schedule_data_update_time', '15:30')
    research_time = getattr(settings, 'schedule_research_time', '16:00')
    report_time = getattr(settings, 'schedule_report_time', '17:00')
    backup_time = getattr(settings, 'schedule_backup_time', '02:00')

    schedule.every().day.at(backup_time).do(run_backup)
    schedule.every().day.at(data_time).do(run_data_update)
    schedule.every().day.at(research_time).do(run_daily_pipeline)
    schedule.every().day.at(report_time).do(run_scheduled_reports)

    logger.info(f"定时任务已配置: 备份 {backup_time}, 数据更新 {data_time}, "
                f"每日研究 {research_time}, 高阶报告 {report_time}")
    logger.info("调度器运行中... (Ctrl+C 退出)")

    while True:
        schedule.run_pending()
        time.sleep(60)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="定时任务调度器")
    parser.add_argument("--run-now", action="store_true", help="立即执行一次并退出")
    parser.add_argument("--dry-run", action="store_true", help="显示调度计划但不执行")
    parser.add_argument("--task", choices=["data", "research", "reports", "backup", "all"],
                       default="all", help="执行指定任务")
    args = parser.parse_args()

    if args.dry_run:
        data_time = getattr(settings, 'schedule_data_update_time', '15:30')
        research_time = getattr(settings, 'schedule_research_time', '16:00')
        report_time = getattr(settings, 'schedule_report_time', '17:00')
        backup_time = getattr(settings, 'schedule_backup_time', '02:00')
        today = date.today()
        logger.info(f"调度计划 (今日: {today}, {'交易日' if is_trading_day(today) else '非交易日'}):")
        logger.info(f"  {backup_time} — 数据库备份（每日）")
        logger.info(f"  {data_time} — 数据更新")
        logger.info(f"  {research_time} — 每日研究流程")
        logger.info(f"  {report_time} — 高阶报告（周五周报/月末月报/季末季报）")
        logger.info(f"  研究流程仅交易日执行；备份每日执行")
        return

    if args.run_now:
        if args.task in ("backup", "all"):
            run_backup()
        if args.task in ("data", "all"):
            run_data_update()
        if args.task in ("research", "all"):
            run_daily_pipeline()
        if args.task in ("reports", "all"):
            run_scheduled_reports()
        return

    # Default: start persistent scheduler
    start_scheduler()


if __name__ == "__main__":
    main()
