"""
通知推送服务 — 基于 Server酱 (SendChan)

职责：
  - 任务完成通知
  - 风控告警推送
  - 每日报告摘要推送
  - 异常事件提醒

设计原则：
  - 支持多用户推送（每人一个 SendKey）
  - 使用 POST form 请求，避免中文 URL 编码问题
  - 默认隐藏调用者 IP
  - 标题限制 32 字符，正文支持 Markdown（限 32KB）
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional

import requests
from loguru import logger

from configs.settings import settings

# 用户注册表 — 从 settings 加载
USERS = {}
if settings.sendchan_sendkey_me:
    USERS["me"] = {"name": "我", "sendkey": settings.sendchan_sendkey_me}
if settings.sendchan_sendkey_daisen:
    USERS["daisen"] = {"name": "代森", "sendkey": settings.sendchan_sendkey_daisen}

_DEFAULT_SENDKEY = settings.sendchan_sendkey_me or ""
_API_ENDPOINT = settings.sendchan_api_url
_STATUS_ENDPOINT = settings.sendchan_status_url


@dataclass
class PushResult:
    """推送结果"""
    success: bool
    pushid: str = ""
    readkey: str = ""
    message: str = ""
    raw_response: dict = field(default_factory=dict)


@dataclass
class NotifierConfig:
    """通知配置"""
    sendkey: str = _DEFAULT_SENDKEY
    noip: bool = True
    channel: Optional[str] = None
    openid: Optional[str] = None


class SendChanNotifier:
    """
    Server酱推送器

    用法：
        notifier = SendChanNotifier()
        result = notifier.send("任务完成", "今日数据更新已完成。")

        # 多用户推送
        notifier = SendChanNotifier(sendkey="SCT...")
        result = notifier.send("风控告警", "## 回撤警告\\n当前回撤已超过 5%")
    """

    def __init__(self, sendkey: str = None, noip: bool = True,
                 channel: str = None, openid: str = None):
        self.config = NotifierConfig(
            sendkey=sendkey or _DEFAULT_SENDKEY,
            noip=noip,
            channel=channel,
            openid=openid,
        )

    def send(self, title: str, desp: str = "",
             short: str = None, noip: bool = None) -> PushResult:
        """
        发送推送

        Args:
            title: 标题（限 32 字符）
            desp: Markdown 正文（限 32KB）
            short: 卡片预览文本（限 64 字符）
            noip: 是否隐藏 IP（默认 True）

        Returns:
            PushResult
        """
        # 截断标题
        if len(title) > 32:
            title = title[:29] + "..."

        url = _API_ENDPOINT.format(sendkey=self.config.sendkey)

        data = {
            "title": title,
            "desp": desp,
            "noip": "1" if (noip if noip is not None else self.config.noip) else "0",
        }

        if short:
            data["short"] = short[:64]
        if self.config.channel:
            data["channel"] = self.config.channel
        if self.config.openid:
            data["openid"] = self.config.openid

        try:
            resp = requests.post(url, data=data, timeout=10)
            resp.raise_for_status()
            result = resp.json()

            success = result.get("code") == 0
            pushid = result.get("data", {}).get("pushid", "")
            readkey = result.get("data", {}).get("readkey", "")
            message = result.get("message", "")

            if success:
                logger.info(f"推送成功: {title} (pushid={pushid})")
            else:
                logger.warning(f"推送失败: {title} - {message}")

            return PushResult(
                success=success,
                pushid=pushid,
                readkey=readkey,
                message=message,
                raw_response=result,
            )

        except requests.RequestException as e:
            logger.error(f"推送异常: {title} - {e}")
            return PushResult(success=False, message=str(e))

    def query_status(self, pushid: str, readkey: str) -> dict:
        """
        查询推送状态

        Args:
            pushid: 推送 ID
            readkey: 读取密钥

        Returns:
            状态信息 dict
        """
        try:
            resp = requests.get(
                _STATUS_ENDPOINT,
                params={"id": pushid, "readkey": readkey},
                timeout=10,
            )
            return resp.json()
        except requests.RequestException as e:
            logger.error(f"查询状态异常: {e}")
            return {"error": str(e)}

    # ============================================================
    # 便捷方法
    # ============================================================

    def notify_task_done(self, task_name: str, detail: str = ""):
        """任务完成通知"""
        return self.send(
            title=f"✅ {task_name}",
            desp=detail or f"任务 `{task_name}` 已完成。",
        )

    def notify_alert(self, alert_type: str, detail: str):
        """风控告警通知"""
        icons = {
            "drawdown": "📉",
            "daily_loss": "💸",
            "data_anomaly": "⚠️",
            "system_error": "🔧",
        }
        icon = icons.get(alert_type, "🚨")
        return self.send(
            title=f"{icon} {alert_type}",
            desp=detail,
        )

    def notify_daily_report(self, date_str: str, summary: str):
        """每日报告通知"""
        return self.send(
            title=f"📊 日报 {date_str}",
            desp=summary,
        )

    def notify_signal(self, symbol: str, signal: str, reason: str = ""):
        """交易信号通知"""
        return self.send(
            title=f"📈 {symbol} {signal}",
            desp=reason,
        )


# ============================================================
# 多用户推送管理
# ============================================================

class MultiUserNotifier:
    """
    多用户推送管理器

    用法：
        # 自动加载注册表中的用户
        manager = MultiUserNotifier()
        manager.send_to("me", "通知", "内容")
        manager.send_to("daisen", "通知", "内容")
        manager.broadcast("系统通知", "今日维护完成")

        # 手动添加用户
        manager.add_user("alice", "SCT...")
    """

    def __init__(self, auto_load: bool = True):
        self._users: dict[str, SendChanNotifier] = {}
        if auto_load:
            self._load_from_registry()

    def _load_from_registry(self):
        """从 USERS 注册表加载"""
        for key, user in USERS.items():
            self._users[key] = SendChanNotifier(sendkey=user["sendkey"])

    def add_user(self, name: str, sendkey: str, **kwargs):
        """添加用户"""
        self._users[name] = SendChanNotifier(sendkey=sendkey, **kwargs)

    def remove_user(self, name: str):
        """移除用户"""
        self._users.pop(name, None)

    def send_to(self, name: str, title: str, desp: str = "") -> PushResult:
        """发送给指定用户"""
        if name not in self._users:
            return PushResult(success=False, message=f"用户 {name} 不存在")
        user_info = USERS.get(name, {})
        display_name = user_info.get("name", name)
        return self._users[name].send(title, desp)

    def broadcast(self, title: str, desp: str = "") -> dict[str, PushResult]:
        """广播给所有用户"""
        results = {}
        for name, notifier in self._users.items():
            results[name] = notifier.send(title, desp)
        return results

    def list_users(self) -> list[str]:
        """列出所有用户"""
        return list(self._users.keys())

    def get_user_info(self, name: str) -> dict:
        """获取用户信息"""
        return USERS.get(name, {})
