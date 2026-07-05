"""
结构化市场事实 — MarketFact + FactStore

MarketFact 是系统对"今天发生了什么"的统一建模。
来源包括行情数据、因子计算、新闻事件、LLM抽取结果。

FactStore 提供 DuckDB-backed 的 CRUD 操作。
"""
import json
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

import pandas as pd
from loguru import logger

from configs.settings import settings

try:
    import duckdb
    HAS_DUCKDB = True
except ImportError:
    HAS_DUCKDB = False


@dataclass
class MarketFact:
    """结构化市场事实

    一个事实是对市场上某一可观察现象的记录。
    区别于 Event（新闻驱动），MarketFact 是数据驱动的。
    """
    fact_id: str
    timestamp: datetime
    fact_type: str          # price_action / volume_event / technical_signal / fundamental / macro / factor_anomaly
    ticker: str             # 空字符串表示全市场
    description: str
    value: float = 0.0
    confidence: float = 1.0
    source: str = ""
    verified: bool = False
    tags: list[str] = field(default_factory=list)

    @classmethod
    def create(cls, fact_type: str, ticker: str, description: str,
               value: float = 0.0, confidence: float = 1.0,
               source: str = "", tags: list[str] = None) -> "MarketFact":
        return cls(
            fact_id=f"fact_{uuid.uuid4().hex[:8]}",
            timestamp=datetime.now(),
            fact_type=fact_type,
            ticker=ticker,
            description=description,
            value=value,
            confidence=confidence,
            source=source,
            tags=tags or [],
        )


class FactStore:
    """市场事实持久化存储

    底层使用 DuckDB market_facts 表。
    自动处理连接的创建和关闭。
    """

    def __init__(self, db_path: str = None):
        if not HAS_DUCKDB:
            raise ImportError("duckdb 未安装")
        self.db_path = db_path or settings.db_path
        self.conn = duckdb.connect(self.db_path)
        self._init_table()

    def _init_table(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS market_facts (
                fact_id VARCHAR PRIMARY KEY,
                timestamp TIMESTAMP,
                fact_type VARCHAR,
                ticker VARCHAR,
                description TEXT,
                value DOUBLE,
                confidence DOUBLE,
                source VARCHAR,
                verified BOOLEAN DEFAULT FALSE,
                tags TEXT
            )
        """)

    # ============================================================
    # CRUD
    # ============================================================

    def add(self, fact: MarketFact):
        """保存一个市场事实"""
        self.conn.execute("""
            INSERT OR REPLACE INTO market_facts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            fact.fact_id,
            fact.timestamp,
            fact.fact_type,
            fact.ticker,
            fact.description,
            fact.value,
            fact.confidence,
            fact.source,
            fact.verified,
            json.dumps(fact.tags, ensure_ascii=False),
        ])

    def add_batch(self, facts: list[MarketFact]):
        """批量保存"""
        for fact in facts:
            self.add(fact)

    def query(self, ticker: str = None, fact_type: str = None,
              start_date: str = None, end_date: str = None,
              verified: bool = None, limit: int = 100) -> list[MarketFact]:
        """查询市场事实"""
        conditions = []
        params = []

        if ticker:
            conditions.append("ticker = ?")
            params.append(ticker)
        if fact_type:
            conditions.append("fact_type = ?")
            params.append(fact_type)
        if start_date:
            conditions.append("timestamp >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("timestamp <= ?")
            params.append(end_date)
        if verified is not None:
            conditions.append("verified = ?")
            params.append(verified)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        query = f"SELECT * FROM market_facts {where} ORDER BY timestamp DESC LIMIT {limit}"

        df = self.conn.execute(query, params).fetchdf()
        if df.empty:
            return []

        facts = []
        for _, row in df.iterrows():
            tags = json.loads(row["tags"]) if row["tags"] else []
            facts.append(MarketFact(
                fact_id=row["fact_id"],
                timestamp=row["timestamp"],
                fact_type=row["fact_type"],
                ticker=row["ticker"],
                description=row["description"],
                value=row["value"],
                confidence=row["confidence"],
                source=row["source"],
                verified=row["verified"],
                tags=tags,
            ))
        return facts

    def query_df(self, ticker: str = None, fact_type: str = None,
                 start_date: str = None, end_date: str = None,
                 limit: int = 100) -> pd.DataFrame:
        """查询并返回 DataFrame"""
        conditions = []
        params = []

        if ticker:
            conditions.append("ticker = ?")
            params.append(ticker)
        if fact_type:
            conditions.append("fact_type = ?")
            params.append(fact_type)
        if start_date:
            conditions.append("timestamp >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("timestamp <= ?")
            params.append(end_date)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        query = f"SELECT * FROM market_facts {where} ORDER BY timestamp DESC LIMIT {limit}"

        return self.conn.execute(query, params).fetchdf()

    def verify(self, fact_id: str):
        """标记事实为已验证"""
        self.conn.execute(
            "UPDATE market_facts SET verified = TRUE WHERE fact_id = ?",
            [fact_id],
        )

    def delete(self, fact_id: str):
        """删除一个事实"""
        self.conn.execute("DELETE FROM market_facts WHERE fact_id = ?", [fact_id])

    def count(self, ticker: str = None, fact_type: str = None) -> int:
        """统计数量"""
        conditions = []
        params = []
        if ticker:
            conditions.append("ticker = ?")
            params.append(ticker)
        if fact_type:
            conditions.append("fact_type = ?")
            params.append(fact_type)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        return self.conn.execute(f"SELECT COUNT(*) FROM market_facts {where}", params).fetchone()[0]

    def get_stats(self) -> dict:
        """获取统计信息"""
        total = self.conn.execute("SELECT COUNT(*) FROM market_facts").fetchone()[0]
        verified = self.conn.execute(
            "SELECT COUNT(*) FROM market_facts WHERE verified = TRUE"
        ).fetchone()[0]
        by_type = self.conn.execute("""
            SELECT fact_type, COUNT(*) as cnt
            FROM market_facts GROUP BY fact_type ORDER BY cnt DESC
        """).fetchdf()
        return {
            "total": total,
            "verified": verified,
            "by_type": by_type.to_dict("records") if not by_type.empty else [],
        }

    def close(self):
        """关闭连接"""
        self.conn.close()
