"""Breakout Strategy - detect breakouts above/below Bollinger Bands with volume confirmation."""
from __future__ import annotations
from typing import Any, Optional

from app.strategies.base import StrategyBase, Signal


class BreakoutStrategy(StrategyBase):
    """Bollinger Band breakout with volume confirmation."""

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        default_params = {
            "bb_period": 20,
            "bb_std": 2.0,
            "volume_threshold": 1.5,
            "rsi_filter_high": 75,
            "rsi_filter_low": 25,
            "confidence_floor": 0.4,
        }
        merged = {**default_params, **params} if params else default_params
        super().__init__("breakout", merged)

    async def analyze(self, symbol: str, factors: dict[str, Any]) -> Signal | None:
        close = factors.get("close", 0)
        boll_ub = factors.get("boll_ub")
        boll_lb = factors.get("boll_lb")
        boll_mb = factors.get("boll_mb")
        rsi = factors.get("rsi_14")
        vol_ratio = factors.get("volume_ratio", 1.0)
        atr = factors.get("atr_14", close * 0.01)

        if not all([close, boll_ub, boll_lb, rsi]):
            return None

        vol_ok = vol_ratio >= self.params["volume_threshold"]

        # Upside breakout: close > upper band + volume confirmation
        if close > boll_ub and vol_ok and rsi <= self.params["rsi_filter_high"]:
            confidence = min(1.0, max(self.params["confidence_floor"],
                                      (close - boll_ub) / boll_ub * 50 + 0.3))
            return Signal(
                symbol=symbol,
                direction="long",
                confidence=round(confidence, 2),
                reason=f"Upside breakout: close({close:.2f}) > BB upper({boll_ub:.2f}), "
                       f"volume ratio={vol_ratio:.2f}, RSI={rsi:.1f}",
                price=close,
                stop_loss=round(boll_mb if boll_mb else close - atr * 2, 2),
                take_profit=round(close + atr * 3, 2),
                strategy=self.name,
            )

        # Downside breakout: close < lower band + volume confirmation
        if close < boll_lb and vol_ok and rsi >= self.params["rsi_filter_low"]:
            confidence = min(1.0, max(self.params["confidence_floor"],
                                      (boll_lb - close) / close * 50 + 0.3))
            return Signal(
                symbol=symbol,
                direction="short",
                confidence=round(confidence, 2),
                reason=f"Downside breakout: close({close:.2f}) < BB lower({boll_lb:.2f}), "
                       f"volume ratio={vol_ratio:.2f}, RSI={rsi:.1f}",
                price=close,
                stop_loss=round(boll_mb if boll_mb else close + atr * 2, 2),
                take_profit=round(close - atr * 3, 2),
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
