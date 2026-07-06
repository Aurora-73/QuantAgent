"""
告警管理器

监控并告警：
  - 策略收益异常
  - 风控规则触发
  - 数据异常
  - 回测/实盘偏差
  - 系统异常
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from loguru import logger


class AlertLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertType(Enum):
    DRAWDOWN = "drawdown"
    DAILY_LOSS = "daily_loss"
    VOLATILITY = "volatility"
    DATA_ANOMALY = "data_anomaly"
    BACKTEST_DEVIATION = "backtest_deviation"
    SYSTEM_ERROR = "system_error"
    STRATEGY_KILL_SWITCH = "strategy_kill_switch"


@dataclass
class Alert:
    """一条告警"""
    alert_id: str
    timestamp: datetime
    level: AlertLevel
    alert_type: AlertType
    title: str
    detail: str
    ticker: Optional[str] = None
    acknowledged: bool = False


class AlertManager:
    """告警管理器"""

    def __init__(self, notifier=None):
        self.notifier = notifier
        self.alerts: list[Alert] = []
        self._counter = 0

    def fire(self, level: AlertLevel, alert_type: AlertType,
             title: str, detail: str, ticker: str = None) -> Alert:
        """触发告警"""
        self._counter += 1
        alert = Alert(
            alert_id=f"alert_{self._counter:06d}",
            timestamp=datetime.now(),
            level=level,
            alert_type=alert_type,
            title=title,
            detail=detail,
            ticker=ticker,
        )
        self.alerts.append(alert)

        # 输出到控制台
        log_map = {"info": logger.info, "warning": logger.warning, "critical": logger.error}
        log_func = log_map[level.value]
        log_func(f"[{alert.level.value.upper()}] {alert.title}: {alert.detail}")

        # 发送通知
        if self.notifier and level in (AlertLevel.WARNING, AlertLevel.CRITICAL):
            self._send_notification(alert)

        return alert

    def check_drawdown(self, current_drawdown: float,
                       threshold: float = -0.05):
        """检查回撤告警"""
        if current_drawdown < threshold:
            return self.fire(
                AlertLevel.CRITICAL,
                AlertType.DRAWDOWN,
                "最大回撤触发",
                f"当前回撤 {current_drawdown:.2%} 超过阈值 {threshold:.2%}",
            )
        elif current_drawdown < threshold * 0.8:
            return self.fire(
                AlertLevel.WARNING,
                AlertType.DRAWDOWN,
                "回撤预警",
                f"当前回撤 {current_drawdown:.2%} 接近阈值 {threshold:.2%}",
            )
        return None

    def check_daily_loss(self, daily_return: float,
                         threshold: float = -0.02):
        """检查日亏损告警"""
        if daily_return < threshold:
            return self.fire(
                AlertLevel.CRITICAL,
                AlertType.DAILY_LOSS,
                "日亏损限额触发",
                f"今日亏损 {daily_return:.2%} 超过限额 {threshold:.2%}",
            )
        return None

    def check_data_anomaly(self, ticker: str, detail: str):
        """数据异常告警"""
        return self.fire(
            AlertLevel.WARNING,
            AlertType.DATA_ANOMALY,
            f"数据异常: {ticker}",
            detail,
            ticker=ticker,
        )

    def check_backtest_deviation(self, strategy: str,
                                  backtest_return: float,
                                  live_return: float,
                                  threshold: float = 0.05):
        """回测 vs 实盘偏差告警"""
        deviation = abs(backtest_return - live_return)
        if deviation > threshold:
            return self.fire(
                AlertLevel.WARNING,
                AlertType.BACKTEST_DEVIATION,
                f"回测偏差: {strategy}",
                f"回测收益 {backtest_return:.2%} vs 实盘收益 {live_return:.2%}, 偏差 {deviation:.2%}",
            )
        return None

    def get_unacknowledged(self) -> list[Alert]:
        """获取未确认的告警"""
        return [a for a in self.alerts if not a.acknowledged]

    def acknowledge(self, alert_id: str):
        """确认告警"""
        for alert in self.alerts:
            if alert.alert_id == alert_id:
                alert.acknowledged = True
                break

    def _send_notification(self, alert: Alert):
        """发送通知到外部服务（通过 notifier，默认使用 Server酱）"""
        try:
            if self.notifier is None:
                from monitoring.notifier import SendChanNotifier
                self.notifier = SendChanNotifier()
            self.notifier.notify_alert(alert.alert_type.value, alert.detail)
        except Exception as e:
            logger.warning(f"告警通知发送失败: {e}")
