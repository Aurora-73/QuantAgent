"""
知识库查询脚本

用法：
    python -m scripts.show_knowledge --type daily
    python -m scripts.show_knowledge --type events --limit 20
    python -m scripts.show_knowledge --type stats
"""
import sys
import argparse
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from knowledge.knowledge_base import KnowledgeBase

from loguru import logger


def show_knowledge(kb_type: str, limit: int = 10, date_str: str = None):
    """查询知识库"""
    kb = KnowledgeBase()

    if kb_type == "stats":
        stats = kb.get_stats()
        logger.info("\n=== 知识库统计 ===")
        for k, v in stats.items():
            logger.info(f"  {k}: {v}")

    elif kb_type == "daily":
        if date_str:
            from datetime import date
            report = kb.load_report("daily", date.fromisoformat(date_str))
            if report:
                logger.info(report)
            else:
                logger.info(f"{date_str} 无日报")
        else:
            reports = kb.list_reports("daily", limit)
            logger.info(f"\n=== 最近 {len(reports)} 份日报 ===")
            for r in reports:
                logger.info(f"  {r['filename']}")

    elif kb_type == "weekly":
        reports = kb.list_reports("weekly", limit)
        logger.info(f"\n=== 最近 {len(reports)} 份周报 ===")
        for r in reports:
            logger.info(f"  {r['filename']}")

    elif kb_type == "monthly":
        reports = kb.list_reports("monthly", limit)
        logger.info(f"\n=== 最近 {len(reports)} 份月报 ===")
        for r in reports:
            logger.info(f"  {r['filename']}")

    elif kb_type == "events":
        events = kb.load_events(limit=limit)
        logger.info(f"\n=== 最近 {len(events)} 个事件 ===")
        for e in events:
            etype = e.get("event_type", "?")
            ticker = e.get("ticker", "?")
            detail = e.get("detail", "")[:60]
            sentiment = e.get("sentiment", "?")
            logger.info(f"  [{etype}] {ticker} {detail} ({sentiment})")

    elif kb_type == "hypotheses":
        hypotheses = kb.load_hypotheses()
        logger.info(f"\n=== 假设库 ({len(hypotheses)} 条) ===")
        for h in hypotheses:
            status = h.get("status", "?")
            desc = h.get("description", "")[:60]
            icon = "✅" if status == "verified" else "⏳" if status == "pending" else "❌"
            logger.info(f"  {icon} [{status}] {desc}")

    elif kb_type == "failures":
        failures = kb.load_failures(limit=limit)
        logger.info(f"\n=== 失败案例 ({len(failures)} 条) ===")
        for f in failures:
            date = f.get("date", "?")
            category = f.get("category", "?")
            lesson = f.get("lesson", "")[:60]
            logger.info(f"  [{date}] [{category}] {lesson}")

    else:
        logger.error(f"未知类型: {kb_type}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="知识库查询")
    parser.add_argument("--type", default="stats",
                       choices=["stats", "daily", "weekly", "monthly",
                                "events", "hypotheses", "failures"],
                       help="查询类型")
    parser.add_argument("--limit", type=int, default=10, help="显示条数")
    parser.add_argument("--date", default=None, help="指定日期")
    args = parser.parse_args()

    show_knowledge(args.type, args.limit, args.date)
