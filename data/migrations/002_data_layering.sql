-- ============================================================
-- Migration 002: Data layering — raw / cleaned / research / published
-- ============================================================
-- Migrates the flat table structure into domain-separated schemas
-- while preserving backward compatibility via public views.
-- ============================================================

-- Step 1: Create schemas
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS cleaned;
CREATE SCHEMA IF NOT EXISTS research;
CREATE SCHEMA IF NOT EXISTS published;

-- ============================================================
-- Step 2: Create schema tables
-- ============================================================

-- raw layer — data as ingested
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
);

CREATE TABLE IF NOT EXISTS raw.index_daily (
    index_code VARCHAR,
    date DATE,
    open DOUBLE,
    high DOUBLE,
    low DOUBLE,
    close DOUBLE,
    volume BIGINT,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- cleaned layer — outliers removed, forward-filled, neutralized
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
);

-- research layer — analysis artefacts
CREATE TABLE IF NOT EXISTS research.factors (
    ticker VARCHAR,
    date DATE,
    factor_name VARCHAR,
    factor_value DOUBLE,
    neutralized_value DOUBLE,
    computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

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
);

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
);

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
);

-- published layer — backtest results & lessons
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
);

CREATE TABLE IF NOT EXISTS published.backtest_equity (
    run_id VARCHAR,
    date DATE,
    equity_value DOUBLE
);

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
);

-- ============================================================
-- Step 3: Copy data from public tables (if they exist)
-- ============================================================

INSERT INTO raw.stock_daily
SELECT *, CURRENT_TIMESTAMP FROM stock_daily
WHERE EXISTS (SELECT 1 FROM stock_daily LIMIT 1)
  AND NOT EXISTS (SELECT 1 FROM raw.stock_daily LIMIT 1);

INSERT INTO raw.index_daily
SELECT *, CURRENT_TIMESTAMP FROM index_daily
WHERE EXISTS (SELECT 1 FROM index_daily LIMIT 1)
  AND NOT EXISTS (SELECT 1 FROM raw.index_daily LIMIT 1);

INSERT INTO research.factors
SELECT *, NULL, CURRENT_TIMESTAMP FROM factors
WHERE EXISTS (SELECT 1 FROM factors LIMIT 1)
  AND NOT EXISTS (SELECT 1 FROM research.factors LIMIT 1);

INSERT INTO research.events
SELECT * FROM events
WHERE EXISTS (SELECT 1 FROM events LIMIT 1)
  AND NOT EXISTS (SELECT 1 FROM research.events LIMIT 1);

INSERT INTO research.predictions
SELECT * FROM predictions
WHERE EXISTS (SELECT 1 FROM predictions LIMIT 1)
  AND NOT EXISTS (SELECT 1 FROM research.predictions LIMIT 1);

INSERT INTO research.decision_memory
SELECT * FROM decision_memory
WHERE EXISTS (SELECT 1 FROM decision_memory LIMIT 1)
  AND NOT EXISTS (SELECT 1 FROM research.decision_memory LIMIT 1);

INSERT INTO published.backtest_runs
SELECT * FROM backtest_runs
WHERE EXISTS (SELECT 1 FROM backtest_runs LIMIT 1)
  AND NOT EXISTS (SELECT 1 FROM published.backtest_runs LIMIT 1);

INSERT INTO published.backtest_equity
SELECT * FROM backtest_equity
WHERE EXISTS (SELECT 1 FROM backtest_equity LIMIT 1)
  AND NOT EXISTS (SELECT 1 FROM published.backtest_equity LIMIT 1);

INSERT INTO published.lessons
SELECT * FROM lessons
WHERE EXISTS (SELECT 1 FROM lessons LIMIT 1)
  AND NOT EXISTS (SELECT 1 FROM published.lessons LIMIT 1);

-- ============================================================
-- Step 4: Add primary keys / indices on tables that need them
-- ============================================================

-- raw.stock_daily doesn't have a PK to allow duplicate ingestion;
-- add a covering index for common query patterns
CREATE INDEX IF NOT EXISTS idx_raw_stock_daily_ticker_date
    ON raw.stock_daily (ticker, date);

CREATE INDEX IF NOT EXISTS idx_raw_index_daily_code_date
    ON raw.index_daily (index_code, date);

CREATE INDEX IF NOT EXISTS idx_research_factors_ticker_date
    ON research.factors (ticker, date);

CREATE INDEX IF NOT EXISTS idx_research_decision_date
    ON research.decision_memory (decision_date DESC);
