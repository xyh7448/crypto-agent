"""Trend Following Strategy - EMA cross, trend filter, ATR-based stops."""
from __future__ import annotations
from typing import Any, Optional

from app.strategies.base import StrategyBase, Signal


class TrendFollowingStrategy(StrategyBase):
    """EMA cross trend following with ATR-based position sizing."""

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        default_params = {
            "ema_fast": 12,
            "ema_slow": 26,
            "trend_filter_sma": 200,
            "rsi_oversold": 30,
            "rsi_overbought": 70,
            "atr_multiplier_sl": 2.0,
            "atr_multiplier_tp": 4.0,
            "min_confidence": 0.5,
        }
        merged = {**default_params, **(params or {})}
        super().__init__("trend_following", merged)

    async def analyze(self, symbol: str, factors: dict[str, Any]) -> Signal | None:
        ema_fast = factors.get("ema_12")
        ema_slow = factors.get("ema_26")
        sma_200 = factors.get("sma_200")
        close = factors.get("close", 0)
        rsi = factors.get("rsi_14")
        atr_val = factors.get("atr_14", 0)
        if None in (ema_fast, ema_slow, close, rsi):
            return None

        price = close
        sl_mult = self.params["atr_multiplier_sl"]
        tp_mult = self.params["atr_multiplier_tp"]
        atr = atr_val or price * 0.01

        # Uptrend: fast > slow and price above 200 SMA
        uptrend = ema_fast > ema_slow and (sma_200 is None or price > sma_200)
        # Downtrend: fast < slow and price below 200 SMA
        downtrend = ema_fast < ema_slow and (sma_200 is None or price < sma_200)

        # Long entry: uptrend + RSI not overbought
        if uptrend:
            if rsi is not None and rsi < self.params["rsi_overbought"]:
                confidence = min(1.0, abs(ema_fast - ema_slow) / ema_slow * 20 + 0.3)
                signal = Signal(
                    symbol=symbol,
                    direction="long",
                    confidence=round(confidence, 2),
                    reason=f"EMA{self.params['ema_fast']}({ema_fast:.2f}) > EMA{self.params['ema_slow']}({ema_slow:.2f}), "
                           f"RSI={rsi:.1f}, uptrend confirmed",
                    price=price,
                    stop_loss=round(price - atr * sl_mult, 2),
                    take_profit=round(price + atr * tp_mult, 2),
                    strategy=self.name,
                )
                return signal

        # Short entry: downtrend + RSI not oversold
        if downtrend:
            if rsi is not None and rsi > self.params["rsi_oversold"]:
                confidence = min(1.0, abs(ema_fast - ema_slow) / ema_slow * 20 + 0.3)
                signal = Signal(
                    symbol=symbol,
                    direction="short",
                    confidence=round(confidence, 2),
                    reason=f"EMA{self.params['ema_fast']}({ema_fast:.2f}) < EMA{self.params['ema_slow']}({ema_slow:.2f}), "
                           f"RSI={rsi:.1f}, downtrend confirmed",
                    price=price,
                    stop_loss=round(price + atr * sl_mult, 2),
                    take_profit=round(price - atr * tp_mult, 2),
                    strategy=self.name,
                )
                return signal

        return None

    async def analyze_series(self, symbol: str, factor_series: list[dict[str, Any]]) -> list[Signal]:
        signals: list[Signal] = []
        position = 0
        for fs in factor_series:
            sig = await self.analyze(symbol, fs)
            if sig:
                # Only generate signal if direction changes
                new_dir = 1 if sig.direction == "long" else -1
                if new_dir != position:
                    signals.append(sig)
                    position = new_dir
        return signals
