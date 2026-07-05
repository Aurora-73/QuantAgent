"""
Social Collector — collect group chat messages via go-cqhttp WebSocket.

Architecture:
    go-cqhttp (QQ bot, external) → WebSocket → SocialCollector → LLM analysis → MarketFact

Usage:
    collector = SocialCollector(ws_url="ws://127.0.0.1:8080")
    collector.connect()
    messages = collector.collect(group_ids=[123456], timeout=60)
    collector.disconnect()

Dependencies:
    - websocket-client (pip install websocket-client)
    - go-cqhttp running externally (https://github.com/Mrs4s/go-cqhttp)
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from threading import Event, Thread
from typing import Optional

from loguru import logger

try:
    import websocket
    HAS_WEBSOCKET = True
except ImportError:
    HAS_WEBSOCKET = False


class SocialCollector:
    """
    QQ 群聊消息采集器

    通过 go-cqhttp 的 WebSocket 接口接收群消息。
    go-cqhttp 需先启动并配置好 WebSocket 服务端。
    """

    def __init__(self,
                 ws_url: str = "ws://127.0.0.1:8080",
                 access_token: str = None,
                 reconnect_interval: int = 5):
        """
        Args:
            ws_url: go-cqhttp WebSocket URL
            access_token: go-cqHTTP 访问令牌（如果有配置）
            reconnect_interval: 断线重连间隔（秒）
        """
        self.ws_url = ws_url
        self.access_token = access_token
        self.reconnect_interval = reconnect_interval
        self.ws: Optional[websocket.WebSocketApp] = None
        self._messages: list[dict] = []
        self._stop_event = Event()
        self._thread: Optional[Thread] = None
        self._connected = False

    def connect(self):
        """连接 WebSocket (非阻塞)"""
        if not HAS_WEBSOCKET:
            logger.warning("websocket-client 未安装，使用模拟模式。pip install websocket-client")
            self._connected = True
            return

        def on_message(ws, message):
            try:
                data = json.loads(message)
                if data.get("post_type") == "message" and data.get("message_type") == "group":
                    self._messages.append({
                        "group_id": data.get("group_id"),
                        "user_id": data.get("user_id"),
                        "message": str(data.get("raw_message", "")),
                        "time": datetime.fromtimestamp(data.get("time", time.time())),
                    })
            except json.JSONDecodeError:
                pass

        def on_error(ws, error):
            logger.error(f"  WebSocket 错误: {error}")

        def on_close(ws, close_status_code, close_msg):
            self._connected = False
            logger.info("  WebSocket 已断开")

        def on_open(ws):
            self._connected = True
            logger.info("  WebSocket 已连接")

        headers = {}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        self.ws = websocket.WebSocketApp(
            self.ws_url,
            header=headers,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
        )

        self._thread = Thread(target=self.ws.run_forever, daemon=True)
        self._thread.start()
        logger.info(f"  采集器已连接: {self.ws_url}")

    def disconnect(self):
        """断开 WebSocket 连接"""
        if self.ws:
            self.ws.close()
        self._stop_event.set()
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    def collect(self,
                group_ids: list[int] = None,
                timeout: int = 60) -> list[dict]:
        """
        收集指定群组的消息。

        Args:
            group_ids: 群号列表 (None = 所有群)
            timeout: 收集超时秒数

        Returns:
            消息列表 [{group_id, user_id, message, time}, ...]
        """
        if not self._connected:
            if HAS_WEBSOCKET:
                # WebSocket 已安装但未连上，等待一小段时间
                for _ in range(min(timeout, 5)):
                    if self._connected:
                        break
                    time.sleep(1)

            if not self._connected:
                # 模拟模式: 生成示例数据
                logger.info("  [模拟模式] 生成示例群聊消息")
                gids = group_ids or [123456]
                sample_messages = [
                    {"group_id": gid, "user_id": 10001,
                     "message": "今天白酒板块不错啊，茅台又要新高了？",
                     "time": datetime.now()} for gid in gids
                ]
                sample_messages.append({
                    "group_id": gids[0],
                    "user_id": 10002,
                    "message": "谨慎点吧，最近量能不够",
                    "time": datetime.now(),
                })
                sample_messages.append({
                    "group_id": gids[0],
                    "user_id": 10003,
                    "message": "AI 板块感觉还有机会，寒武纪又涨了",
                    "time": datetime.now(),
                })
                self._messages = sample_messages
                return self._messages

        collected = []
        start = time.time()
        while time.time() - start < timeout and not self._stop_event.is_set():
            new_messages = [
                m for m in self._messages
                if m not in collected
            ]
            for m in new_messages:
                if group_ids is None or m["group_id"] in group_ids:
                    collected.append(m)
            if collected:
                break
            time.sleep(1)

        return collected

    def get_active_users(self, since_hours: int = 24) -> int:
        """获取最近活跃用户数（用于可信度评估）"""
        cutoff = datetime.now().timestamp() - since_hours * 3600
        users = set()
        for m in self._messages:
            if isinstance(m["time"], datetime) and m["time"].timestamp() > cutoff:
                users.add(m["user_id"])
        return len(users)
