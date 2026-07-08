"""
MCP Knowledge Tools — reports, events, wiki, decisions, social sentiment.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from data.storage import DataStorage
from knowledge.knowledge_base import KnowledgeBase
from knowledge.wiki_retriever import WikiRetriever
from knowledge.decision_memory import DecisionMemory
from mcp_server.registry import register_mcp_tool


@register_mcp_tool(
    name="get_daily_report",
    description="获取指定日期的研究报告。用于每日研究",
    read_only=True,
    skill="daily-workflow",
)
def get_daily_report(report_date: str = "") -> str:
    """获取指定日期的研究报告"""
    try:
        kb = KnowledgeBase()
        target = date.fromisoformat(report_date) if report_date else date.today()
        content = kb.load_report("daily", target)
        if content is None:
            return json.dumps({"error": f"无日报: {target}"}, ensure_ascii=False)
        return content
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@register_mcp_tool(
    name="search_events",
    description="搜索结构化金融事件。用于知识探索",
    read_only=True,
    skill="knowledge-exploration",
)
def search_events(ticker: str = "", event_type: str = "", days: int = 7) -> str:
    """搜索结构化金融事件"""
    try:
        storage = DataStorage()
        start = (date.today() - timedelta(days=days)).isoformat()
        df = storage.load_events(
            ticker=ticker if ticker else None,
            event_type=event_type if event_type else None,
            start_date=start,
        )
        if df.empty:
            return json.dumps({"count": 0, "events": []}, ensure_ascii=False)
        records = []
        for _, row in df.iterrows():
            records.append({
                "event_id": str(row.get("event_id", "")),
                "date": str(row.get("timestamp", ""))[:10],
                "type": str(row.get("event_type", "")),
                "ticker": str(row.get("ticker", "")),
                "detail": str(row.get("detail", ""))[:100],
                "sentiment": str(row.get("sentiment", "")),
                "confidence": float(row.get("confidence", 0)),
            })
        return json.dumps({"count": len(records), "events": records}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@register_mcp_tool(
    name="wiki_search",
    description="搜索交易方法论文档。用于知识探索",
    read_only=True,
    skill="knowledge-exploration",
)
def wiki_search(query: str, top_k: int = 3) -> str:
    """搜索交易方法论文档"""
    try:
        retriever = WikiRetriever()
        results = retriever.search(query, top_k=top_k)
        serialized = []
        for entry, score in results:
            serialized.append({
                "title": entry.title,
                "type": entry.type,
                "tags": entry.tags,
                "keywords": entry.keywords,
                "market_regime": entry.market_regime,
                "timeframe": entry.timeframe,
                "content": (entry.content or "")[:200],
                "source": entry.source,
                "score": round(score, 3),
            })
        return json.dumps({"query": query, "count": len(serialized), "results": serialized},
                          ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@register_mcp_tool(
    name="get_knowledge_stats",
    description="获取知识库统计信息。用于知识探索",
    read_only=True,
    skill="knowledge-exploration",
)
def get_knowledge_stats() -> str:
    """获取知识库统计"""
    try:
        kb = KnowledgeBase()
        stats = kb.get_stats()
        return json.dumps(stats, ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@register_mcp_tool(
    name="get_recent_events",
    description="获取最近事件列表。用于知识探索",
    read_only=True,
    skill="knowledge-exploration",
)
def get_recent_events(limit: int = 20) -> str:
    """获取最近事件"""
    try:
        storage = DataStorage()
        df = storage.load_events(limit=limit)
        if df.empty:
            return json.dumps({"count": 0, "events": []}, ensure_ascii=False)
        records = []
        for _, row in df.iterrows():
            records.append({
                "event_id": str(row.get("event_id", "")),
                "date": str(row.get("timestamp", ""))[:10],
                "type": str(row.get("event_type", "")),
                "ticker": str(row.get("ticker", "")),
                "detail": str(row.get("detail", ""))[:80],
            })
        return json.dumps({"count": len(records), "events": records}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@register_mcp_tool(
    name="get_decision_accuracy",
    description="查询决策记忆准确率。用于知识探索",
    read_only=True,
    skill="knowledge-exploration",
)
def get_decision_accuracy(signal_type: str = "", days: int = 90) -> str:
    """查询决策记忆准确率"""
    try:
        storage = DataStorage()
        dm = DecisionMemory(storage)
        if signal_type:
            acc = dm.get_accuracy(signal_type=signal_type, days=days)
        else:
            acc = dm.get_accuracy(days=days)
        return json.dumps(acc, ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@register_mcp_tool(
    name="get_recent_decisions",
    description="获取最近决策记录。用于知识探索",
    read_only=True,
    skill="knowledge-exploration",
)
def get_recent_decisions(limit: int = 20) -> str:
    """获取最近决策记录"""
    try:
        storage = DataStorage()
        dm = DecisionMemory(storage)
        df = dm.get_recent_decisions(limit=limit)
        if df.empty:
            return json.dumps({"count": 0, "decisions": []}, ensure_ascii=False)
        records = []
        for _, row in df.iterrows():
            records.append({
                "decision_id": str(row.get("decision_id", "")),
                "date": str(row.get("decision_date", ""))[:10],
                "ticker": str(row.get("ticker", "")),
                "direction": str(row.get("direction", "")),
                "weight": float(row.get("weight", 0)),
                "return_1d": float(row.get("return_1d", 0)) if row.get("return_1d") is not None else None,
            })
        return json.dumps({"count": len(records), "decisions": records}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@register_mcp_tool(
    name="get_prediction_accuracy",
    description="获取预测准确率统计。用于知识探索",
    read_only=True,
    skill="knowledge-exploration",
)
def get_prediction_accuracy(days: int = 30) -> str:
    """获取预测准确率统计"""
    try:
        storage = DataStorage()
        stats = storage.get_prediction_stats(days=days)
        return json.dumps(stats, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@register_mcp_tool(
    name="get_db_stats",
    description="获取数据库各表行数统计。用于知识探索",
    read_only=True,
    skill="knowledge-exploration",
)
def get_db_stats() -> str:
    """获取数据库各表行数统计"""
    try:
        storage = DataStorage()
        stats = storage.get_table_stats()
        return json.dumps(stats, ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@register_mcp_tool(
    name="get_social_sentiment",
    description="获取社交情绪分析结果。用于知识探索",
    read_only=True,
    skill="knowledge-exploration",
)
def get_social_sentiment(days: int = 1) -> str:
    """获取社交情绪分析结果

    注意：社交情绪管道当前已后移（2026-07-06），
    依赖 go-cqhttp 后端且原实现依赖内部 LLM 调用。
    当前返回空数据和状态说明。
    """
    try:
        # 尝试从 MarketFact DB 读取历史数据（如有）
        from data.market_fact import FactStore
        store = FactStore()
        facts = store.query(fact_type="social_sentiment", limit=5)
        fact_list = []
        for f in facts:
            fact_list.append({
                "fact_id": f.fact_id,
                "timestamp": str(f.timestamp),
                "description": f.description[:100],
                "confidence": f.confidence,
            })
        return json.dumps({
            "status": "disabled",
            "message": "社交情绪管道已后移，当前不执行采集和分析",
            "reason": "依赖 go-cqhttp 后端 + 内部 LLM 调用，架构定位调整为 MCP Server 后暂不维护",
            "recent_facts": fact_list,
            "count": len(fact_list),
        }, ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": str(e),
            "recent_facts": [],
            "count": 0,
        }, ensure_ascii=False)


@register_mcp_tool(
    name="search_hypotheses",
    description="搜索投资假设库。用于知识探索",
    read_only=True,
    skill="knowledge-exploration",
)
def search_hypotheses(limit: int = 20) -> str:
    """搜索投资假设库"""
    try:
        from knowledge.knowledge_base import KnowledgeBase
        kb = KnowledgeBase()
        import json as _json
        hypos = kb.list_hypotheses(limit=limit) if hasattr(kb, 'list_hypotheses') else []
        return _json.dumps({"count": len(hypos), "hypotheses": hypos}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# ============================================================
# 高阶报告工具 (Phase 4 B1.3)
# ============================================================

@register_mcp_tool(
    name="get_higher_order_report",
    description="查询周报/月报/季报内容。用于知识探索和跨时间尺度分析",
    read_only=True,
    skill="knowledge-exploration",
)
def get_higher_order_report(report_type: str = "weekly",
                            report_date: str = "") -> str:
    """
    查询已生成的高阶报告。

    Args:
        report_type: "weekly" / "monthly" / "quarterly"
        report_date: 报告日期 (YYYY-MM-DD)，为空则取最新

    Returns:
        JSON 格式的报告内容
    """
    try:
        from knowledge.knowledge_base import KnowledgeBase
        from datetime import date as _date

        kb = KnowledgeBase()

        if report_date:
            target = _date.fromisoformat(report_date)
            content = kb.load_report(report_type, target)
        else:
            reports = kb.list_reports(report_type, limit=1)
            if reports:
                filepath = Path(reports[0]["path"])
                content = filepath.read_text(encoding="utf-8") if filepath.exists() else None
            else:
                content = None

        if content is None:
            return json.dumps({
                "report_type": report_type,
                "found": False,
                "message": f"未找到 {report_type} 报告",
            }, ensure_ascii=False)

        return json.dumps({
            "report_type": report_type,
            "found": True,
            "content": content,
            "length": len(content),
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@register_mcp_tool(
    name="generate_higher_order_report",
    description="生成并保存周报/月报/季报（从 decision_memory/factors/events/backtest_runs 聚合）。注意：写操作。用于每日研究",
    read_only=False,
    skill="daily-workflow",
)
def generate_higher_order_report(report_type: str = "weekly",
                                 report_date: str = "",
                                 dry_run: bool = False) -> str:
    """
    生成并保存高阶报告。

    从 decision_memory、factors、events、backtest_runs 聚合数据，
    生成周/月/季报，保存到 KnowledgeBase 报告目录。

    Args:
        report_type: "weekly" / "monthly" / "quarterly"
        report_date: 报告日期 (YYYY-MM-DD)，为空则今天
        dry_run: 预览模式（不保存）
    """
    try:
        if report_type not in ("weekly", "monthly", "quarterly"):
            return json.dumps({
                "success": False,
                "message": f"不支持的报告类型: {report_type}",
            }, ensure_ascii=False)

        if dry_run:
            return json.dumps({
                "success": True,
                "message": "dry-run 模式：报告生成预览",
                "dry_run": True,
                "report_type": report_type,
                "report_date": report_date or str(__import__("datetime").date.today()),
            }, ensure_ascii=False)

        from research.reporting import save_report
        from datetime import date as _date

        target = _date.fromisoformat(report_date) if report_date else None
        path = save_report(report_type, target)

        if path:
            return json.dumps({
                "success": True,
                "message": f"{report_type} 报告已生成",
                "path": str(path),
                "report_type": report_type,
            }, ensure_ascii=False)
        else:
            return json.dumps({
                "success": False,
                "message": f"{report_type} 报告生成失败",
            }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({
            "success": False,
            "message": str(e),
        }, ensure_ascii=False)
