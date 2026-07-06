"""
数据存储层 — 基于 DuckDB

职责：
  - 持久化行情数据
  - 持久化因子数据
  - 持久化事件数据
  - 提供高效的查询接口

DuckDB 优势：
  - 列式存储，分析查询快
  - 单文件数据库，部署简单
  - 兼容 SQL 语法
  - 直接查询 Parquet/CSV
"""
import json
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from loguru import logger

from configs.settings import settings

try:
    import duckdb
    HAS_DUCKDB = True
except ImportError:
    HAS_DUCKDB = False
    logger.warning("duckdb 未安装，数据存储功能不可用。pip install duckdb")


class DataStorage:
    """
    DuckDB 数据存储 — 分层架构

    分层：
      raw.*        数据原始层，写入后不修改
      cleaned.*    清洗层，包含去极值、前向填充等处理
      research.*   研究层，包含因子、事件、预测、决策
      published.*  发布层，包含回测结果、经验教训

    表结构：
      - stock_daily: 个股日线行情
      - index_daily: 指数日线行情
      - factors: 因子数据
      - events: 结构化事件
      - predictions: 预测记录
      - lessons: 经验教训
    """

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = settings.db_path
        if not HAS_DUCKDB:
            raise ImportError("duckdb 未安装")
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = duckdb.connect(str(self.db_path))
        self._init_tables()

    def _init_tables(self):
        """初始化表结构"""
        # schema_version 表必须在其他迁移之前创建
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version VARCHAR PRIMARY KEY,
                description VARCHAR,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 先创建所有 public 表，再运行迁移（迁移可能引用这些表）
        self._create_public_tables()

        self._run_migrations()

        # 分层架构：创建 schema 和分层表（与 public 表共存，逐步迁移）
        self._init_schemas()

    def _create_public_tables(self):
        """创建 public schema 下的所有表（在迁移之前创建）"""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS stock_daily (
                ticker VARCHAR,
                date DATE,
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume BIGINT,
                amount DOUBLE,
                pct_change DOUBLE,
                turnover DOUBLE,
                PRIMARY KEY (ticker, date)
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS index_daily (
                index_code VARCHAR,
                date DATE,
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume BIGINT,
                PRIMARY KEY (index_code, date)
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS factors (
                ticker VARCHAR,
                date DATE,
                factor_name VARCHAR,
                factor_value DOUBLE,
                PRIMARY KEY (ticker, date, factor_name)
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                event_id VARCHAR PRIMARY KEY,
                timestamp TIMESTAMP,
                source VARCHAR,
                event_type VARCHAR,
                ticker VARCHAR,
                company VARCHAR,
                detail TEXT,
                sentiment VARCHAR,
                impact_objects TEXT,
                time_window VARCHAR,
                confidence DOUBLE,
                tradability VARCHAR,
                tags TEXT
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                prediction_id VARCHAR PRIMARY KEY,
                date DATE,
                agent VARCHAR,
                category VARCHAR,
                prediction TEXT,
                confidence DOUBLE,
                time_horizon VARCHAR,
                verify_date DATE,
                actual_result TEXT,
                verified BOOLEAN DEFAULT FALSE,
                correct BOOLEAN,
                lesson TEXT
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS lessons (
                lesson_id VARCHAR PRIMARY KEY,
                date DATE,
                category VARCHAR,
                lesson TEXT,
                evidence TEXT,
                confidence DOUBLE,
                applicable TEXT,
                times_applied INTEGER DEFAULT 0,
                success_rate DOUBLE DEFAULT 0.0
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS backtest_runs (
                run_id VARCHAR PRIMARY KEY,
                strategy VARCHAR,
                ticker VARCHAR,
                date_start DATE,
                date_end DATE,
                params_json TEXT,
                total_return DOUBLE,
                annual_return DOUBLE,
                sharpe_ratio DOUBLE,
                max_drawdown DOUBLE,
                win_rate DOUBLE,
                trade_count INTEGER,
                init_cash DOUBLE,
                fees DOUBLE,
                slippage DOUBLE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS backtest_equity (
                run_id VARCHAR,
                date DATE,
                equity_value DOUBLE,
                PRIMARY KEY (run_id, date)
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS decision_memory (
                decision_id VARCHAR PRIMARY KEY,
                decision_date DATE,
                ticker VARCHAR,
                direction VARCHAR,
                weight DOUBLE,
                price DOUBLE,
                reason TEXT,
                signal_type VARCHAR,
                strategy VARCHAR,
                return_1d DOUBLE,
                return_3d DOUBLE,
                return_5d DOUBLE,
                return_10d DOUBLE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    def _run_migrations(self):
        """查找并应用 data/migrations/ 下未执行的迁移"""
        migrations_dir = Path(__file__).parent / "migrations"
        if not migrations_dir.exists():
            return

        # 获取已应用的迁移
        applied = set()
        try:
            rows = self.conn.execute(
                "SELECT version FROM schema_version ORDER BY version"
            ).fetchall()
            applied = {r[0] for r in rows}
        except Exception:
            pass  # schema_version 表可能刚创建

        # 按编号排序迁移文件
        migration_files = sorted(migrations_dir.glob("*.sql"))
        for mf in migration_files:
            version = mf.stem  # e.g. "001_init"
            if version in applied:
                continue

            sql = mf.read_text(encoding="utf-8")
            try:
                self.conn.execute(sql)
                self.conn.execute(
                    "INSERT INTO schema_version (version, description) VALUES (?, ?)",
                    [version, mf.stem.replace("_", " ").title()],
                )
                logger.info(f"  迁移 {version} 已应用")
            except Exception as e:
                logger.error(f"  迁移 {version} 失败: {e}")
                raise

    def _init_schemas(self):
        """初始化分层 schema 和分层表"""
        # 创建 schema
        for schema in ["raw", "cleaned", "research", "published"]:
            self.conn.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")

        # raw.stock_daily — 原始行情副本
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS raw.stock_daily (
                ticker VARCHAR,
                date DATE,
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume BIGINT,
                amount DOUBLE,
                pct_change DOUBLE,
                turnover DOUBLE,
                ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # raw.index_daily — 原始指数副本
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS raw.index_daily (
                index_code VARCHAR,
                date DATE,
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume BIGINT,
                ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # cleaned.stock_daily — 清洗后行情
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS cleaned.stock_daily (
                ticker VARCHAR,
                date DATE,
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume BIGINT,
                amount DOUBLE,
                pct_change DOUBLE,
                turnover DOUBLE,
                is_outlier BOOLEAN DEFAULT FALSE,
                cleaned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # research.financials — 基本面财务数据
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS research.financials (
                ticker VARCHAR,
                report_date DATE,
                report_type VARCHAR,
                revenue DOUBLE,
                net_profit DOUBLE,
                roe DOUBLE,
                total_assets DOUBLE,
                equity DOUBLE,
                eps DOUBLE,
                PRIMARY KEY (ticker, report_date)
            )
        """)

        # research.factors
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS research.factors (
                ticker VARCHAR,
                date DATE,
                factor_name VARCHAR,
                factor_value DOUBLE,
                neutralized_value DOUBLE,
                computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # research.events
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS research.events (
                event_id VARCHAR PRIMARY KEY,
                timestamp TIMESTAMP,
                source VARCHAR,
                event_type VARCHAR,
                ticker VARCHAR,
                company VARCHAR,
                detail TEXT,
                sentiment VARCHAR,
                impact_objects TEXT,
                time_window VARCHAR,
                confidence DOUBLE,
                tradability VARCHAR,
                tags TEXT
            )
        """)

        # research.predictions
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS research.predictions (
                prediction_id VARCHAR PRIMARY KEY,
                date DATE,
                agent VARCHAR,
                category VARCHAR,
                prediction TEXT,
                confidence DOUBLE,
                time_horizon VARCHAR,
                verify_date DATE,
                actual_result TEXT,
                verified BOOLEAN DEFAULT FALSE,
                correct BOOLEAN,
                lesson TEXT
            )
        """)

        # research.decision_memory
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS research.decision_memory (
                decision_id VARCHAR PRIMARY KEY,
                decision_date DATE,
                ticker VARCHAR,
                direction VARCHAR,
                weight DOUBLE,
                price DOUBLE,
                reason TEXT,
                signal_type VARCHAR,
                strategy VARCHAR,
                return_1d DOUBLE,
                return_3d DOUBLE,
                return_5d DOUBLE,
                return_10d DOUBLE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # published.backtest_runs
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS published.backtest_runs (
                run_id VARCHAR PRIMARY KEY,
                strategy VARCHAR,
                ticker VARCHAR,
                date_start DATE,
                date_end DATE,
                params_json TEXT,
                total_return DOUBLE,
                annual_return DOUBLE,
                sharpe_ratio DOUBLE,
                max_drawdown DOUBLE,
                win_rate DOUBLE,
                trade_count INTEGER,
                init_cash DOUBLE,
                fees DOUBLE,
                slippage DOUBLE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # published.backtest_equity
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS published.backtest_equity (
                run_id VARCHAR,
                date DATE,
                equity_value DOUBLE
            )
        """)

        # published.lessons
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS published.lessons (
                lesson_id VARCHAR PRIMARY KEY,
                date DATE,
                category VARCHAR,
                lesson TEXT,
                evidence TEXT,
                confidence DOUBLE,
                applicable TEXT,
                times_applied INTEGER DEFAULT 0,
                success_rate DOUBLE DEFAULT 0.0
            )
        """)

    # ============================================================
    # 行情数据
    # ============================================================

    def save_stock_daily(self, ticker: str, df: pd.DataFrame):
        """保存个股日线数据（写入 public + raw schema）"""
        if df.empty:
            return

        df = df.copy()
        df["ticker"] = ticker

        # 确保列存在
        for col in ["open", "high", "low", "close", "volume", "amount", "pct_change", "turnover"]:
            if col not in df.columns:
                df[col] = None

        if df.index.name == "date":
            df = df.reset_index()

        df["date"] = pd.to_datetime(df["date"]).dt.date

        # public 表（向后兼容）— 先删除该股票所有数据，再插入
        self.conn.execute("DELETE FROM stock_daily WHERE ticker = ?", [ticker])
        self.conn.execute("""
            INSERT INTO stock_daily
            SELECT ticker, date, open, high, low, close, volume, amount, pct_change, turnover
            FROM df
        """)

        # raw 分层表（新架构）— 先删除该股票所有数据，再插入
        self.conn.execute("DELETE FROM raw.stock_daily WHERE ticker = ?", [ticker])
        self.conn.execute("""
            INSERT INTO raw.stock_daily
            SELECT ticker, date, open, high, low, close, volume, amount, pct_change, turnover, CURRENT_TIMESTAMP
            FROM df
        """)

    def load_stock_daily(self, ticker: str,
                         start_date: str = None,
                         end_date: str = None) -> pd.DataFrame:
        """加载个股日线数据"""
        query = "SELECT * FROM stock_daily WHERE ticker = ?"
        params = [ticker]

        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)

        query += " ORDER BY date"
        df = self.conn.execute(query, params).fetchdf()

        if not df.empty:
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date")

        return df

    def save_index_daily(self, index_code: str, df: pd.DataFrame):
        """保存指数日线数据（写入 public + raw schema）"""
        if df.empty:
            return

        df = df.copy()
        df["index_code"] = index_code

        if df.index.name == "date":
            df = df.reset_index()

        df["date"] = pd.to_datetime(df["date"]).dt.date

        for col in ["open", "high", "low", "close", "volume"]:
            if col not in df.columns:
                df[col] = None

        # public 表 — 先删除该指数所有数据，再插入（避免索引删除问题）
        self.conn.execute("DELETE FROM index_daily WHERE index_code = ?", [index_code])
        self.conn.execute("""
            INSERT INTO index_daily
            SELECT index_code, date, open, high, low, close, volume
            FROM df
        """)

        # raw 分层表 — 先删除该指数所有数据，再插入
        self.conn.execute("DELETE FROM raw.index_daily WHERE index_code = ?", [index_code])
        self.conn.execute("""
            INSERT INTO raw.index_daily
            SELECT index_code, date, open, high, low, close, volume, CURRENT_TIMESTAMP
            FROM df
        """)

    def load_index_daily(self, index_code: str,
                         start_date: str = None,
                         end_date: str = None) -> pd.DataFrame:
        """加载指数日线数据"""
        query = "SELECT * FROM index_daily WHERE index_code = ?"
        params = [index_code]

        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)

        query += " ORDER BY date"
        df = self.conn.execute(query, params).fetchdf()

        if not df.empty:
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date")

        return df

    # ============================================================
    # 基本面数据
    # ============================================================

    def save_financials(self, ticker: str, df: pd.DataFrame):
        """
        保存财务数据到 research.financials 表。

        Args:
            ticker: 股票代码
            df: 包含 report_date, report_type, revenue, net_profit, roe,
                total_assets, equity, eps 列的 DataFrame
        """
        if df.empty:
            return

        df = df.copy()
        df["ticker"] = ticker
        if "date" in df.columns and "report_date" not in df.columns:
            df = df.rename(columns={"date": "report_date"})
        if df.index.name == "report_date" or df.index.name == "date":
            df = df.reset_index()

        df["report_date"] = pd.to_datetime(df["report_date"]).dt.date

        for col in ["report_type", "revenue", "net_profit", "roe",
                     "total_assets", "equity", "eps"]:
            if col not in df.columns:
                df[col] = None

        self.conn.execute("""
            DELETE FROM research.financials
            WHERE (ticker, report_date) IN (SELECT ticker, report_date FROM df)
        """)
        self.conn.execute("""
            INSERT INTO research.financials
            SELECT ticker, report_date, report_type, revenue, net_profit,
                   roe, total_assets, equity, eps
            FROM df
        """)

    def load_financials(self, ticker: str,
                        min_date: str = None,
                        max_date: str = None) -> pd.DataFrame:
        """加载指定股票的财务数据"""
        query = "SELECT * FROM research.financials WHERE ticker = ?"
        params = [ticker]
        if min_date:
            query += " AND report_date >= ?"
            params.append(min_date)
        if max_date:
            query += " AND report_date <= ?"
            params.append(max_date)
        query += " ORDER BY report_date"
        df = self.conn.execute(query, params).fetchdf()
        if not df.empty:
            df["report_date"] = pd.to_datetime(df["report_date"])
        return df

    def get_latest_financials(self, ticker: str) -> dict:
        """获取指定股票最新的财务数据"""
        df = self.conn.execute("""
            SELECT * FROM research.financials
            WHERE ticker = ?
            ORDER BY report_date DESC
            LIMIT 1
        """, [ticker]).fetchdf()
        if df.empty:
            return {}
        row = df.iloc[-1]
        return {
            "report_date": str(row.get("report_date", "")),
            "report_type": row.get("report_type", ""),
            "revenue": row.get("revenue"),
            "net_profit": row.get("net_profit"),
            "roe": row.get("roe"),
            "total_assets": row.get("total_assets"),
            "equity": row.get("equity"),
            "eps": row.get("eps"),
        }

    # ============================================================
    # 分层查询辅助（schema-aware）
    # ============================================================

    def load_raw_stock_daily(self, ticker: str,
                              start_date: str = None,
                              end_date: str = None) -> pd.DataFrame:
        """从 raw schema 加载原始行情"""
        query = "SELECT * FROM raw.stock_daily WHERE ticker = ?"
        params = [ticker]
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
        query += " ORDER BY date"
        df = self.conn.execute(query, params).fetchdf()
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date")
        return df

    def load_research_factors(self, ticker: str = None,
                               factor_name: str = None,
                               start_date: str = None,
                               end_date: str = None) -> pd.DataFrame:
        """从 research schema 加载因子"""
        conditions = []
        params = []
        if ticker:
            conditions.append("ticker = ?")
            params.append(ticker)
        if factor_name:
            conditions.append("factor_name = ?")
            params.append(factor_name)
        if start_date:
            conditions.append("date >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("date <= ?")
            params.append(end_date)
        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        return self.conn.execute(
            f"SELECT * FROM research.factors {where} ORDER BY date", params
        ).fetchdf()

    def load_research_decisions(self, ticker: str = None,
                                 signal_type: str = None,
                                 strategy: str = None,
                                 limit: int = 50) -> pd.DataFrame:
        """从 research schema 加载决策记录"""
        conditions = []
        params = []
        if ticker:
            conditions.append("ticker = ?")
            params.append(ticker)
        if signal_type:
            conditions.append("signal_type = ?")
            params.append(signal_type)
        if strategy:
            conditions.append("strategy = ?")
            params.append(strategy)
        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        return self.conn.execute(
            f"SELECT * FROM research.decision_memory {where} ORDER BY decision_date DESC LIMIT {limit}",
            params,
        ).fetchdf()

    def load_published_backtests(self, strategy: str = None,
                                  ticker: str = None,
                                  limit: int = 10) -> pd.DataFrame:
        """从 published schema 加载回测结果"""
        conditions = []
        params = []
        if strategy:
            conditions.append("strategy = ?")
            params.append(strategy)
        if ticker:
            conditions.append("ticker = ?")
            params.append(ticker)
        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        return self.conn.execute(
            f"SELECT * FROM published.backtest_runs {where} ORDER BY created_at DESC LIMIT {limit}",
            params,
        ).fetchdf()

    # ============================================================
    # 因子数据
    # ============================================================

    def save_factors(self, ticker: str, factor_name: str, series: pd.Series):
        """保存因子数据（写入 public + research schema）"""
        if series.empty:
            return

        df = pd.DataFrame({
            "ticker": ticker,
            "date": series.index,
            "factor_name": factor_name,
            "factor_value": series.values,
        })
        df["date"] = pd.to_datetime(df["date"]).dt.date

        # public 表
        self.conn.execute("""
            INSERT OR REPLACE INTO factors
            SELECT * FROM df
        """)

        # research 分层表 — 删除已有同 ticker+date+factor_name 记录后插入
        df["neutralized_value"] = None
        df["computed_at"] = datetime.now()
        self.conn.execute("""
            DELETE FROM research.factors
            WHERE (ticker, date, factor_name) IN (
                SELECT ticker, date, factor_name FROM df
            )
        """)
        self.conn.execute("""
            INSERT INTO research.factors
            SELECT ticker, date, factor_name, factor_value, neutralized_value, computed_at
            FROM df
        """)

    def save_neutralized_values(self, df: pd.DataFrame):
        """
        批量更新 research.factors 表的 neutralized_value。

        Args:
            df: 包含 ticker, date, factor_name, neutralized_value 列的 DataFrame
        """
        if df.empty:
            return
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"]).dt.date
        df["neutralized_value"] = df["neutralized_value"].astype("float64")

        # 逐行 UPDATE (DuckDB 不直接支持 JOIN UPDATE)
        for _, row in df.iterrows():
            self.conn.execute("""
                UPDATE research.factors
                SET neutralized_value = ?
                WHERE ticker = ? AND date = ? AND factor_name = ?
            """, [
                None if pd.isna(row["neutralized_value"]) else float(row["neutralized_value"]),
                row["ticker"],
                row["date"],
                row["factor_name"],
            ])

    def load_factors(self, ticker: str = None,
                     factor_name: str = None,
                     start_date: str = None,
                     end_date: str = None) -> pd.DataFrame:
        """加载因子数据"""
        conditions = []
        params = []

        if ticker:
            conditions.append("ticker = ?")
            params.append(ticker)
        if factor_name:
            conditions.append("factor_name = ?")
            params.append(factor_name)
        if start_date:
            conditions.append("date >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("date <= ?")
            params.append(end_date)

        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        query = f"SELECT * FROM factors {where} ORDER BY date"

        return self.conn.execute(query, params).fetchdf()

    # ============================================================
    # 事件数据
    # ============================================================

    def save_event(self, event: dict):
        """保存一个事件（写入 public + research schema）"""
        self.conn.execute("""
            INSERT OR REPLACE INTO events VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """, [
            event.get("event_id"),
            event.get("timestamp"),
            event.get("source"),
            event.get("event_type"),
            event.get("ticker"),
            event.get("company"),
            event.get("detail"),
            event.get("sentiment"),
            json.dumps(event.get("impact_objects", []), ensure_ascii=False),
            event.get("time_window"),
            event.get("confidence"),
            event.get("tradability"),
            json.dumps(event.get("tags", []), ensure_ascii=False),
        ])

        self.conn.execute("""
            INSERT OR REPLACE INTO research.events VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """, [
            event.get("event_id"),
            event.get("timestamp"),
            event.get("source"),
            event.get("event_type"),
            event.get("ticker"),
            event.get("company"),
            event.get("detail"),
            event.get("sentiment"),
            json.dumps(event.get("impact_objects", []), ensure_ascii=False),
            event.get("time_window"),
            event.get("confidence"),
            event.get("tradability"),
            json.dumps(event.get("tags", []), ensure_ascii=False),
        ])

    def load_events(self, ticker: str = None,
                    event_type: str = None,
                    start_date: str = None,
                    limit: int = 100) -> pd.DataFrame:
        """加载事件数据"""
        conditions = []
        params = []

        if ticker:
            conditions.append("ticker = ?")
            params.append(ticker)
        if event_type:
            conditions.append("event_type = ?")
            params.append(event_type)
        if start_date:
            conditions.append("timestamp >= ?")
            params.append(start_date)

        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        query = f"SELECT * FROM events {where} ORDER BY timestamp DESC LIMIT {limit}"

        return self.conn.execute(query, params).fetchdf()

    # ============================================================
    # 预测与教训
    # ============================================================

    def save_prediction(self, pred: dict):
        """保存一条预测（写入 public + research schema）"""
        self.conn.execute("""
            INSERT OR REPLACE INTO predictions VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """, [
            pred.get("prediction_id"),
            pred.get("date"),
            pred.get("agent"),
            pred.get("category"),
            pred.get("prediction"),
            pred.get("confidence"),
            pred.get("time_horizon"),
            pred.get("verify_date"),
            pred.get("actual_result"),
            pred.get("verified", False),
            pred.get("correct"),
            pred.get("lesson"),
        ])

        self.conn.execute("""
            INSERT OR REPLACE INTO research.predictions VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """, [
            pred.get("prediction_id"),
            pred.get("date"),
            pred.get("agent"),
            pred.get("category"),
            pred.get("prediction"),
            pred.get("confidence"),
            pred.get("time_horizon"),
            pred.get("verify_date"),
            pred.get("actual_result"),
            pred.get("verified", False),
            pred.get("correct"),
            pred.get("lesson"),
        ])

    def get_pending_predictions(self, current_date: date) -> pd.DataFrame:
        """获取待验证的预测"""
        return self.conn.execute("""
            SELECT * FROM predictions
            WHERE verified = FALSE AND verify_date <= ?
            ORDER BY date
        """, [current_date]).fetchdf()

    def update_prediction(self, prediction_id: str,
                          actual_result: str, correct: bool, lesson: str = ""):
        """更新预测结果"""
        self.conn.execute("""
            UPDATE predictions
            SET actual_result = ?, verified = TRUE, correct = ?, lesson = ?
            WHERE prediction_id = ?
        """, [actual_result, correct, lesson, prediction_id])

    # ============================================================
    # 回测结果持久化
    # ============================================================

    def save_backtest_run(self, result: dict) -> str:
        """
        保存一次回测运行结果。

        Args:
            result: 回测结果 dict（含 equity_curve）
                    必需字段: strategy, ticker, date_start, date_end
                    指标字段: total_return, annual_return, sharpe_ratio, etc.

        Returns:
            run_id
        """
        run_id = result.get("run_id", f"bt_{uuid.uuid4().hex[:12]}")

        # 提取权益曲线单独存储
        equity_curve = result.pop("equity_curve", None)

        # 提取drawdown_curve（不存储）
        result.pop("drawdown_curve", None)

        # 序列化 params
        params = result.get("params", {})
        params_json = json.dumps(params, ensure_ascii=False, default=str)

        bt_values = [
            run_id,
            result.get("strategy", ""),
            result.get("ticker", ""),
            result.get("date_start"),
            result.get("date_end"),
            params_json,
            float(result.get("total_return", 0)),
            float(result.get("annual_return", 0)),
            float(result.get("sharpe_ratio", 0)),
            float(result.get("max_drawdown", 0)),
            float(result.get("win_rate", 0)),
            int(result.get("trade_count", 0)),
            float(result.get("init_cash", 1_000_000)),
            float(result.get("fees", 0.001)),
            float(result.get("slippage", 0.001)),
        ]

        # public 表
        self.conn.execute("""
            INSERT INTO backtest_runs
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, bt_values)

        # published 分层表
        self.conn.execute("""
            INSERT INTO published.backtest_runs
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, bt_values)

        # 存储权益曲线
        if equity_curve is not None:
            self.save_backtest_equity(run_id, equity_curve)

        return run_id

    def save_backtest_equity(self, run_id: str, equity_curve):
        """保存回测权益曲线"""
        if equity_curve is None or (hasattr(equity_curve, 'empty') and equity_curve.empty):
            return

        df = equity_curve.reset_index()
        df.columns = ["date", "equity_value"]
        df["run_id"] = run_id
        df["date"] = pd.to_datetime(df["date"]).dt.date

        self.conn.execute("""
            INSERT INTO backtest_equity
            SELECT run_id, date, equity_value FROM df
        """)
        self.conn.execute("""
            INSERT INTO published.backtest_equity
            SELECT run_id, date, equity_value FROM df
        """)

    def load_backtest_runs(self, strategy: str = None,
                           ticker: str = None,
                           limit: int = 10) -> pd.DataFrame:
        """加载回测运行记录"""
        conditions = []
        params = []

        if strategy:
            conditions.append("strategy = ?")
            params.append(strategy)
        if ticker:
            conditions.append("ticker = ?")
            params.append(ticker)

        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        query = f"SELECT * FROM backtest_runs {where} ORDER BY created_at DESC LIMIT {limit}"

        return self.conn.execute(query, params).fetchdf()

    def load_backtest_equity(self, run_id: str) -> pd.DataFrame:
        """加载回测权益曲线"""
        return self.conn.execute("""
            SELECT date, equity_value FROM backtest_equity
            WHERE run_id = ?
            ORDER BY date
        """, [run_id]).fetchdf()

    def save_lesson(self, lesson: dict):
        """保存一条经验教训（写入 public + published schema）"""
        values = [
            lesson.get("lesson_id"),
            lesson.get("date"),
            lesson.get("category"),
            lesson.get("lesson"),
            json.dumps(lesson.get("evidence", []), ensure_ascii=False),
            lesson.get("confidence"),
            lesson.get("applicable"),
            lesson.get("times_applied", 0),
            lesson.get("success_rate", 0.0),
        ]
        self.conn.execute("""
            INSERT OR REPLACE INTO lessons VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """, values)
        self.conn.execute("""
            INSERT OR REPLACE INTO published.lessons VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """, values)

    def get_lessons(self, category: str = None,
                    min_confidence: float = 0.0) -> pd.DataFrame:
        """获取经验教训"""
        conditions = [f"confidence >= {min_confidence}"]
        if category:
            conditions.append(f"category = '{category}'")

        where = "WHERE " + " AND ".join(conditions)
        return self.conn.execute(f"""
            SELECT * FROM lessons {where}
            ORDER BY confidence DESC
        """).fetchdf()

    def get_prediction_stats(self, agent: str = None, days: int = 30) -> dict:
        """获取预测统计"""
        conditions = [f"verified = TRUE", f"date >= CURRENT_DATE - INTERVAL '{days}' DAY"]
        if agent:
            conditions.append(f"agent = '{agent}'")

        where = "WHERE " + " AND ".join(conditions)
        result = self.conn.execute(f"""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN correct THEN 1 ELSE 0 END) as correct_count
            FROM predictions {where}
        """).fetchdf()

        if result.empty:
            return {"total": 0, "correct": 0, "accuracy": 0.0}

        total = int(result.iloc[0]["total"])
        correct_val = result.iloc[0]["correct_count"]
        correct = int(correct_val) if correct_val is not None and not (isinstance(correct_val, float) and correct_val != correct_val) else 0
        return {
            "total": total,
            "correct": correct,
            "accuracy": correct / total if total > 0 else 0.0,
        }

    # ============================================================
    # 决策记忆
    # ============================================================

    def save_decision(self,
                      ticker: str,
                      direction: str,
                      weight: float,
                      reason: str,
                      signal_type: str = "generic",
                      strategy: str = "momentum",
                      decision_date: date = None,
                      price: float = None) -> str:
        """保存一条决策记录（写入 public + research schema）"""
        decision_id = f"dec_{decision_date.isoformat() if decision_date else date.today().isoformat()}_{ticker}_{uuid.uuid4().hex[:6]}"
        values = [
            decision_id,
            decision_date or date.today(),
            ticker,
            direction,
            float(weight),
            float(price) if price is not None else None,
            reason,
            signal_type,
            strategy,
        ]
        self.conn.execute("""
            INSERT OR REPLACE INTO decision_memory
            (decision_id, decision_date, ticker, direction, weight, price,
             reason, signal_type, strategy)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, values)
        self.conn.execute("""
            INSERT OR REPLACE INTO research.decision_memory
            (decision_id, decision_date, ticker, direction, weight, price,
             reason, signal_type, strategy)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, values)
        return decision_id

    def load_decisions(self,
                       ticker: str = None,
                       signal_type: str = None,
                       strategy: str = None,
                       limit: int = 50) -> pd.DataFrame:
        """加载决策记录"""
        conditions = []
        params = []
        if ticker:
            conditions.append("ticker = ?")
            params.append(ticker)
        if signal_type:
            conditions.append("signal_type = ?")
            params.append(signal_type)
        if strategy:
            conditions.append("strategy = ?")
            params.append(strategy)

        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        query = f"SELECT * FROM decision_memory {where} ORDER BY decision_date DESC LIMIT {limit}"
        return self.conn.execute(query, params).fetchdf()

    def get_decision_accuracy(self,
                              signal_type: str = None,
                              strategy: str = None,
                              days: int = 90) -> dict:
        """查询决策准确率"""
        conditions = [
            "return_1d IS NOT NULL",
            f"decision_date >= CURRENT_DATE - INTERVAL '{days}' DAY",
        ]
        params = []

        if signal_type and signal_type != "__all__":
            conditions.append("signal_type = ?")
            params.append(signal_type)
        if strategy:
            conditions.append("strategy = ?")
            params.append(strategy)

        where = "WHERE " + " AND ".join(conditions)

        if signal_type == "__all__":
            # 按信号类型分组
            df = self.conn.execute(f"""
                SELECT signal_type,
                       COUNT(*) as total,
                       SUM(CASE WHEN return_1d > 0 THEN 1 ELSE 0 END) as correct
                FROM decision_memory {where}
                GROUP BY signal_type
                ORDER BY total DESC
            """, params).fetchdf()

            if df.empty:
                return {}
            result = {}
            for _, row in df.iterrows():
                t = int(row["total"])
                c = int(row["correct"])
                result[row["signal_type"]] = {
                    "total": t,
                    "correct": c,
                    "accuracy": c / t if t > 0 else 0.0,
                }
            return result
        else:
            # 总体统计
            result = self.conn.execute(f"""
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN return_1d > 0 THEN 1 ELSE 0 END) as correct
                FROM decision_memory {where}
            """, params).fetchdf()

            if result.empty or result.iloc[0]["total"] == 0:
                return {"total": 0, "correct": 0, "accuracy": 0.0}

            total = int(result.iloc[0]["total"])
            correct = int(result.iloc[0]["correct"])
            return {"total": total, "correct": correct, "accuracy": correct / total if total > 0 else 0.0}

    def get_pending_decision_returns(self) -> pd.DataFrame:
        """获取待回填收益的决策"""
        return self.conn.execute("""
            SELECT * FROM decision_memory
            WHERE return_1d IS NULL AND return_3d IS NULL
              AND return_5d IS NULL AND return_10d IS NULL
            ORDER BY decision_date
            LIMIT 200
        """).fetchdf()

    def update_decision_returns(self, decision_id: str, returns: dict):
        """回填决策事后收益"""
        set_clauses = []
        params = []
        for label in ["return_1d", "return_3d", "return_5d", "return_10d"]:
            if label in returns and returns[label] is not None:
                set_clauses.append(f"{label} = ?")
                params.append(float(returns[label]))
            else:
                set_clauses.append(f"{label} = NULL")

        params.append(decision_id)
        self.conn.execute(f"""
            UPDATE decision_memory
            SET {', '.join(set_clauses)}
            WHERE decision_id = ?
        """, params)

    # ============================================================
    # 辅助
    # ============================================================

    def get_table_stats(self) -> dict:
        """获取各表的行数"""
        tables = ["stock_daily", "index_daily", "factors", "events", "predictions",
                   "lessons", "backtest_runs", "backtest_equity", "decision_memory"]
        stats = {}
        for table in tables:
            try:
                count = self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                stats[table] = count
            except Exception:
                stats[table] = None
        return stats

    def get_schema_stats(self) -> dict:
        """获取各分层 schema 的表行数"""
        schema_stats = {}
        for schema in ["raw", "cleaned", "research", "published"]:
            try:
                rows = self.conn.execute(f"""
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema = '{schema}'
                """).fetchall()
                schema_stats[schema] = {}
                for (table_name,) in rows:
                    count = self.conn.execute(
                        f"SELECT COUNT(*) FROM {schema}.{table_name}"
                    ).fetchone()[0]
                    schema_stats[schema][table_name] = count
            except Exception:
                schema_stats[schema] = None
        return schema_stats

    def close(self):
        """关闭连接"""
        if hasattr(self, 'conn') and self.conn is not None:
            self.conn.close()
            self.conn = None

    def __del__(self):
        self.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
