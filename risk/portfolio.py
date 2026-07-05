"""
组合优化器 — 基于 Riskfolio-Lib

职责：
  - 最优权重计算
  - 风险平价
  - 均值方差优化
  - 波动率目标仓位
  - 再平衡建议

第一版先做三种：
  1. 等权 (Equal Weight)
  2. 风险平价 (Risk Parity)
  3. 波动率目标 (Volatility Targeting)
"""
import numpy as np
import pandas as pd

from loguru import logger

HAS_RISKFOLIO = False


class PortfolioOptimizer:
    """组合优化器"""

    @staticmethod
    def equal_weight(tickers: list[str]) -> dict[str, float]:
        """
        等权分配

        最简单但有效的策略：
        - 每只股票等权
        - 不需要任何估计
        - 天然分散化
        """
        n = len(tickers)
        if n == 0:
            return {}
        w = 1.0 / n
        return {t: w for t in tickers}

    @staticmethod
    def risk_parity(returns: pd.DataFrame) -> dict[str, float]:
        """
        风险平价

        使每个资产对组合风险的贡献相等。
        波动率高的资产分配更少权重。
        """
        if returns.empty:
            return {}

        tickers = returns.columns.tolist()

        if HAS_RISKFOLIO:
            try:
                port = rp.Portfolio(returns=returns)
                port.assets_stats(method_mu="hist", method_cov="hist")
                w = port.rp_optimization(model="Classic", rm="MV", rf=0, b=None)
                weights = w["weights"].to_dict()
                return {t: float(weights.get(t, 0)) for t in tickers}
            except Exception as e:
                logger.warning(f"  Riskfolio 风险平价失败: {e}，使用简化版本")

        # 简化版本：逆波动率加权
        vols = returns.std()
        inv_vol = 1 / (vols + 1e-8)
        weights = inv_vol / inv_vol.sum()
        return weights.to_dict()

    @staticmethod
    def min_variance(returns: pd.DataFrame) -> dict[str, float]:
        """
        最小方差组合

        最小化组合方差，不考虑收益。
        """
        if returns.empty:
            return {}

        tickers = returns.columns.tolist()

        if HAS_RISKFOLIO:
            try:
                port = rp.Portfolio(returns=returns)
                port.assets_stats(method_mu="hist", method_cov="hist")
                w = port.optimization(model="Classic", rm="MV", obj="MinRisk", rf=0)
                weights = w["weights"].to_dict()
                return {t: float(weights.get(t, 0)) for t in tickers}
            except Exception as e:
                logger.warning(f"  Riskfolio 最小方差失败: {e}，使用简化版本")

        # 简化版本
        return PortfolioOptimizer.risk_parity(returns)

    @staticmethod
    def max_sharpe(returns: pd.DataFrame,
                   risk_free_rate: float = 0.02) -> dict[str, float]:
        """
        最大夏普比率组合
        """
        if returns.empty:
            return {}

        tickers = returns.columns.tolist()

        if HAS_RISKFOLIO:
            try:
                port = rp.Portfolio(returns=returns)
                port.assets_stats(method_mu="hist", method_cov="hist")
                w = port.optimization(model="Classic", rm="MV", obj="Sharpe",
                                      rf=risk_free_rate)
                weights = w["weights"].to_dict()
                return {t: float(weights.get(t, 0)) for t in tickers}
            except Exception as e:
                logger.warning(f"  Riskfolio 最大夏普失败: {e}，使用简化版本")

        return PortfolioOptimizer.risk_parity(returns)

    @staticmethod
    def volatility_target(returns: pd.DataFrame,
                          target_vol: float = 0.15) -> dict[str, float]:
        """
        波动率目标

        先做等权，然后缩放使组合波动率等于目标。

        Args:
            returns: 收益率 DataFrame
            target_vol: 目标年化波动率 (如 0.15 = 15%)
        """
        tickers = returns.columns.tolist()
        n = len(tickers)
        if n == 0:
            return {}

        # 先等权
        equal_w = np.array([1.0 / n] * n)

        # 计算组合波动率
        cov = returns.cov() * 252
        port_vol = np.sqrt(equal_w @ cov.values @ equal_w)

        # 缩放
        scale = target_vol / (port_vol + 1e-8)
        scale = min(scale, 1.0)  # 不加杠杆

        adjusted_w = equal_w * scale
        return {t: float(w) for t, w in zip(tickers, adjusted_w)}

    @staticmethod
    def risk_budget(returns: pd.DataFrame,
                   budget: dict[str, float] = None) -> dict[str, float]:
        """
        风险预算

        按指定的风险预算分配权重。

        Args:
            returns: 收益率
            budget: {ticker: risk_budget} 如 {"A": 0.5, "B": 0.5}
        """
        if returns.empty:
            return {}

        tickers = returns.columns.tolist()
        if budget is None:
            budget = {t: 1.0 / len(tickers) for t in tickers}

        if HAS_RISKFOLIO:
            try:
                port = rp.Portfolio(returns=returns)
                port.assets_stats(method_mu="hist", method_cov="hist")
                b = [budget.get(t, 0) for t in tickers]
                w = port.rp_optimization(model="Classic", rm="MV", rf=0, b=b)
                weights = w["weights"].to_dict()
                return {t: float(weights.get(t, 0)) for t in tickers}
            except Exception as e:
                logger.warning(f"  Riskfolio 风险预算失败: {e}")

        return PortfolioOptimizer.risk_parity(returns)

    @staticmethod
    def rebalance(current_weights: dict[str, float],
                  target_weights: dict[str, float],
                  total_value: float,
                  threshold: float = 0.01) -> list[dict]:
        """
        计算再平衡交易

        Args:
            current_weights: 当前权重
            target_weights: 目标权重
            total_value: 总资产
            threshold: 再平衡阈值 (偏离多少才交易)

        Returns:
            交易列表 [{"ticker": ..., "action": "buy"/"sell", "value": ...}]
        """
        all_tickers = set(list(current_weights.keys()) + list(target_weights.keys()))
        trades = []

        for ticker in all_tickers:
            current = current_weights.get(ticker, 0)
            target = target_weights.get(ticker, 0)
            diff = target - current

            if abs(diff) < threshold:
                continue

            action = "buy" if diff > 0 else "sell"
            value = abs(diff) * total_value

            trades.append({
                "ticker": ticker,
                "action": action,
                "weight_change": diff,
                "value": value,
            })

        return trades
