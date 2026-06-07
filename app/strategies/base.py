"""Strategy base class and signal model."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Signal:
    """Trading signal output by a strategy."""
    symbol: str
    direction: str  # "long", "short", "close"
    confidence: float  # 0.0 to 1.0
    reason: str
    price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    strategy: str = ""
    timeframe: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class StrategyBase(ABC):
    """Abstract base class for all trading strategies."""

    def __init__(self, name: str, params: dict[str, Any] | None = None) -> None:
        self.name = name
        self.params = params or {}

    @abstractmethod
    async def analyze(self, symbol: str, factors: dict[str, Any]) -> Signal | None:
        """Analyze current factors and return a signal if triggered."""
        ...

    @abstractmethod
    async def analyze_series(self, symbol: str, factor_series: list[dict[str, Any]]) -> list[Signal]:
        """Analyze a series of factor data (for backtesting). Returns list of signals."""
        ...
