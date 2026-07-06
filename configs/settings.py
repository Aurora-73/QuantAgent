"""
Unified configuration management via pydantic-settings.

Loads from:
  1. .env file (secrets: API keys, send keys, tokens)
  2. configs/app.yaml (structured config: risk params, factor params, etc.)
  3. Environment variables (highest priority)

Usage:
    from configs.settings import settings

    api_key = settings.openai_api_key
    risk = settings.max_single_position
"""
from pathlib import Path
from typing import Optional

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _yaml_config_source(settings_cls) -> dict:
    """Load structured config from YAML file."""
    yaml_path = Path(__file__).parent / "app.yaml"
    if yaml_path.exists():
        with open(yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return _flatten_dict(data)
    return {}


def _flatten_dict(d: dict, prefix: str = "") -> dict:
    """Flatten nested dict for pydantic-settings: {a: {b: 1}} -> {a_b: 1}."""
    result = {}
    for k, v in d.items():
        key = f"{prefix}{k}" if prefix else k
        if isinstance(v, dict) and not any(isinstance(vv, (list, dict)) for vv in v.values()):
            result.update(_flatten_dict(v, f"{key}_"))
        else:
            result[key] = v
    return result


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ============================================================
    # Paths
    # ============================================================
    db_path: str = "data/quant.duckdb"
    knowledge_dir: str = "knowledge"
    log_dir: str = "logs"
    log_level: str = "INFO"
    reference_dir: str = "../_reference"

    # ============================================================
    # Data
    # ============================================================
    default_start_date: str = "20200101"
    default_universe: str = "csi300"
    data_request_sleep: float = 0.3
    default_index_code: str = "000300"

    # ============================================================
    # Scheduler
    # ============================================================
    schedule_data_update_time: str = "15:30"
    schedule_research_time: str = "16:00"
    schedule_timezone: str = "Asia/Shanghai"

    # ============================================================
    # LLM — 已废弃（2026-07-06）
    #
    # 项目定位调整为 MCP Server，LLM 调用由外部 Agent 提供，
    # 不在 quant-system 内部调用 LLM API。以下配置保留以兼容
    # 旧代码，实际不再使用。
    # ============================================================
    openai_api_key: Optional[str] = None
    openai_base_url: Optional[str] = None
    llm_model: str = "gpt-4o"
    llm_temperature: float = 0.3
    llm_max_tokens: int = 4096
    llm_extraction_temperature: float = 0.2
    llm_extraction_max_tokens: int = 2048

    # ============================================================
    # Notification (ServerChan / SendChan)
    # ============================================================
    sendchan_sendkey_me: Optional[str] = None
    sendchan_sendkey_daisen: Optional[str] = None
    sendchan_api_url: str = "https://sctapi.ftqq.com/{sendkey}.send"
    sendchan_status_url: str = "https://sctapi.ftqq.com/push"

    # ============================================================
    # Risk
    # ============================================================
    max_single_position: float = 0.05
    max_sector_exposure: float = 0.20
    max_total_exposure: float = 1.00
    max_daily_turnover: float = 0.10
    max_drawdown_stop: float = -0.05
    daily_loss_limit: float = -0.02
    min_daily_volume: float = 50_000_000  # 5000万
    volatility_cap: float = 3.0
    consecutive_losses_limit: int = 5
    risk_free_rate: float = 0.02

    # ============================================================
    # Strategy defaults
    # ============================================================
    momentum_lookback: int = 20
    momentum_entry_threshold: float = 0.05
    momentum_exit_threshold: float = -0.02
    momentum_rsi_overbought: int = 70
    momentum_rsi_oversold: int = 30
    momentum_max_position_pct: float = 0.05
    momentum_target_positions: int = 10
    momentum_holding_min_days: int = 3
    momentum_holding_max_days: int = 20
    momentum_holding_typical_days: int = 10

    # ============================================================
    # Backtest
    # ============================================================
    backtest_init_cash: float = 1_000_000
    backtest_fees: float = 0.001
    backtest_slippage: float = 0.001
    backtest_freq: str = "B"
    backtest_train_window: int = 252
    backtest_test_window: int = 63
    backtest_step: int = 21
    backtest_topk: int = 50
    backtest_n_drop: int = 5

    # ============================================================
    # Factor evaluation
    # ============================================================
    factor_ic_min_samples: int = 30
    factor_ic_rolling_window: int = 60
    factor_group_count: int = 5
    factor_decay_max_lag: int = 20
    factor_decay_min_samples: int = 30
    factor_holding_period: int = 5
    factor_lookahead_period: int = 5

    # ============================================================
    # News / Events
    # ============================================================
    news_tier1_weight: float = 1.0
    news_tier2_weight: float = 0.8
    news_tier3_weight: float = 0.6
    news_tier4_weight: float = 0.4
    news_confidence_boost_per_source: float = 0.1
    news_confidence_boost_cap: float = 0.3
    news_dedup_time_window_hours: int = 24
    news_dedup_similarity_threshold: float = 0.8
    news_high_confidence_threshold: float = 0.7
    news_multi_source_threshold: int = 2

    # ============================================================
    # Qlib integration
    # ============================================================
    qlib_provider_uri: str = "~/.qlib/qlib_data/cn_data"
    qlib_lgbm_loss: str = "mse"
    qlib_lgbm_early_stopping: int = 50
    qlib_lgbm_num_boost: int = 1000
    qlib_lstm_hidden_size: int = 64
    qlib_lstm_num_layers: int = 2
    qlib_lstm_epochs: int = 200
    qlib_lstm_lr: float = 0.001
    qlib_train_start: str = "2020-01-01"
    qlib_train_end: str = "2023-12-31"
    qlib_limit_threshold: float = 0.095
    qlib_open_cost: float = 0.0005
    qlib_close_cost: float = 0.0015
    qlib_min_cost: int = 5

    @classmethod
    def customise_sources(cls, init_settings, env_settings, file_secret_settings):
        """Load order: YAML → .env → environment variables (highest priority)."""
        return (
            init_settings,
            _yaml_config_source,
            env_settings,
            file_secret_settings,
        )


settings = Settings()


# ============================================================
# User lookup helper
# ============================================================
def get_notification_users() -> list[dict]:
    """Get notification user list from settings."""
    users = []
    if settings.sendchan_sendkey_me:
        users.append({"name": "me", "sendkey": settings.sendchan_sendkey_me})
    if settings.sendchan_sendkey_daisen:
        users.append({"name": "daisen", "sendkey": settings.sendchan_sendkey_daisen})
    return users
