"""
因子评估器

评估维度：
  - IC (Information Coefficient): 因子与未来收益的相关性
  - ICIR: IC 的稳定性 (IC均值 / IC标准差)
  - 分组收益: 按因子分组后各组的收益差异
  - 换手率: 因子信号的稳定性
  - 衰减速度: 因子预测力的持续时间
"""
import numpy as np
import pandas as pd


class FactorEvaluator:
    """因子评估器"""

    @staticmethod
    def evaluate_ic(factor: pd.Series,
                    forward_returns: pd.Series,
                    method: str = "spearman") -> dict:
        """
        计算 IC 统计

        Args:
            factor: 因子值序列
            forward_returns: 未来收益率序列
            method: 相关系数计算方法 ("spearman" / "pearson")

        Returns:
            IC 统计结果
        """
        valid = pd.DataFrame({
            "factor": factor,
            "returns": forward_returns
        }).dropna()

        if len(valid) < 30:
            return {"ic": np.nan, "icir": np.nan, "ic_positive_ratio": np.nan}

        if method == "spearman":
            # Spearman = Pearson on ranks
            ranked_factor = valid["factor"].rank()
            ranked_returns = valid["returns"].rank()
            ic_series = ranked_factor.rolling(60).corr(ranked_returns)
        else:
            ic_series = valid["factor"].rolling(60).corr(valid["returns"])

        ic_series = ic_series.dropna()

        if len(ic_series) == 0:
            return {"ic": np.nan, "icir": np.nan, "ic_positive_ratio": np.nan}

        ic_mean = ic_series.mean()
        ic_std = ic_series.std()
        icir = ic_mean / (ic_std + 1e-8)
        ic_positive_ratio = (ic_series > 0).mean()

        return {
            "ic": ic_mean,
            "icir": icir,
            "ic_std": ic_std,
            "ic_positive_ratio": ic_positive_ratio,
            "ic_series": ic_series,
        }

    @staticmethod
    def evaluate_groups(factor: pd.Series,
                        forward_returns: pd.Series,
                        n_groups: int = 5) -> dict:
        """
        分组评估

        Args:
            factor: 因子值
            forward_returns: 未来收益率
            n_groups: 分组数

        Returns:
            分组收益统计
        """
        valid = pd.DataFrame({
            "factor": factor,
            "returns": forward_returns
        }).dropna()

        if len(valid) < n_groups * 10:
            return {"group_returns": None, "long_short": np.nan}

        try:
            valid["group"] = pd.qcut(valid["factor"], n_groups,
                                     labels=range(n_groups), duplicates="drop")
        except ValueError:
            return {"group_returns": None, "long_short": np.nan}

        group_returns = valid.groupby("group")["returns"].agg(["mean", "std", "count"])
        group_returns.columns = ["mean_return", "std_return", "count"]

        long_short = group_returns["mean_return"].iloc[-1] - group_returns["mean_return"].iloc[0]

        # 单调性检验
        monotonic = all(group_returns["mean_return"].diff().dropna() > 0) or \
                    all(group_returns["mean_return"].diff().dropna() < 0)

        return {
            "group_returns": group_returns,
            "long_short": long_short,
            "monotonic": monotonic,
        }

    @staticmethod
    def evaluate_turnover(factor: pd.Series,
                          holding_period: int = 5) -> dict:
        """
        换手率评估

        Args:
            factor: 因子值
            holding_period: 持仓周期

        Returns:
            换手率统计
        """
        # 因子排名变化
        rank = factor.rank(pct=True)
        rank_change = rank.diff(holding_period).abs()
        avg_turnover = rank_change.mean()

        return {
            "avg_turnover": avg_turnover,
            "stability": 1 - avg_turnover,  # 稳定性 = 1 - 换手率
        }

    @staticmethod
    def evaluate_decay(factor: pd.Series,
                       close: pd.Series,
                       max_lag: int = 20) -> dict:
        """
        因子衰减评估

        Args:
            factor: 因子值
            close: 收盘价
            max_lag: 最大滞后天数

        Returns:
            各滞后期的 IC
        """
        returns = close.pct_change().shift(-1)
        decay = {}

        for lag in range(1, max_lag + 1):
            fwd_ret = close.pct_change(lag).shift(-lag)
            valid = pd.DataFrame({"factor": factor, "returns": fwd_ret}).dropna()
            if len(valid) > 30:
                ic = valid["factor"].corr(valid["returns"])
                decay[lag] = ic
            else:
                decay[lag] = np.nan

        return {
            "decay": decay,
            "half_life": FactorEvaluator._calc_half_life(decay),
        }

    @staticmethod
    def full_report(factor: pd.Series,
                    close: pd.Series,
                    forward_period: int = 5,
                    n_groups: int = 5) -> dict:
        """
        完整因子评估报告

        Args:
            factor: 因子值
            close: 收盘价
            forward_period: 未来收益周期
            n_groups: 分组数

        Returns:
            完整评估报告
        """
        forward_returns = close.pct_change(forward_period).shift(-forward_period)

        ic_result = FactorEvaluator.evaluate_ic(factor, forward_returns)
        group_result = FactorEvaluator.evaluate_groups(factor, forward_returns, n_groups)
        turnover_result = FactorEvaluator.evaluate_turnover(factor)
        decay_result = FactorEvaluator.evaluate_decay(factor, close)

        # 综合评分
        score = 0
        if not np.isnan(ic_result.get("icir", np.nan)):
            score += min(abs(ic_result["icir"]) / 2, 3)  # ICIR 贡献最多3分
        if not np.isnan(group_result.get("long_short", np.nan)):
            score += min(abs(group_result["long_short"]) * 20, 3)  # 多空收益贡献最多3分
        if group_result.get("monotonic", False):
            score += 2  # 单调性加分
        score = min(score, 10)

        return {
            "ic": ic_result,
            "groups": group_result,
            "turnover": turnover_result,
            "decay": decay_result,
            "overall_score": score,
            "grade": "A" if score >= 7 else "B" if score >= 5 else "C" if score >= 3 else "D",
        }

    @staticmethod
    def _calc_half_life(decay: dict) -> int:
        """计算因子半衰期"""
        if not decay:
            return 0

        initial_ic = None
        for lag in sorted(decay.keys()):
            ic = decay[lag]
            if not np.isnan(ic):
                if initial_ic is None:
                    initial_ic = abs(ic)
                elif abs(ic) < initial_ic / 2:
                    return lag

        return max(decay.keys())
