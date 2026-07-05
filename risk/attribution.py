"""
Brinson Attribution — decompose portfolio excess return.

Components:
  - Allocation effect: sector allocation vs benchmark
  - Selection effect: stock selection within sectors
  - Interaction effect: cross term

Reference: Brinson, Hood & Beebower (1986)
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class AttributionResult:
    """Brinson 归因结果"""
    total_excess_return: float = 0.0
    allocation_effect: float = 0.0
    selection_effect: float = 0.0
    interaction_effect: float = 0.0
    sector_details: list[dict] = field(default_factory=list)

    @property
    def sum_of_parts(self) -> float:
        """各部分之和应等于超额收益"""
        return self.allocation_effect + self.selection_effect + self.interaction_effect


class BrinsonAttribution:
    """
    Brinson 收益归因

    用法:
        attr = BrinsonAttribution()
        result = attr.attribute(
            portfolio_weights={"白酒": 0.4, "新能源": 0.3, "医药": 0.3},
            benchmark_weights={"白酒": 0.3, "新能源": 0.4, "医药": 0.3},
            portfolio_returns={"白酒": 0.02, "新能源": -0.01, "医药": 0.03},
            benchmark_returns={"白酒": 0.015, "新能源": 0.005, "医药": 0.02},
        )
    """

    def attribute(self,
                  portfolio_weights: dict[str, float],
                  benchmark_weights: dict[str, float],
                  portfolio_returns: dict[str, float],
                  benchmark_returns: dict[str, float]) -> AttributionResult:
        """
        执行 Brinson 归因

        Args:
            portfolio_weights: 组合各行业权重 {sector: weight}
            benchmark_weights: 基准各行业权重
            portfolio_returns: 组合各行业收益
            benchmark_returns: 基准各行业收益

        Returns:
            AttributionResult
        """
        all_sectors = set(portfolio_weights) | set(benchmark_weights)
        result = AttributionResult()
        details = []

        total_allocation = 0.0
        total_selection = 0.0
        total_interaction = 0.0

        for sector in all_sectors:
            w_p = portfolio_weights.get(sector, 0.0)
            w_b = benchmark_weights.get(sector, 0.0)
            r_p = portfolio_returns.get(sector, 0.0)
            r_b = benchmark_returns.get(sector, 0.0)
            r_b_total = sum(benchmark_returns.values()) / max(len(benchmark_returns), 1)

            # Allocation effect: (w_p - w_b) * (r_b - r_b_total)
            alloc = (w_p - w_b) * (r_b - r_b_total)

            # Selection effect: w_b * (r_p - r_b)
            select = w_b * (r_p - r_b)

            # Interaction effect: (w_p - w_b) * (r_p - r_b)
            interact = (w_p - w_b) * (r_p - r_b)

            total_allocation += alloc
            total_selection += select
            total_interaction += interact

            details.append({
                "sector": sector,
                "portfolio_weight": round(w_p, 4),
                "benchmark_weight": round(w_b, 4),
                "portfolio_return": round(r_p, 6),
                "benchmark_return": round(r_b, 6),
                "allocation": round(alloc, 6),
                "selection": round(select, 6),
                "interaction": round(interact, 6),
            })

        result.allocation_effect = total_allocation
        result.selection_effect = total_selection
        result.interaction_effect = total_interaction
        result.sector_details = details

        # Total excess return = sum of weighted returns difference
        portfolio_total = sum(
            portfolio_weights.get(s, 0) * portfolio_returns.get(s, 0)
            for s in all_sectors
        )
        benchmark_total = sum(
            benchmark_weights.get(s, 0) * benchmark_returns.get(s, 0)
            for s in all_sectors
        )
        result.total_excess_return = portfolio_total - benchmark_total

        return result
