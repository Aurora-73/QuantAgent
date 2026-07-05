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
    """

    # 因子注册表：name -> (function, description)
    FACTORY_REGISTRY = {}

    @classmethod
    def register(cls, name: str, description: str = ""):
        """注册因子的装饰器"""
        def decorator(func):
            cls.FACTORY_REGISTRY[name] = (func, description)
            return func
        return decorator

    def compute(self, df: pd.DataFrame,
                factor_names: list[str] = None) -> pd.DataFrame:
        """
        计算指定因子

        Args:
            df: OHLCV DataFrame (必须包含 open, high, low, close, volume)
            factor_names: 因子名称列表，None 则计算全部

        Returns:
            添加了因子列的 DataFrame
        """
        df = df.copy()

        if factor_names is None:
            factor_names = list(self.FACTORY_REGISTRY.keys())

        for name in factor_names:
            if name in self.FACTORY_REGISTRY:
                func, _ = self.FACTORY_REGISTRY[name]
                try:
                    df[name] = func(df)
                except Exception as e:
                    logger.error(f"  因子 {name} 计算失败: {e}")
                    df[name] = np.nan
            else:
                logger.error(f"  未知因子: {name}")

        return df

    def compute_all(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算所有已注册因子"""
        return self.compute(df)

    def list_factors(self) -> dict[str, str]:
        """列出所有已注册因子"""
        return {name: desc for name, (_, desc) in self.FACTORY_REGISTRY.items()}


# ============================================================
# 价格因子
# ============================================================

@FactorEngine.register("momentum_5d", "5日动量 (5日收益率)")
def momentum_5d(df):
    return df["close"].pct_change(5)

@FactorEngine.register("momentum_10d", "10日动量")
def momentum_10d(df):
    return df["close"].pct_change(10)

@FactorEngine.register("momentum_20d", "20日动量")
def momentum_20d(df):
    return df["close"].pct_change(20)

@FactorEngine.register("momentum_60d", "60日动量")
def momentum_60d(df):
    return df["close"].pct_change(60)

@FactorEngine.register("reversal_5d", "5日反转 (负动量)")
def reversal_5d(df):
    return -df["close"].pct_change(5)

@FactorEngine.register("reversal_20d", "20日反转")
def reversal_20d(df):
    return -df["close"].pct_change(20)

@FactorEngine.register("ma_deviation_5", "收盘价偏离5日均线")
def ma_deviation_5(df):
    ma = df["close"].rolling(5).mean()
    return (df["close"] - ma) / ma

@FactorEngine.register("ma_deviation_20", "收盘价偏离20日均线")
def ma_deviation_20(df):
    ma = df["close"].rolling(20).mean()
    return (df["close"] - ma) / ma

@FactorEngine.register("ma_deviation_60", "收盘价偏离60日均线")
def ma_deviation_60(df):
    ma = df["close"].rolling(60).mean()
    return (df["close"] - ma) / ma

@FactorEngine.register("high_low_ratio", "20日最高/最低比")
def high_low_ratio(df):
    high_20 = df["high"].rolling(20).max()
    low_20 = df["low"].rolling(20).min()
    return (df["close"] - low_20) / (high_20 - low_20 + 1e-8)


# ============================================================
# 成交量因子
# ============================================================

@FactorEngine.register("volume_ratio_5d", "5日量比")
def volume_ratio_5d(df):
    avg_vol = df["volume"].rolling(5).mean()
    return df["volume"] / (avg_vol + 1)

@FactorEngine.register("volume_ratio_20d", "20日量比")
def volume_ratio_20d(df):
    avg_vol = df["volume"].rolling(20).mean()
    return df["volume"] / (avg_vol + 1)

@FactorEngine.register("volume_momentum", "成交量动量 (5日成交量变化)")
def volume_momentum(df):
    return df["volume"].pct_change(5)

@FactorEngine.register("turnover_ma5", "5日平均换手率")
def turnover_ma5(df):
    if "turnover" in df.columns:
        return df["turnover"].rolling(5).mean()
    return pd.Series(np.nan, index=df.index)

@FactorEngine.register("price_volume_corr", "价量相关性 (20日)")
def price_volume_corr(df):
    return df["close"].pct_change().rolling(20).corr(df["volume"].pct_change())


# ============================================================
# 波动率因子
# ============================================================

@FactorEngine.register("volatility_20d", "20日历史波动率")
def volatility_20d(df):
    return df["close"].pct_change().rolling(20).std() * np.sqrt(252)

@FactorEngine.register("volatility_60d", "60日历史波动率")
def volatility_60d(df):
    return df["close"].pct_change().rolling(60).std() * np.sqrt(252)

@FactorEngine.register("atr_14", "14日ATR (归一化)")
def atr_14(df):
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift(1)).abs()
    low_close = (df["low"] - df["close"].shift(1)).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    return atr / df["close"]  # 归一化

@FactorEngine.register("realized_skew", "20日实现偏度")
def realized_skew(df):
    returns = df["close"].pct_change()
    return returns.rolling(20).skew()

@FactorEngine.register("realized_kurt", "20日实现峰度")
def realized_kurt(df):
    returns = df["close"].pct_change()
    return returns.rolling(20).kurt()


# ============================================================
# 技术指标因子
# ============================================================

@FactorEngine.register("rsi_14", "14日RSI")
def rsi_14(df):
    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / (loss + 1e-8)
    return 100 - (100 / (1 + rs))

@FactorEngine.register("macd_diff", "MACD 差值")
def macd_diff(df):
    ema12 = df["close"].ewm(span=12).mean()
    ema26 = df["close"].ewm(span=26).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9).mean()
    return macd - signal

@FactorEngine.register("bollinger_position", "布林带位置")
def bollinger_position(df):
    ma = df["close"].rolling(20).mean()
    std = df["close"].rolling(20).std()
    upper = ma + 2 * std
    lower = ma - 2 * std
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

@FactorEngine.register("quality_momentum", "质量动量 (动量/波动率)")
def quality_momentum(df):
    mom = df["close"].pct_change(20)
    vol = df["close"].pct_change().rolling(20).std()
    return mom / (vol + 1e-8)

@FactorEngine.register("smart_money", "聪明资金 (大单占比 proxy)")
def smart_money(df):
    # 用价量关系近似：上涨放量 = 聪明资金流入
    returns = df["close"].pct_change()
    vol_change = df["volume"].pct_change()
    return (returns * vol_change).rolling(10).mean()
