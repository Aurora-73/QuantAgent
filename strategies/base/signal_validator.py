"""
SignalValidator — validates signals before they reach the risk engine.

Checks:
  1. Historical win rate — has this signal pattern been successful before?
  2. Factor consistency — do driving and warning factors agree?
  3. Market regime match — is the signal appropriate for current conditions?

Reference: SignalFlow Meta-Labeling pattern.

Usage:
    validator = SignalValidator()
    result = validator.validate(weight_vector, regime, factor_data, ticker)
"""
from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd
from loguru import logger


@dataclass
class ValidationResult:
    """Result of signal validation."""
    passed: bool
    confidence_multiplier: float = 1.0  # Applied to signal confidence
    checks: dict = field(default_factory=dict)
    # {check_name: {passed: bool, detail: str, adjustment: float}}
    warnings: list[str] = field(default_factory=list)
    recommendation: str = ""


class SignalValidator:
    """
    Validates trading signals across multiple dimensions.

    In Phase B, uses stub decision memory (in-memory cache).
    Phase C will connect to decision_memory DuckDB table for real history.
    """

    def __init__(self):
        self._decision_cache: dict[str, list[dict]] = {}  # ticker → [{direction, return, ...}]

    def validate(self, weight_vector,  # WeightVector
                 regime: str = "unknown",
                 factor_data: dict = None,
                 ticker: str = None) -> ValidationResult:
        """
        Validate a weight vector signal.

        Args:
            weight_vector: WeightVector from strategy
            regime: Current market regime
            factor_data: Dict of factor_name → value
            ticker: Ticker to validate for (if weight vector covers multiple)

        Returns:
            ValidationResult with pass/fail and confidence adjustment
        """
        factor_data = factor_data or {}

        # If no weights or all near zero, skip validation
        if weight_vector.is_empty():
            return ValidationResult(
                passed=True, confidence_multiplier=1.0,
                checks={"no_signal": {"passed": True, "detail": "无信号"}},
                recommendation="hold",
            )

        checks = {}
        warnings = []
        multiplier = 1.0

        # 1. Historical win rate check
        win_check = self._check_historical_winrate(weight_vector, ticker)
        checks["historical_winrate"] = win_check
        if not win_check["passed"]:
            multiplier *= 0.7
            warnings.append(f"历史胜率低: {win_check['detail']}")

        # 2. Factor consistency check
        factor_check = self._check_factor_consistency(weight_vector, factor_data)
        checks["factor_consistency"] = factor_check
        if not factor_check["passed"]:
            multiplier *= 0.8
            warnings.append(f"因子不一致: {factor_check['detail']}")

        # 3. Market regime match
        regime_check = self._check_regime_match(weight_vector, regime)
        checks["regime_match"] = regime_check
        if not regime_check["passed"]:
            multiplier *= 0.85
            warnings.append(f"市场状态不匹配: {regime_check['detail']}")

        # 4. Concentration check (if multiple tickers)
        conc_check = self._check_concentration(weight_vector)
        checks["concentration"] = conc_check
        if not conc_check["passed"]:
            multiplier *= 0.9
            warnings.append(f"集中度警告: {conc_check['detail']}")

        passed = all(c["passed"] for c in checks.values())

        return ValidationResult(
            passed=passed,
            confidence_multiplier=round(multiplier, 3),
            checks=checks,
            warnings=warnings,
            recommendation=self._make_recommendation(passed, multiplier),
        )

    def _check_historical_winrate(self, weight_vector,
                                  ticker: str = None) -> dict:
        """Check historical performance of similar signals."""
        # In Phase B: stub. Phase C: real decision_memory lookup.
        ticker = ticker or (list(weight_vector.weights.keys())[0] if weight_vector.weights else "unknown")

        history = self._decision_cache.get(ticker, [])
        if len(history) < 5:
            return {"passed": True, "detail": "历史数据不足，跳过往期检查", "adjustment": 1.0}

        wins = sum(1 for h in history if h.get("return", 0) > 0)
        win_rate = wins / len(history)

        if win_rate < 0.35:
            return {"passed": False, "detail": f"历史胜率仅{win_rate:.1%}（{len(history)}次）", "adjustment": 0.7}
        elif win_rate < 0.45:
            return {"passed": True, "detail": f"历史胜率偏低{win_rate:.1%}（{len(history)}次）", "adjustment": 0.9}
        else:
            return {"passed": True, "detail": f"历史胜率{win_rate:.1%}（{len(history)}次）", "adjustment": 1.0}

    def _check_factor_consistency(self, weight_vector,
                                  factor_data: dict) -> dict:
        """Check if driving and warning factors agree."""
        if not factor_data:
            return {"passed": True, "detail": "无因子数据", "adjustment": 1.0}

        # Determine signal direction from weights
        avg_weight = np.mean(list(weight_vector.weights.values()))
        direction = "bullish" if avg_weight > 0.1 else ("bearish" if avg_weight < -0.1 else "neutral")

        if direction == "neutral":
            return {"passed": True, "detail": "信号中性", "adjustment": 1.0}

        # Check momentum factors
        mom_factors = {k: v for k, v in factor_data.items() if "momentum" in k.lower()}
        rsi_factors = {k: v for k, v in factor_data.items() if "rsi" in k.lower()}

        consistent = 0
        inconsistent = 0

        for k, v in mom_factors.items():
            if direction == "bullish" and v > 0:
                consistent += 1
            elif direction == "bearish" and v < 0:
                consistent += 1
            elif abs(v) > 0.01:
                inconsistent += 1

        for k, v in rsi_factors.items():
            if direction == "bullish" and v < 70:  # Not overbought
                consistent += 1
            elif direction == "bearish" and v > 30:  # Not oversold
                consistent += 1
            else:
                inconsistent += 1

        if inconsistent > consistent:
            return {"passed": False,
                    "detail": f"驱动因子({consistent}个)与警告因子({inconsistent}个)矛盾",
                    "adjustment": 0.8}
        return {"passed": True,
                "detail": f"因子一致性通过 ({consistent}驱动, {inconsistent}警告)",
                "adjustment": 1.0}

    def _check_regime_match(self, weight_vector, regime: str) -> dict:
        """Check if the signal type matches the current market regime."""
        avg_weight = np.mean(list(weight_vector.weights.values()))

        # Momentum strategies work best in trending markets
        # Mean-reversion strategies work best in oscillating markets
        source = weight_vector.source

        if "momentum" in source.lower() and "oscillating" in regime:
            return {"passed": False,
                    "detail": f"动量策略在震荡市({regime})效果较差",
                    "adjustment": 0.85}
        elif "reversal" in source.lower() and "trend" in regime:
            return {"passed": False,
                    "detail": f"反转策略在趋势市({regime})效果较差",
                    "adjustment": 0.85}
        elif regime == "extreme_volatility" and abs(avg_weight) > 0.5:
            return {"passed": False,
                    "detail": "极端波动环境下高权重信号风险较大",
                    "adjustment": 0.7}
        return {"passed": True,
                "detail": f"策略与市场状态({regime})匹配",
                "adjustment": 1.0}

    def _check_concentration(self, weight_vector) -> dict:
        """Check if weights are too concentrated."""
        if len(weight_vector.weights) <= 1:
            return {"passed": True, "detail": "单标的", "adjustment": 1.0}

        max_weight = max(abs(w) for w in weight_vector.weights.values())
        if max_weight > 0.5:
            return {"passed": False,
                    "detail": f"单一标的权重{max_weight:.1%}过高",
                    "adjustment": 0.9}

        # Herfindahl index
        abs_weights = [abs(w) for w in weight_vector.weights.values()]
        total = sum(abs_weights)
        if total > 0:
            hhi = sum((w / total) ** 2 for w in abs_weights)
            if hhi > 0.5:
                return {"passed": False,
                        "detail": f"权重集中度HHI={hhi:.2f}偏高",
                        "adjustment": 0.9}

        return {"passed": True, "detail": f"集中度正常", "adjustment": 1.0}

    def _make_recommendation(self, passed: bool, multiplier: float) -> str:
        if passed and multiplier > 0.9:
            return "proceed"
        elif passed and multiplier > 0.6:
            return "proceed_with_caution"
        else:
            return "review"

    # ============================================================
    # Decision memory (stub in Phase B, real in Phase C)
    # ============================================================

    def record_decision(self, ticker: str, direction: str,
                        weight: float, reason: str,
                        target_date: date = None):
        """Record a decision for future win-rate tracking."""
        if ticker not in self._decision_cache:
            self._decision_cache[ticker] = []
        self._decision_cache[ticker].append({
            "date": (target_date or date.today()).isoformat(),
            "direction": direction,
            "weight": weight,
            "reason": reason,
            "return": None,  # Filled later by post-hoc check
        })

    def record_outcome(self, ticker: str, actual_return: float):
        """Update the most recent unverified decision with actual return."""
        if ticker not in self._decision_cache:
            return
        for decision in reversed(self._decision_cache[ticker]):
            if decision["return"] is None:
                decision["return"] = actual_return
                break

    def get_win_rate(self, ticker: str, lookback: int = 20) -> tuple[float, int]:
        """Get historical win rate for a ticker."""
        history = self._decision_cache.get(ticker, [])[-lookback:]
        completed = [h for h in history if h["return"] is not None]
        if not completed:
            return 0.5, 0
        wins = sum(1 for h in completed if h["return"] > 0)
        return wins / len(completed), len(completed)
