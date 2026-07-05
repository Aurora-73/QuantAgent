"""
数据清洗器 — 三道防线保障数据质量

数据层最重要的是：
  - 时间对齐
  - 去重
  - 缺失值处理
  - 复权/拆分/合并
  - 统一 ticker / symbol / 事件 ID

数据问题传播链:
  原始数据 → NaN/极端值 → 因子计算失真 → 权重全nan → 风控异常 → 策略崩溃

三道防线:
  1. 缺失值填充: 避免 NaN 在计算中传播
  2. 极值裁剪: 避免极端值扭曲因子分布
  3. 降级路径: 关键特征缺失时提供 fallback
"""
import pandas as pd
import numpy as np
from loguru import logger


class DataCleaner:
    """数据清洗器"""

    @staticmethod
    def clean_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
        """
        清洗 OHLCV 数据

        处理：
        1. 去重
        2. 排序
        3. 缺失值
        4. 异常值
        """
        df = df.copy()

        # 去重
        if df.index.name == "date" or "date" in df.columns:
            df = df.drop_duplicates(subset=["date"] if "date" in df.columns else None)

        # 排序
        if "date" in df.columns:
            df = df.sort_values("date")
        elif isinstance(df.index, pd.DatetimeIndex):
            df = df.sort_index()

        # 检查必要列
        required = ["open", "high", "low", "close", "volume"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"缺少必要列: {missing}")

        # 删除全为 NaN 的行
        df = df.dropna(subset=["close"], how="all")

        # 价格为 0 或负数 → NaN
        for col in ["open", "high", "low", "close"]:
            df[col] = df[col].where(df[col] > 0)

        # 成交量为负 → 0
        df["volume"] = df["volume"].clip(lower=0)

        # OHLC 逻辑校验: high >= low
        invalid = df["high"] < df["low"]
        if invalid.any():
            df.loc[invalid, ["high", "low"]] = np.nan

        return df

    @staticmethod
    def handle_missing(df: pd.DataFrame, method: str = "ffill",
                       limit: int = 5) -> pd.DataFrame:
        """
        处理缺失值

        Args:
            df: 数据
            method: ffill (前向填充) / bfill / interpolate
            limit: 最大连续填充天数
        """
        df = df.copy()
        if method == "ffill":
            df = df.ffill(limit=limit)
        elif method == "bfill":
            df = df.bfill(limit=limit)
        elif method == "interpolate":
            df = df.interpolate(method="time", limit=limit)
        return df

    @staticmethod
    def detect_outliers(series: pd.Series,
                        method: str = "zscore",
                        threshold: float = 3.0) -> pd.Series:
        """
        检测异常值

        Args:
            series: 数据序列
            method: zscore / iqr
            threshold: 阈值

        Returns:
            布尔序列 (True = 异常)
        """
        if method == "zscore":
            z = (series - series.mean()) / series.std()
            return z.abs() > threshold
        elif method == "iqr":
            q1 = series.quantile(0.25)
            q3 = series.quantile(0.75)
            iqr = q3 - q1
            lower = q1 - threshold * iqr
            upper = q3 + threshold * iqr
            return (series < lower) | (series > upper)
        return pd.Series(False, index=series.index)

    @staticmethod
    def adjust_for_splits(df: pd.DataFrame,
                          split_ratio: pd.Series = None) -> pd.DataFrame:
        """
        复权处理

        Args:
            df: OHLCV 数据
            split_ratio: 拆股/合股比率序列

        Returns:
            复权后的数据
        """
        df = df.copy()
        if split_ratio is not None:
            for col in ["open", "high", "low", "close"]:
                df[col] = df[col] * split_ratio
            df["volume"] = df["volume"] / split_ratio
        return df

    @staticmethod
    def drop_infinite(df: pd.DataFrame) -> pd.DataFrame:
        """移除无穷值"""
        original_count = len(df)
        df = df.replace([np.inf, -np.inf], np.nan)
        df = df.dropna(how="all")
        dropped = original_count - len(df)
        if dropped > 0:
            logger.debug(f"移除 {dropped} 行全缺失数据")
        return df

    @staticmethod
    def fill_missing(df: pd.DataFrame, method: str = "median",
                     fill_value: float = None) -> pd.DataFrame:
        """
        填充缺失值

        Args:
            df: 输入 DataFrame
            method: "median"(横截面中位数) / "mean"(均值) / "constant"(常数)
            fill_value: 常数填充时使用的值

        Returns:
            填充后的 DataFrame
        """
        df = df.copy()
        numeric_cols = df.select_dtypes(include=[np.number]).columns

        for col in numeric_cols:
            missing_ratio = df[col].isna().sum() / len(df)
            if missing_ratio > 0.5:
                logger.warning(f"列 {col} 缺失率 {missing_ratio:.1%}，建议检查数据源")

            if method == "median":
                fill_val = df[col].median()
            elif method == "mean":
                fill_val = df[col].mean()
            elif method == "constant":
                fill_val = fill_value if fill_value is not None else 0.0
            else:
                fill_val = df[col].median()

            df[col] = df[col].fillna(fill_val)

        return df

    @staticmethod
    def winsorize(df: pd.DataFrame, lower: float = 0.01,
                  upper: float = 0.99) -> pd.DataFrame:
        """
        Winsorize 极值裁剪

        将低于 lower 分位数和高于 upper 分位数的值替换为分位数值

        Args:
            df: 输入 DataFrame
            lower: 低分位数 (0-1)
            upper: 高分位数 (0-1)

        Returns:
            裁剪后的 DataFrame
        """
        df = df.copy()
        numeric_cols = df.select_dtypes(include=[np.number]).columns

        for col in numeric_cols:
            if df[col].nunique() < 10:
                continue

            lower_val = df[col].quantile(lower)
            upper_val = df[col].quantile(upper)

            clipped_lower = (df[col] < lower_val).sum()
            clipped_upper = (df[col] > upper_val).sum()

            if clipped_lower > 0 or clipped_upper > 0:
                logger.debug(f"列 {col} 裁剪: 低{int(lower*100)}%={clipped_lower}个, "
                            f"高{int((1-upper)*100)}%={clipped_upper}个")

            df[col] = np.clip(df[col], lower_val, upper_val)

        return df

    @staticmethod
    def clip_by_range(df: pd.DataFrame, ranges: dict) -> pd.DataFrame:
        """
        按指定范围裁剪

        Args:
            df: 输入 DataFrame
            ranges: {column: (min_val, max_val)} 字典

        Returns:
            裁剪后的 DataFrame
        """
        df = df.copy()
        for col, (min_val, max_val) in ranges.items():
            if col not in df.columns:
                continue

            clipped_lower = (df[col] < min_val).sum()
            clipped_upper = (df[col] > max_val).sum()

            if clipped_lower > 0 or clipped_upper > 0:
                logger.debug(f"列 {col} 范围裁剪: <{min_val}={clipped_lower}, >{max_val}={clipped_upper}")

            df[col] = np.clip(df[col], min_val, max_val)

        return df

    @staticmethod
    def handle_pe_ratio(df: pd.DataFrame, pe_col: str = "pe_ttm") -> pd.DataFrame:
        """
        处理 PE 比率特殊情况

        PE 可能为负(亏损)或超大(微利)，需要特殊处理:
        - 负数 PE 替换为行业中位数或置为 NaN
        - 超大 PE(>1000) 裁剪为合理范围
        """
        df = df.copy()
        if pe_col not in df.columns:
            return df

        negative_count = (df[pe_col] < 0).sum()
        if negative_count > 0:
            logger.debug(f"PE 负数: {negative_count} 个，替换为中位数")
            positive_pe = df[df[pe_col] > 0][pe_col]
            if not positive_pe.empty:
                median_pe = positive_pe.median()
                df.loc[df[pe_col] < 0, pe_col] = median_pe

        df[pe_col] = np.clip(df[pe_col], 0, 200)
        return df

    @staticmethod
    def macro_feature_fallback(df: pd.DataFrame, macro_cols: list = None,
                               fallback_value: float = 0.0) -> pd.DataFrame:
        """
        宏观特征 NaN 降级处理

        关键宏观特征(如行业轮动)出现 nan 时，提供可解释的 fallback 路径

        Args:
            df: 输入 DataFrame
            macro_cols: 需要降级处理的列名列表
            fallback_value: 降级时使用的值

        Returns:
            处理后的 DataFrame
        """
        df = df.copy()
        if macro_cols is None:
            macro_cols = ["industry_rotation", "market_sentiment",
                          "liquidity", "volatility"]

        for col in macro_cols:
            if col not in df.columns:
                continue

            nan_count = df[col].isna().sum()
            if nan_count > 0:
                logger.info(f"宏观特征 {col} 出现 {nan_count} 个 NaN，降级为 {fallback_value}")
                df[col] = df[col].fillna(fallback_value)

        return df

    @staticmethod
    def clean_daily_data(df: pd.DataFrame) -> pd.DataFrame:
        """
        清洗日线数据的标准流程

        适用于 get_stock_daily 返回的数据
        """
        if df.empty:
            return df

        df = DataCleaner.clean_ohlcv(df)
        df = DataCleaner.drop_infinite(df)
        df = DataCleaner.fill_missing(df, method="median")

        range_config = {
            "pct_chg": (-20, 20),
            "turnover": (0, 50),
        }
        df = DataCleaner.clip_by_range(df, range_config)

        return df

    @staticmethod
    def clean_valuation_data(df: pd.DataFrame) -> pd.DataFrame:
        """
        清洗估值数据的标准流程

        适用于 get_batch_valuation 返回的数据
        """
        if df.empty:
            return df

        df = DataCleaner.drop_infinite(df)
        df = DataCleaner.handle_pe_ratio(df, "pe_ttm")
        df = DataCleaner.fill_missing(df, method="median")
        df = DataCleaner.winsorize(df, lower=0.02, upper=0.98)

        range_config = {
            "pe_ttm": (0, 200),
            "pb": (0, 30),
            "total_mv": (0, None),
        }
        df = DataCleaner.clip_by_range(df, range_config)

        return df

    @staticmethod
    def clean_factor_data(df: pd.DataFrame, macro_cols: list = None) -> pd.DataFrame:
        """
        清洗因子数据的标准流程

        适用于策略 prepare_features 阶段的数据
        """
        if df.empty:
            return df

        df = DataCleaner.drop_infinite(df)
        df = DataCleaner.fill_missing(df, method="median")
        df = DataCleaner.winsorize(df, lower=0.01, upper=0.99)
        df = DataCleaner.macro_feature_fallback(df, macro_cols)

        return df
