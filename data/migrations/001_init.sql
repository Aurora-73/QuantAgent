-- ============================================================
-- Migration 001: Initialize backtest persistence tables
-- ============================================================

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
);

CREATE TABLE IF NOT EXISTS backtest_equity (
    run_id VARCHAR,
    date DATE,
    equity_value DOUBLE,
    PRIMARY KEY (run_id, date)
);
