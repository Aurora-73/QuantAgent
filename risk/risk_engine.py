"""
风控引擎 — 全局风控

策略级风控在 strategies/base/strategy_base.py 的 risk_check() 中。
全局风控在这里，负责：

1. exposure_limit      总暴露限制
2. sector_limit        行业集中度限制
3. single_name_limit   单票仓位限制
4. volatility_adjust   波动率调整
5. max_drawdown_guard  最大回撤熔断
6. liquidity_filter    流动性筛选
7. event_blacklist     事件黑名单
"""
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

import pandas as pd

from configs.settings import settings


@dataclass
class RiskConfig:
    """风控配置 — 默认值从 configs/settings.py 加载"""
    max_single_position: float = settings.max_single_position
    max_sector_exposure: float = settings.max_sector_exposure
    max_total_exposure: float = settings.max_total_exposure
    max_daily_turnover: float = settings.max_daily_turnover
    max_drawdown_stop: float = settings.max_drawdown_stop
    daily_loss_limit: float = settings.daily_loss_limit
    min_daily_volume: float = settings.min_daily_volume
    volatility_cap: float = settings.volatility_cap
    blacklist: list[str] = field(default_factory=list)


@dataclass
class RiskViolation:
    """风控违规"""
    rule: str           # 违反的规则
    ticker: str         # 涉及的 ticker
    detail: str         # 详情
    severity: str       # "warning" / "block"


@dataclass
class RiskReport:
    """风控报告"""
    passed: bool
    violations: list[RiskViolation] = field(default_factory=list)
    adjusted: bool = False
    notes: str = ""


class RiskEngine:
    """
    全局风控引擎

    在交易指令执行前进行检查，确保不违反风控规则。
    """

    def __init__(self, config: RiskConfig = None):
        self.config = config or RiskConfig()

    def check_orders(self, orders: list, portfolio: list[dict],
                     market_data: pd.DataFrame = None) -> RiskReport:
        """
        检查交易指令是否违反风控规则

        Args:
            orders: 交易指令列表
            portfolio: 当前持仓 [{"ticker": ..., "weight": ..., "sector": ...}]
            market_data: 市场数据 (用于流动性检查)

        Returns:
            RiskReport
        """
        violations = []

        # 1. 黑名单检查
        violations.extend(self._check_blacklist(orders))

        # 2. 单票仓位检查
        violations.extend(self._check_single_name(orders, portfolio))

        # 3. 行业集中度检查
        violations.extend(self._check_sector_exposure(orders, portfolio))

        # 4. 换手率检查
        violations.extend(self._check_turnover(orders, portfolio))

        # 5. 流动性检查
        if market_data is not None:
            violations.extend(self._check_liquidity(orders, market_data))

        passed = not any(v.severity == "block" for v in violations)

        return RiskReport(
            passed=passed,
            violations=violations,
            notes=f"检查完成，{len(violations)} 条违规" if violations else "全部通过",
        )

    def check_drawdown(self, equity_curve: pd.Series) -> RiskReport:
        """
        检查回撤是否触发熔断

        Args:
            equity_curve: 权益曲线

        Returns:
            RiskReport
        """
        if len(equity_curve) < 2:
            return RiskReport(passed=True)

        peak = equity_curve.expanding().max()
        drawdown = (equity_curve - peak) / peak
        max_dd = drawdown.min()

        violations = []
        if max_dd < self.config.max_drawdown_stop:
            violations.append(RiskViolation(
                rule="max_drawdown",
                ticker="PORTFOLIO",
                detail=f"最大回撤 {max_dd:.2%} 超过阈值 {self.config.max_drawdown_stop:.2%}",
                severity="block",
            ))

        return RiskReport(
            passed=len(violations) == 0,
            violations=violations,
        )

    def check_daily_loss(self, daily_return: float) -> RiskReport:
        """
        检查日亏损是否触发限额

        Args:
            daily_return: 当日收益率

        Returns:
            RiskReport
        """
        violations = []
        if daily_return < self.config.daily_loss_limit:
            violations.append(RiskViolation(
                rule="daily_loss",
                ticker="PORTFOLIO",
                detail=f"日亏损 {daily_return:.2%} 超过限额 {self.config.daily_loss_limit:.2%}",
                severity="block",
            ))

        return RiskReport(
            passed=len(violations) == 0,
            violations=violations,
        )

    # ============================================================
    # 内部检查方法
    # ============================================================

    def _check_blacklist(self, orders: list) -> list[RiskViolation]:
        violations = []
        for order in orders:
            if order.ticker in self.config.blacklist:
                violations.append(RiskViolation(
                    rule="blacklist",
                    ticker=order.ticker,
                    detail=f"{order.ticker} 在黑名单中",
                    severity="block",
                ))
        return violations

    def _check_single_name(self, orders: list, portfolio: list[dict]) -> list[RiskViolation]:
        violations = []
        # 简化实现：检查目标仓位是否超过限制
        for order in orders:
            # 计算目标权重
            target_weight = abs(getattr(order, 'target_weight', 0))
            if target_weight > self.config.max_single_position:
                violations.append(RiskViolation(
                    rule="single_name",
                    ticker=order.ticker,
                    detail=f"{order.ticker} 目标仓位 {target_weight:.2%} 超过上限 {self.config.max_single_position:.2%}",
                    severity="warning",
                ))
        return violations

    def _check_sector_exposure(self, orders: list, portfolio: list[dict]) -> list[RiskViolation]:
        violations = []
        # 聚合现有持仓的行业权重
        sector_weights: dict[str, float] = {}
        for pos in portfolio:
            sector = pos.get("sector", "unknown")
            sector_weights[sector] = sector_weights.get(sector, 0) + abs(pos.get("weight", 0))

        # 聚合新订单的目标行业权重
        for order in orders:
            ticker = getattr(order, 'ticker', '') or getattr(order, 'symbol', '')
            target_weight = abs(getattr(order, 'target_weight', 0))
            # 从现有持仓中查找该 ticker 的行业
            sector = None
            for pos in portfolio:
                if pos.get("ticker") == ticker:
                    sector = pos.get("sector")
                    break
            if sector is None:
                sector = ticker  # 无行业映射时以 ticker 自身为粒度
            sector_weights[sector] = sector_weights.get(sector, 0) + target_weight

        for sector, total_weight in sector_weights.items():
            if total_weight > self.config.max_sector_exposure:
                violations.append(RiskViolation(
                    rule="sector_exposure",
                    ticker=sector,
                    detail=f"{sector} 总权重 {total_weight:.2%} 超过上限 {self.config.max_sector_exposure:.2%}",
                    severity="warning",
                ))
        return violations

    def _check_turnover(self, orders: list, portfolio: list[dict]) -> list[RiskViolation]:
        violations = []
        if not orders:
            return violations

        # 从持仓估算总组合价值
        total_value = sum(abs(pos.get("weight", 0)) for pos in portfolio) if portfolio else 1.0
        if total_value <= 0:
            total_value = 1.0

        # 计算换手量：新订单 target_weight 之和 / 2（每笔买入对应一笔卖出）
        turnover_ratio = sum(abs(getattr(o, 'target_weight', 0)) for o in orders) / 2.0

        if turnover_ratio > self.config.max_daily_turnover:
            violations.append(RiskViolation(
                rule="daily_turnover",
                ticker="PORTFOLIO",
                detail=f"日换手率 {turnover_ratio:.2%} 超过限额 {self.config.max_daily_turnover:.2%}",
                severity="warning",
            ))
        return violations

    def _check_liquidity(self, orders: list, market_data: pd.DataFrame) -> list[RiskViolation]:
        violations = []
        if "volume" not in market_data.columns:
            return violations

        for order in orders:
            if order.ticker in market_data.index:
                avg_volume = market_data.loc[order.ticker, "volume"]
                if avg_volume < self.config.min_daily_volume:
                    violations.append(RiskViolation(
                        rule="liquidity",
                        ticker=order.ticker,
                        detail=f"{order.ticker} 日均成交额 {avg_volume/1e7:.1f}千万 低于阈值 {self.config.min_daily_volume/1e7:.1f}千万",
                        severity="warning",
                    ))
        return violations
