"""
Factor Neutralizer — remove sector/market-cap bias from factor values.

Methods:
  - Cross-sectional regression: factor ~ industry_dummies + log(market_cap)
  - Group-wise demeaning: subtract group mean within each industry

Usage:
    neutralizer = FactorNeutralizer()
    df = neutralizer.regress_neutralize(df, factor_cols=["momentum_20d", ...],
                                        industry_col="industry", cap_col="market_cap")
    df = neutralizer.group_demean(df, factor_cols=[...], group_col="industry")
"""
import numpy as np
import pandas as pd

from loguru import logger


class FactorNeutralizer:
    """
    因子中性化工具

    支持两种模式:
      1. regress_neutralize — 截面回归取残差 (sector + market cap)
      2. group_demean — 组内去均值 (sector only, 更快)
    """

    @staticmethod
    def regress_neutralize(df: pd.DataFrame,
                            factor_cols: list[str],
                            industry_col: str = "industry",
                            cap_col: str = None) -> pd.DataFrame:
        """
        截面回归中性化: factor = beta * industry_dummies + gamma * log(cap) + residual

        Args:
            df: 截面数据 (每行一只股票)
            factor_cols: 需要中性化的因子列名
            industry_col: 行业分类列名 (categorical)
            cap_col: 市值列名 (可选)，若提供则做 log(cap) 回归

        Returns:
            含 neutralized_<factor> 列的 DataFrame
        """
        df = df.copy()
        valid = df.dropna(subset=factor_cols + ([cap_col] if cap_col else []) + [industry_col])

        if len(valid) < 30:
            logger.warning(f"  中性化样本不足 ({len(valid)}), 跳过")
            for col in factor_cols:
                df[f"neutralized_{col}"] = np.nan
            return df

        # 构建行业哑变量
        dummies = pd.get_dummies(valid[industry_col], prefix="ind", drop_first=True)
        X_cols = list(dummies.columns)

        X_meta = pd.DataFrame(index=valid.index)

        # 添加市值
        if cap_col and cap_col in valid.columns:
            valid_cap = valid[cap_col].copy()
            # 预防极端值
            log_cap = np.where(valid_cap > 0, np.log(valid_cap), 0)
            # 标准化
            log_cap = (log_cap - log_cap.mean()) / (log_cap.std() + 1e-8)
            X_meta["log_cap"] = log_cap
            X_cols.append("log_cap")

        # 拼接设计矩阵 (含截距)
        X = np.column_stack([np.ones(len(dummies))] + [dummies[c].values for c in dummies.columns]
                            + [X_meta[c].values for c in X_meta.columns if c in X_meta.columns])
        # X_meta columns already in X_cols, dummies added above

        for col in factor_cols:
            if col not in valid.columns:
                df[f"neutralized_{col}"] = np.nan
                continue

            y = valid[col].values
            # OLS: beta = (X'X)^(-1) X'y
            try:
                beta = np.linalg.lstsq(X, y, rcond=None)[0]
                y_pred = X @ beta
                residual = y - y_pred
                result = pd.Series(np.nan, index=df.index)
                result.loc[valid.index] = residual
                df[f"neutralized_{col}"] = result
            except np.linalg.LinAlgError as e:
                logger.warning(f"  因子 {col} 中性化回归失败: {e}")
                df[f"neutralized_{col}"] = np.nan

        return df

    @staticmethod
    def group_demean(df: pd.DataFrame,
                      factor_cols: list[str],
                      group_col: str = "industry") -> pd.DataFrame:
        """
        组内去均值中性化 (快速版)

        在每个 group 内减去该组的因子均值。

        Args:
            df: 截面数据
            factor_cols: 因子列
            group_col: 分组列 (如 industry)

        Returns:
            含 neutralized_<factor> 列的 DataFrame
        """
        df = df.copy()

        for col in factor_cols:
            if col not in df.columns:
                df[f"neutralized_{col}"] = np.nan
                continue

            group_means = df.groupby(group_col)[col].transform("mean")
            df[f"neutralized_{col}"] = df[col] - group_means

        return df

    @staticmethod
    def time_series_neutralize(panel: pd.DataFrame,
                                factor_cols: list[str],
                                industry_col: str = "industry",
                                cap_col: str = None,
                                method: str = "regress") -> pd.DataFrame:
        """
        面板数据中性化 (按日期逐截面执行)

        Args:
            panel: 面板数据 (必须包含 date 列)
            factor_cols: 因子列
            industry_col: 行业列
            cap_col: 市值列
            method: "regress" 或 "demean"

        Returns:
            含 neutralized_<factor> 列的 DataFrame
        """
        if "date" not in panel.columns:
            # 尝试从 index 恢复
            if isinstance(panel.index, pd.DatetimeIndex):
                panel = panel.reset_index().rename(columns={"index": "date"})
            else:
                raise ValueError("panel 必须包含 'date' 列或 DatetimeIndex")

        neutralizer = (
            FactorNeutralizer.regress_neutralize
            if method == "regress"
            else FactorNeutralizer.group_demean
        )

        results = []
        dates = panel["date"].unique()
        for d in sorted(dates):
            cross_section = panel[panel["date"] == d].copy()
            # Drop date for per-date call
            neutralized = neutralizer(
                cross_section.drop(columns=["date"]),
                factor_cols,
                industry_col,
                cap_col,
            )
            neutralized["date"] = d
            results.append(neutralized)

        return pd.concat(results, ignore_index=True) if results else pd.DataFrame()
