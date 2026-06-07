"""Parameter optimizer - grid search over strategy parameters."""
from __future__ import annotations
import asyncio
import itertools
import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from app.strategies.base import StrategyBase
from app.backtest.engine import BacktestEngine, BacktestResult

logger = logging.getLogger(__name__)


@dataclass
class OptimizationResult:
    best_params: dict[str, Any]
    best_metric: float
    metric_name: str
    results: list[dict] = field(default_factory=list)


class ParameterOptimizer:
    """Grid/random search optimizer for strategy parameters."""

    def __init__(
        self,
        strategy_class: type[StrategyBase],
        backtest_engine: BacktestEngine,
    ) -> None:
        self.strategy_class = strategy_class
        self.engine = backtest_engine

    async def grid_search(
        self,
        param_grid: dict[str, list[Any]],
        symbol: str,
        factor_series: list[dict[str, Any]],
        metric: str = "sharpe_ratio",
        maximize: bool = True,
    ) -> OptimizationResult:
        """Grid search over parameter combinations."""
        keys = list(param_grid.keys())
        values = list(param_grid.values())
        combinations = list(itertools.product(*values))

        logger.info("Grid search: %d combinations for %s", len(combinations), symbol)

        best_metric = float("-inf") if maximize else float("inf")
        best_params = {}
        results = []

        for combo in combinations:
            params = dict(zip(keys, combo))
            strategy = self.strategy_class(params=params)
            result = await self.engine.run(strategy, symbol, "1h", factor_series)

            metric_value = getattr(result, metric, 0.0)
            results.append({"params": params, metric: metric_value})

            if (maximize and metric_value > best_metric) or (not maximize and metric_value < best_metric):
                best_metric = metric_value
                best_params = params

            logger.debug("Params %s: %s=%s, total_return=%.2f", params, metric, metric_value, result.total_return)

        return OptimizationResult(
            best_params=best_params,
            best_metric=best_metric,
            metric_name=metric,
            results=sorted(results, key=lambda r: r[metric], reverse=maximize)[:20],
        )
