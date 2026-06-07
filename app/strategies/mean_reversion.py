"""Mean Reversion Strategy - RSI extremes with Bollinger Band proximity."""
from __future__ import annotations
from typing import Any, Optional

from app.strategies.base import StrategyBase, Signal


class MeanReversionStrategy(StrategyBase):
    """RSI-based mean reversion with Bollinger Band proximity filter."""

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        default_params = {
            "rsi_oversold": 30,
            "rsi_overbought": 70,
            "rsi_extreme_oversold": 20,
            "rsi_extreme_overbought": 80,
            "bb_proximity_threshold": 0.5,  # 50% of band width
        }
        merged = {**default_params, **params} if params else default_params
        super().__init__("mean_reversion", merged)

    async def analyze(self, symbol: str, factors: dict[str, Any]) -> Signal | None:
        close = factors.get("close", 0)
        rsi = factors.get("rsi_14")
        boll_ub = factors.get("boll_ub")
        boll_lb = factors.get("boll_lb")
        boll_mb = factors.get("boll_mb")
        atr = factors.get("atr_14", close * 0.01)

        if not all([close, rsi, boll_ub, boll_lb, boll_mb]):
            return None

        band_width = boll_ub - boll_lb
        if band_width <= 0:
            return None

        # Proximity to lower band
        dist_to_lower = (close - boll_lb) / band_width if band_width else 1.0
        # Proximity to upper band
        dist_to_upper = (boll_ub - close) / band_width if band_width else 1.0

        rsi_val = rsi if rsi is not None else 50

        # Oversold bounce (long)
        if rsi_val <= self.params["rsi_extreme_oversold"]:
            confidence = min(1.0, (self.params["rsi_extreme_oversold"] - rsi_val) / 20 + 0.6)
            return Signal(
                symbol=symbol,
                direction="long",
                confidence=round(confidence, 2),
                reason=f"RSI={rsi_val:.1f} extremely oversold, mean reversion expected. "
                       f"Proximity to lower BB={dist_to_lower:.2%}",
                price=close,
                stop_loss=round(close - atr * 1.5, 2),
                take_profit=round(boll_mb + atr * 1, 2),
                strategy=self.name,
            )

        if rsi_val <= self.params["rsi_oversold"] and dist_to_lower < self.params["bb_proximity_threshold"]:
            confidence = min(1.0, (self.params["rsi_oversold"] - rsi_val) / 30 + 0.4)
            return Signal(
                symbol=symbol,
                direction="long",
                confidence=round(confidence, 2),
                reason=f"RSI={rsi_val:.1f} oversold near BB lower band, mean reversion setup",
                price=close,
                stop_loss=round(close - atr * 1.5, 2),
                take_profit=round(boll_mb + atr * 1, 2),
                strategy=self.name,
            )

        # Overbought pullback (short)
        if rsi_val >= self.params["rsi_extreme_overbought"]:
            confidence = min(1.0, (rsi_val - self.params["rsi_extreme_overbought"]) / 20 + 0.6)
            return Signal(
                symbol=symbol,
                direction="short",
                confidence=round(confidence, 2),
                reason=f"RSI={rsi_val:.1f} extremely overbought, mean reversion expected. "
                       f"Proximity to upper BB={dist_to_upper:.2%}",
                price=close,
                stop_loss=round(close + atr * 1.5, 2),
                take_profit=round(boll_mb - atr * 1, 2),
                strategy=self.name,
            )

        if rsi_val >= self.params["rsi_overbought"] and dist_to_upper < self.params["bb_proximity_threshold"]:
            confidence = min(1.0, (rsi_val - self.params["rsi_overbought"]) / 30 + 0.4)
            return Signal(
                symbol=symbol,
                direction="short",
                confidence=round(confidence, 2),
                reason=f"RSI={rsi_val:.1f} overbought near BB upper band, mean reversion setup",
                price=close,
                stop_loss=round(close + atr * 1.5, 2),
                take_profit=round(boll_mb - atr * 1, 2),
                strategy=self.name,
            )

        return None

    async def analyze_series(self, symbol: str, factor_series: list[dict[str, Any]]) -> list[Signal]:
        signals: list[Signal] = []
        for fs in factor_series:
            sig = await self.analyze(symbol, fs)
            if sig:
                signals.append(sig)
        return signals
