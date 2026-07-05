"""Strategy registry tests — registration, discovery, creation."""
from __future__ import annotations

import pytest

from strategies.registry import (
    register_strategy,
    list_strategies,
    get_strategy,
    create_strategy,
)


class TestListStrategies:
    def test_registry_has_builtin_strategies(self):
        strategies = list_strategies()
        names = [s["name"] for s in strategies]
        assert "momentum" in names
        assert "event_driven" in names
        assert "sentiment" in names
        assert "regime_switch" in names

    def test_each_strategy_has_required_fields(self):
        for s in list_strategies():
            assert "name" in s
            assert "description" in s
            assert "category" in s


class TestGetStrategy:
    def test_get_strategy_by_name(self):
        cls = get_strategy("momentum")
        assert cls is not None
        assert cls._strategy_name == "momentum"

    def test_get_strategy_nonexistent(self):
        cls = get_strategy("nonexistent_strategy")
        assert cls is None

    def test_get_strategies_by_category(self):
        """Filter by category via list_strategies (get_strategy only supports name)."""
        all_strategies = list_strategies()
        meta = [s for s in all_strategies if s["category"] == "meta"]
        assert len(meta) >= 1
        names = [s["name"] for s in meta]
        assert "regime_switch" in names

        event = [s for s in all_strategies if s["category"] == "event"]
        names = [s["name"] for s in event]
        assert "event_driven" in names
        assert "sentiment" in names

    def test_get_technical_strategies(self):
        """momentum strategy is in 'trend' category, not 'technical'."""
        trend = [s for s in list_strategies() if s["category"] == "trend"]
        names = [s["name"] for s in trend]
        assert "momentum" in names


class TestCreateStrategy:
    def test_create_strategy_by_name(self):
        strat = create_strategy("momentum")
        assert strat is not None
        assert strat.name == "momentum"

    def test_create_strategy_invalid_name(self):
        with pytest.raises(ValueError):
            create_strategy("nonexistent")

    def test_create_strategy_has_expected_methods(self):
        strat = create_strategy("event_driven")
        assert hasattr(strat, "generate_signal")
        assert hasattr(strat, "generate_weight_vector")
        assert hasattr(strat, "expected_holding_period")

    def test_create_all_builtin_strategies(self):
        for s in list_strategies():
            strat = create_strategy(s["name"])
            assert strat is not None, f"Failed to create: {s['name']}"
