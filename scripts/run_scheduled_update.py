"""
定时数据更新包装脚本（供 systemd timer 调用）。

职责：
  1. 检查今天是否为交易日（TradingCalendar），非交易日跳过
  2. 交易日运行增量数据更新（update_market_data）
  3. 失败时通过 AlertManager → SendChanNotifier 推送告警
  4. 成功时记录日志（可选推送通知）

用法（手动测试）：
    python -m scripts.run_scheduled_update
    python -m scripts.run_scheduled_update --force   # 强制运行（忽略非交易日）
    python -m scripts.run_scheduled_update --dry-run  # 预览不执行
"""
from __future__ import annotations

import argparse
import sys
import traceback
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

from data.trading_calendar import TradingCalendar
from scripts.update_data import update_market_data


def run_scheduled_update(force: bool = False, dry_run: bool = False) -> int:
    """
    运行定时数据更新。

    Args:
        force: 强制运行（忽略非交易日检查）
        dry_run: 预览模式，不执行实际更新

    Returns:
        退出码: 0=成功/跳过, 1=失败
    """
    today = date.today()

    # 1. 交易日检查
    if not force:
        cal = None
        try:
            cal = TradingCalendar()
            if not cal.is_trading_day(today):
                logger.info(f"今天 {today} 非交易日，跳过数据更新")
                return 0
        except Exception as e:
            logger.warning(f"交易日历检查失败，按交易日处理: {e}")
        finally:
            if cal is not None:
                cal.close()

    logger.info(f"{'='*60}")
    logger.info(f"  定时数据更新 ({today})")
    logger.info(f"{'='*60}")

    if dry_run:
        logger.info("dry-run 模式：跳过实际更新")
        return 0

    # 2. 运行增量更新
    try:
        result = update_market_data(target_date=today, incremental=True)
        logger.success(
            f"数据更新完成: {result['tickers_updated']} 只更新, "
            f"{result['rows_added']} 行新增, {len(result['skipped'])} 只跳过"
        )

        # 3. 成功通知（可选）
        _notify_success(result)
        return 0

    except Exception as e:
        logger.error(f"数据更新失败: {e}")
        logger.error(traceback.format_exc())
        _notify_failure(e)
        return 1


def _notify_success(result: dict):
    """成功时推送通知"""
    try:
        from monitoring.notifier import SendChanNotifier
        notifier = SendChanNotifier()
        notifier.notify_task_done(
            "定时数据更新",
            f"更新 {result['tickers_updated']} 只, 新增 {result['rows_added']} 行",
        )
    except Exception as e:
        logger.debug(f"成功通知发送失败（非致命）: {e}")


def _notify_failure(error: Exception):
    """失败时推送告警"""
    try:
        from monitoring.alerts import AlertManager, AlertLevel, AlertType
        am = AlertManager()
        am.fire(
            level=AlertLevel.CRITICAL,
            alert_type=AlertType.SYSTEM_ERROR,
            title="定时数据更新失败",
            detail=f"{error}",
        )
    except Exception as e:
        logger.error(f"告警发送失败: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="定时数据更新（供 systemd 调用）")
    parser.add_argument("--force", action="store_true", help="强制运行（忽略非交易日）")
    parser.add_argument("--dry-run", action="store_true", help="预览模式")
    args = parser.parse_args()

    exit_code = run_scheduled_update(force=args.force, dry_run=args.dry_run)
    sys.exit(exit_code)
