#!/usr/bin/env python3
"""
Server酱推送脚本

用法：
    python scripts/send_notify.py --title "任务完成" --desp "数据更新已完成。"
    python scripts/send_notify.py --title "风控告警" --desp "## 回撤警告\n当前回撤超过5%"
    python scripts/send_notify.py --title "日报" --file report.md
    python scripts/send_notify.py --title "信号" --desp "贵州茅台 买入信号" --key SCT...
"""
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from monitoring.notifier import SendChanNotifier


def main():
    parser = argparse.ArgumentParser(description="Server酱推送")
    parser.add_argument("--title", required=True, help="标题（限32字符）")
    parser.add_argument("--desp", default="", help="Markdown正文（限32KB）")
    parser.add_argument("--file", help="从文件读取正文")
    parser.add_argument("--short", help="卡片预览文本（限64字符）")
    parser.add_argument("--key", help="SendKey（默认使用内置key）")
    parser.add_argument("--channel", help="推送通道")
    parser.add_argument("--noip", default="1", help="隐藏IP（默认1）")
    parser.add_argument("--query", nargs=2, metavar=("PUSHID", "READKEY"),
                       help="查询推送状态")

    args = parser.parse_args()

    from loguru import logger

    # 查询状态
    if args.query:
        notifier = SendChanNotifier()
        result = notifier.query_status(args.query[0], args.query[1])
        logger.info(f"状态: {result}")
        return

    # 读取文件内容
    desp = args.desp
    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            logger.error(f"文件不存在: {args.file}")
            sys.exit(1)
        desp = file_path.read_text(encoding="utf-8")

    # 发送推送
    notifier = SendChanNotifier(
        sendkey=args.key,
        noip=(args.noip == "1"),
        channel=args.channel,
    )

    result = notifier.send(
        title=args.title,
        desp=desp,
        short=args.short,
    )

    if result.success:
        logger.success(f"✅ 推送成功")
        logger.success(f"   pushid: {result.pushid}")
        logger.success(f"   readkey: {result.readkey}")
        logger.success(f"   message: {result.message}")
        if result.pushid and result.readkey:
            logger.info(f"\n查询状态:")
            logger.info(f"   python scripts/send_notify.py --query {result.pushid} {result.readkey}")
    else:
        logger.error(f"❌ 推送失败: {result.message}")
        sys.exit(1)


if __name__ == "__main__":
    main()
