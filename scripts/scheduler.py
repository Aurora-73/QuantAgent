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

# Known A-share market holidays (approximate, update yearly)
_MARKET_HOLIDAYS = {
    # 2026 (approximate)
    "2026-01-01", "2026-01-02",   # New Year
    "2026-02-16", "2026-02-17", "2026-02-18", "2026-02-19", "2026-02-20",  # Spring Festival
    "2026-04-06",                 # Qingming
    "2026-05-01", "2026-05-04", "2026-05-05",  # Labor Day
    "2026-06-22",                 # Dragon Boat
    "2026-09-28",                 # Mid-Autumn
    "2026-10-01", "2026-10-02", "2026-10-05", "2026-10-06", "2026-10-07",  # National Day
}


def is_trading_day(d: date = None) -> bool:
    """Check if today is a trading day."""
    d = d or date.today()

    # Weekends
    if d.weekday() >= 5:  # Saturday=5, Sunday=6
        return False

    # Known holidays
    if d.isoformat() in _MARKET_HOLIDAYS:
        return False

    return True


def run_data_update():
    """Run data update step."""
    logger.info("定时数据更新开始")
    try:
        from scripts.daily_research import run_daily_research
        run_daily_research(target_date=date.today(), use_llm=False)
        logger.success("定时数据更新完成")
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

    schedule.every().day.at(data_time).do(run_data_update)
    schedule.every().day.at(research_time).do(run_daily_pipeline)

    logger.info(f"定时任务已配置: 数据更新 {data_time}, 每日研究 {research_time}")
    logger.info("调度器运行中... (Ctrl+C 退出)")

    while True:
        schedule.run_pending()
        time.sleep(60)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="定时任务调度器")
    parser.add_argument("--run-now", action="store_true", help="立即执行一次并退出")
    parser.add_argument("--dry-run", action="store_true", help="显示调度计划但不执行")
    parser.add_argument("--task", choices=["data", "research", "all"],
                       default="all", help="执行指定任务")
    args = parser.parse_args()

    if args.dry_run:
        data_time = getattr(settings, 'schedule_data_update_time', '15:30')
        research_time = getattr(settings, 'schedule_research_time', '16:00')
        today = date.today()
        logger.info(f"调度计划 (今日: {today}, {'交易日' if is_trading_day(today) else '非交易日'}):")
        logger.info(f"  {data_time} — 数据更新")
        logger.info(f"  {research_time} — 每日研究流程")
        logger.info(f"  仅交易日执行")
        return

    if args.run_now:
        if args.task in ("data", "all"):
            run_data_update()
        if args.task in ("research", "all"):
            run_daily_pipeline()
        return

    # Default: start persistent scheduler
    start_scheduler()


if __name__ == "__main__":
    main()
