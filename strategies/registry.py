"""
Strategy registry — decorator-based registration.

Usage:
    @register_strategy("momentum", description="动量突破策略")
    class MomentumStrategy(StrategyBase):
        ...

    strategies = list_strategies()         # List all registered
    cls = get_strategy("momentum")          # Get by name
    instance = create_strategy("momentum")  # Create instance
"""
from typing import Optional


_registry: dict[str, dict] = {}


def register_strategy(name: str, description: str = "", category: str = ""):
    """
    Decorator to register a strategy class.

    Args:
        name: Unique strategy name (used in CLI: --strategy momentum)
        description: Human-readable description
        category: trend / reversal / arbitrage / event / meta
    """
    def decorator(cls):
        _registry[name] = {
            "class": cls,
            "name": name,
            "description": description,
            "category": category,
        }
        # Tag the class itself
        cls._strategy_name = name
        cls._strategy_description = description
        return cls
    return decorator


def get_strategy(name: str) -> Optional[type]:
    """Get strategy class by name."""
    entry = _registry.get(name)
    return entry["class"] if entry else None


def create_strategy(name: str, **kwargs):
    """Create a strategy instance by name."""
    cls = get_strategy(name)
    if cls is None:
        raise ValueError(f"Unknown strategy: {name}. Available: {list_strategies()}")
    return cls(**kwargs)


def list_strategies() -> list[dict]:
    """List all registered strategies."""
    return [
        {
            "name": v["name"],
            "description": v["description"],
            "category": v["category"],
        }
        for v in _registry.values()
    ]


def get_registry() -> dict[str, dict]:
    """Get the full registry (for introspection)."""
    return dict(_registry)
