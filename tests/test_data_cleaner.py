"""
数据清洗器单元测试

测试覆盖:
  - 缺失值填充
  - 极值裁剪 (Winsorize)
  - 范围裁剪 (Clip)
  - PE 比率处理
  - 宏观特征 fallback
  - 标准化清洗流程
"""
import pandas as pd
import numpy as np
import pytest

from data.cleaner import DataCleaner


class TestDropInfinite:
    def test_removes_infinite_values(self):
        df = pd.DataFrame({"a": [1, np.inf, 3, -np.inf, 5]})
        result = DataCleaner.drop_infinite(df)
        assert not np.any(np.isinf(result["a"]))

    def test_does_not_remove_valid_values(self):
        df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
        result = DataCleaner.drop_infinite(df)
        assert len(result) == 3


class TestFillMissing:
    def test_median_fill(self):
        df = pd.DataFrame({"a": [1, 2, np.nan, 4, 5]})
        result = DataCleaner.fill_missing(df, method="median")
        assert result["a"].isna().sum() == 0
        assert result["a"].iloc[2] == 3

    def test_mean_fill(self):
        df = pd.DataFrame({"a": [1, 2, np.nan, 4, 5]})
        result = DataCleaner.fill_missing(df, method="mean")
        assert result["a"].isna().sum() == 0
        assert result["a"].iloc[2] == 3

    def test_constant_fill(self):
        df = pd.DataFrame({"a": [1, 2, np.nan, 4, 5]})
        result = DataCleaner.fill_missing(df, method="constant", fill_value=0)
        assert result["a"].iloc[2] == 0

    def test_handles_high_missing_ratio(self):
        df = pd.DataFrame({"a": [np.nan] * 6 + [1, 2, 3, 4]})
        result = DataCleaner.fill_missing(df, method="median")
        assert result["a"].isna().sum() == 0


class TestWinsorize:
    def test_clips_extreme_values(self):
        df = pd.DataFrame({"a": list(range(1, 21)) + [100]})
        result = DataCleaner.winsorize(df, lower=0.1, upper=0.9)
        assert result["a"].max() <= 20
        assert result["a"].min() >= 1

    def test_preserves_central_values(self):
        df = pd.DataFrame({"a": [10, 20, 30, 40, 50]})
        result = DataCleaner.winsorize(df, lower=0.1, upper=0.9)
        assert result.equals(df)


class TestClipByRange:
    def test_clips_by_specified_range(self):
        df = pd.DataFrame({"a": [-10, 5, 15, 25], "b": [1, 2, 3, 4]})
        result = DataCleaner.clip_by_range(df, {"a": (0, 20)})
        assert result["a"].min() == 0
        assert result["a"].max() == 20
        assert result["b"].equals(pd.Series([1, 2, 3, 4]))

    def test_ignores_nonexistent_columns(self):
        df = pd.DataFrame({"a": [1, 2, 3]})
        result = DataCleaner.clip_by_range(df, {"nonexistent": (0, 10)})
        assert result.equals(df)


class TestHandlePeRatio:
    def test_replaces_negative_pe(self):
        df = pd.DataFrame({"pe_ttm": [-10, 15, 20, np.nan, -5]})
        result = DataCleaner.handle_pe_ratio(df)
        assert result["pe_ttm"].min() >= 0

    def test_clips_extreme_pe(self):
        df = pd.DataFrame({"pe_ttm": [1000, 2000, 3000]})
        result = DataCleaner.handle_pe_ratio(df)
        assert result["pe_ttm"].max() == 200


class TestMacroFeatureFallback:
    def test_fills_nan_with_fallback_value(self):
        df = pd.DataFrame({"industry_rotation": [0.5, np.nan, 0.8], "market_sentiment": [np.nan, 0.3, 0.6]})
        result = DataCleaner.macro_feature_fallback(df, fallback_value=0.0)
        assert result["industry_rotation"].isna().sum() == 0
        assert result["market_sentiment"].isna().sum() == 0
        assert result["industry_rotation"].iloc[1] == 0.0
        assert result["market_sentiment"].iloc[0] == 0.0

    def test_preserves_valid_values(self):
        df = pd.DataFrame({"industry_rotation": [0.5, 0.6, 0.7]})
        result = DataCleaner.macro_feature_fallback(df)
        assert result.equals(df)


class TestCleanDailyData:
    def test_returns_cleaned_data(self):
        df = pd.DataFrame({
            "open": [10, 11, np.nan, 13, 14],
            "high": [12, 13, 14, np.inf, 16],
            "low": [8, 9, 10, 11, -np.inf],
            "close": [11, 12, 13, 14, 15],
            "volume": [1000, 2000, 3000, 4000, 5000],
            "pct_change": [-30, 5, 3, 2, 30]
        })
        result = DataCleaner.clean_daily_data(df)
        assert result.isna().sum().sum() == 0
        assert not np.any(np.isinf(result.values))
        assert result["pct_change"].min() >= -20
        assert result["pct_change"].max() <= 20


class TestCleanValuationData:
    def test_returns_cleaned_valuation(self):
        df = pd.DataFrame({
            "pe_ttm": [-10, 15, 2000, np.nan, 25],
            "pb": [0.5, 1.0, np.nan, 3.0, 100],
            "total_mv": [100, 200, 300, np.nan, 500]
        })
        result = DataCleaner.clean_valuation_data(df)
        assert result.isna().sum().sum() == 0
        assert result["pe_ttm"].max() == 200
        assert result["pe_ttm"].min() >= 0
        assert result["pb"].max() <= 30


class TestCleanFactorData:
    def test_returns_cleaned_factor_data(self):
        df = pd.DataFrame({
            "momentum": [0.5, np.nan, 0.8, 100, -100],
            "value": [0.3, 0.4, np.nan, 0.6, 0.7],
            "industry_rotation": [np.nan, 0.5, 0.6, np.nan, 0.8]
        })
        result = DataCleaner.clean_factor_data(df)
        assert result.isna().sum().sum() == 0