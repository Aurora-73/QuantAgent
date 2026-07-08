"""
因子计算引擎

内置因子分类：
  - 价格因子：动量、反转、均线偏离
  - 成交量因子：量比、成交量动量
  - 波动率因子：历史波动率、ATR
  - 基本面因子：ROE、营收增速（需要额外数据）
  - AI 因子：情绪评分、事件评分（来自 LLM 模块）

所有因子输出为 pd.Series，index 为日期。
"""
import numpy as np
import pandas as pd

from loguru import logger


class FactorEngine:
    """
    因子计算引擎

    使用方式：
        engine = FactorEngine()
        df = engine.compute_all(df)  # 计算所有因子
        df = engine.compute(df, ["momentum_20d", "reversal_5d"])  # 计算指定因子
        df = engine.compute(df, params={"momentum": {"lookback": 10}})  # 带参数计算
    """

    # 因子注册表：name -> (function, description, default_params)
    FACTORY_REGISTRY = {}

    @classmethod
    def register(cls, name: str, description: str = "", **default_params):
        """注册因子的装饰器，支持默认参数"""
        def decorator(func):
            cls.FACTORY_REGISTRY[name] = (func, description, default_params)
            return func
        return decorator

    def compute(self, df: pd.DataFrame,
                factor_names: list[str] = None,
                params: dict = None) -> pd.DataFrame:
        """
        计算指定因子

        Args:
            df: OHLCV DataFrame (必须包含 open, high, low, close, volume)
            factor_names: 因子名称列表，None 则计算全部
            params: 因子参数覆盖，格式: {"factor_group": {"param_name": value}}

        Returns:
            添加了因子列的 DataFrame
        """
        df = df.copy()
        params = params or {}

        if factor_names is None:
            factor_names = list(self.FACTORY_REGISTRY.keys())

        for name in factor_names:
            if name in self.FACTORY_REGISTRY:
                func, _, default_params = self.FACTORY_REGISTRY[name]
                try:
                    factor_params = default_params.copy()
                    group_name = name.split("_")[0] if "_" in name else name
                    if group_name in params:
                        factor_params.update(params[group_name])
                    df[name] = func(df, **factor_params)
                except Exception as e:
                    logger.error(f"  因子 {name} 计算失败: {e}")
                    df[name] = np.nan
            else:
                logger.error(f"  未知因子: {name}")

        return df

    def compute_all(self, df: pd.DataFrame, params: dict = None) -> pd.DataFrame:
        """计算所有已注册因子"""
        return self.compute(df, params=params)

    def list_factors(self) -> dict[str, str]:
        """列出所有已注册因子"""
        return {name: desc for name, (_, desc, _) in self.FACTORY_REGISTRY.items()}

    def get_factor_params(self, name: str) -> dict:
        """获取因子的默认参数"""
        if name in self.FACTORY_REGISTRY:
            _, _, params = self.FACTORY_REGISTRY[name]
            return params
        return {}


# ============================================================
# 价格因子
# ============================================================

@FactorEngine.register("momentum_5d", "5日动量 (5日收益率)", lookback=5)
def momentum_5d(df, lookback=5):
    return df["close"].pct_change(lookback)

@FactorEngine.register("momentum_10d", "10日动量", lookback=10)
def momentum_10d(df, lookback=10):
    return df["close"].pct_change(lookback)

@FactorEngine.register("momentum_20d", "20日动量", lookback=20)
def momentum_20d(df, lookback=20):
    return df["close"].pct_change(lookback)

@FactorEngine.register("momentum_60d", "60日动量", lookback=60)
def momentum_60d(df, lookback=60):
    return df["close"].pct_change(lookback)

@FactorEngine.register("reversal_5d", "5日反转 (负动量)", lookback=5)
def reversal_5d(df, lookback=5):
    return -df["close"].pct_change(lookback)

@FactorEngine.register("reversal_20d", "20日反转", lookback=20)
def reversal_20d(df, lookback=20):
    return -df["close"].pct_change(lookback)

@FactorEngine.register("ma_deviation_5", "收盘价偏离5日均线", window=5)
def ma_deviation_5(df, window=5):
    ma = df["close"].rolling(window).mean()
    return (df["close"] - ma) / ma

@FactorEngine.register("ma_deviation_20", "收盘价偏离20日均线", window=20)
def ma_deviation_20(df, window=20):
    ma = df["close"].rolling(window).mean()
    return (df["close"] - ma) / ma

@FactorEngine.register("ma_deviation_60", "收盘价偏离60日均线", window=60)
def ma_deviation_60(df, window=60):
    ma = df["close"].rolling(window).mean()
    return (df["close"] - ma) / ma

@FactorEngine.register("high_low_ratio", "20日最高/最低比", window=20)
def high_low_ratio(df, window=20):
    high_20 = df["high"].rolling(window).max()
    low_20 = df["low"].rolling(window).min()
    return (df["close"] - low_20) / (high_20 - low_20 + 1e-8)


# ============================================================
# 成交量因子
# ============================================================

@FactorEngine.register("volume_ratio_5d", "5日量比", window=5)
def volume_ratio_5d(df, window=5):
    avg_vol = df["volume"].rolling(window).mean()
    return df["volume"] / (avg_vol + 1)

@FactorEngine.register("volume_ratio_20d", "20日量比", window=20)
def volume_ratio_20d(df, window=20):
    avg_vol = df["volume"].rolling(window).mean()
    return df["volume"] / (avg_vol + 1)

@FactorEngine.register("volume_momentum", "成交量动量 (5日成交量变化)", lookback=5)
def volume_momentum(df, lookback=5):
    return df["volume"].pct_change(lookback)

@FactorEngine.register("turnover_ma5", "5日平均换手率", window=5)
def turnover_ma5(df, window=5):
    if "turnover" in df.columns:
        return df["turnover"].rolling(window).mean()
    return pd.Series(np.nan, index=df.index)

@FactorEngine.register("price_volume_corr", "价量相关性 (20日)", window=20)
def price_volume_corr(df, window=20):
    return df["close"].pct_change().rolling(window).corr(df["volume"].pct_change())


# ============================================================
# 波动率因子
# ============================================================

@FactorEngine.register("volatility_20d", "20日历史波动率", window=20)
def volatility_20d(df, window=20):
    return df["close"].pct_change().rolling(window).std() * np.sqrt(252)

@FactorEngine.register("volatility_60d", "60日历史波动率", window=60)
def volatility_60d(df, window=60):
    return df["close"].pct_change().rolling(window).std() * np.sqrt(252)

@FactorEngine.register("atr_14", "14日ATR (归一化)", window=14)
def atr_14(df, window=14):
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift(1)).abs()
    low_close = (df["low"] - df["close"].shift(1)).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = tr.rolling(window).mean()
    return atr / df["close"]  # 归一化

@FactorEngine.register("realized_skew", "20日实现偏度", window=20)
def realized_skew(df, window=20):
    returns = df["close"].pct_change()
    return returns.rolling(window).skew()

@FactorEngine.register("realized_kurt", "20日实现峰度", window=20)
def realized_kurt(df, window=20):
    returns = df["close"].pct_change()
    return returns.rolling(window).kurt()


# ============================================================
# 技术指标因子
# ============================================================

@FactorEngine.register("rsi_14", "14日RSI", window=14)
def rsi_14(df, window=14):
    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0).rolling(window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window).mean()
    rs = gain / (loss + 1e-8)
    return 100 - (100 / (1 + rs))

@FactorEngine.register("macd_diff", "MACD 差值", fast=12, slow=26, signal=9)
def macd_diff(df, fast=12, slow=26, signal=9):
    ema12 = df["close"].ewm(span=fast).mean()
    ema26 = df["close"].ewm(span=slow).mean()
    macd = ema12 - ema26
    signal_line = macd.ewm(span=signal).mean()
    return macd - signal_line

@FactorEngine.register("bollinger_position", "布林带位置", window=20, num_std=2)
def bollinger_position(df, window=20, num_std=2):
    ma = df["close"].rolling(window).mean()
    std = df["close"].rolling(window).std()
    upper = ma + num_std * std
    lower = ma - num_std * std
    return (df["close"] - lower) / (upper - lower + 1e-8)


# ============================================================
# 基本面因子 (需要 financials 数据合并到 df)
# ============================================================

@FactorEngine.register("roe", "净资产收益率")
def roe(df):
    return df.get("roe", pd.Series(np.nan, index=df.index))

@FactorEngine.register("pe_ttm", "市盈率 (TTM)")
def pe_ttm(df):
    eps = df.get("eps", pd.Series(np.nan, index=df.index))
    return df["close"] / (eps + 1e-8)

@FactorEngine.register("revenue_growth", "营收同比增速 (季度)")
def revenue_growth(df):
    rev = df.get("revenue", pd.Series(np.nan, index=df.index))
    # 取最新有值的点做同比，forward-fill 后使用约 60 日前的值近似上期
    return rev / (rev.shift(60) + 1e-8) - 1

@FactorEngine.register("profit_growth", "净利润同比增速 (季度)")
def profit_growth(df):
    np_val = df.get("net_profit", pd.Series(np.nan, index=df.index))
    return np_val / (np_val.shift(60) + 1e-8) - 1


# ============================================================
# 复合因子
# ============================================================

@FactorEngine.register("quality_momentum", "质量动量 (动量/波动率)", lookback=20)
def quality_momentum(df, lookback=20):
    mom = df["close"].pct_change(lookback)
    vol = df["close"].pct_change().rolling(lookback).std()
    return mom / (vol + 1e-8)

@FactorEngine.register("smart_money", "聪明资金 (大单占比 proxy)", window=10)
def smart_money(df, window=10):
    # 用价量关系近似：上涨放量 = 聪明资金流入
    returns = df["close"].pct_change()
    vol_change = df["volume"].pct_change()
    return (returns * vol_change).rolling(window).mean()
