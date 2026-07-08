"""
DuckDB performance optimizations module

Contains:
- Index creation functions
- View definitions
- Batch operations
"""
import pandas as pd
from datetime import datetime


def create_indexes(conn):
    """Create indexes for common queries"""
    indexes = [
        ("idx_factors_ticker_date", "research.factors (ticker, date)"),
        ("idx_factors_factor_name", "research.factors (factor_name)"),
        ("idx_stock_daily_ticker_date", "raw.stock_daily (ticker, date)"),
        ("idx_financials_ticker_date", "research.financials (ticker, report_date)"),
        ("idx_events_ticker_timestamp", "research.events (ticker, timestamp)"),
        ("idx_decision_memory_ticker_date", "research.decision_memory (ticker, decision_date)"),
    ]
    for name, columns in indexes:
        try:
            conn.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {columns}")
        except Exception:
            pass


def create_views(conn):
    """Create materialized views for common aggregations"""
    views = [
        """
        CREATE VIEW IF NOT EXISTS v_factor_summary AS
        SELECT 
            factor_name,
            COUNT(*) as total_rows,
            MIN(date) as min_date,
            MAX(date) as max_date,
            COUNT(DISTINCT ticker) as ticker_count
        FROM research.factors
        GROUP BY factor_name
        """,
        """
        CREATE VIEW IF NOT EXISTS v_daily_market_summary AS
        SELECT 
            date,
            COUNT(DISTINCT ticker) as stock_count,
            AVG(pct_change) as avg_pct_change,
            STDDEV(pct_change) as std_pct_change,
            SUM(volume) as total_volume
        FROM raw.stock_daily
        GROUP BY date
        ORDER BY date
        """,
        """
        CREATE VIEW IF NOT EXISTS v_backtest_comparison AS
        SELECT 
            strategy,
            ticker,
            MAX(created_at) as latest_run,
            AVG(sharpe_ratio) as avg_sharpe,
            MIN(max_drawdown) as best_drawdown,
            COUNT(*) as run_count
        FROM published.backtest_runs
        GROUP BY strategy, ticker
        """,
    ]
    for view_sql in views:
        try:
            conn.execute(view_sql)
        except Exception:
            pass


def apply_optimizations(conn):
    """Apply all optimizations"""
    create_indexes(conn)
    create_views(conn)


def save_factors_batch(conn, ticker, factors_df):
    """
    Batch save multiple factors for a ticker.

    Args:
        conn: DuckDB connection
        ticker: Stock ticker symbol
        factors_df: DataFrame with factor columns
    """
    if factors_df.empty:
        return

    exclude_cols = {"open", "high", "low", "close", "volume", "amount", 
                   "pct_change", "turnover", "revenue", "net_profit", "roe", "eps"}
    factor_cols = [c for c in factors_df.columns if c not in exclude_cols]

    rows = []
    for date_idx, row in factors_df.iterrows():
        for factor_name in factor_cols:
            value = row.get(factor_name)
            if value is not None and not (isinstance(value, float) and value != value):
                rows.append({
                    "ticker": ticker,
                    "date": date_idx,
                    "factor_name": factor_name,
                    "factor_value": float(value),
                })

    if not rows:
        return

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"]).dt.date

    conn.execute("""
        INSERT OR REPLACE INTO factors
        SELECT ticker, date, factor_name, factor_value
        FROM df
    """)

    df["neutralized_value"] = None
    df["computed_at"] = datetime.now()
    conn.execute("""
        INSERT OR REPLACE INTO research.factors
        SELECT ticker, date, factor_name, factor_value, neutralized_value, computed_at
        FROM df
    """)


def batch_update_neutralized_values(conn, df):
    """
    Batch update neutralized_value using JOIN UPDATE.

    Args:
        conn: DuckDB connection
        df: DataFrame with ticker, date, factor_name, neutralized_value
    """
    if df.empty:
        return
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df["neutralized_value"] = df["neutralized_value"].astype("float64")

    temp_df = df[["ticker", "date", "factor_name", "neutralized_value"]].copy()
    temp_df = temp_df.dropna(subset=["neutralized_value"])

    if temp_df.empty:
        return

    conn.execute("""
        UPDATE research.factors
        SET neutralized_value = temp.neutralized_value
        FROM temp_df as temp
        WHERE research.factors.ticker = temp.ticker
          AND research.factors.date = temp.date
          AND research.factors.factor_name = temp.factor_name
    """)