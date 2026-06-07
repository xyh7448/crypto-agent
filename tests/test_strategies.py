"""Test trading strategies."""
from __future__ import annotations
import pytest
from app.strategies.trend_following import TrendFollowingStrategy
from app.strategies.breakout import BreakoutStrategy
from app.strategies.mean_reversion import MeanReversionStrategy


class TestTrendFollowing:
    @pytest.mark.asyncio
    async def test_bullish_signal(self):
        strat = TrendFollowingStrategy()
        factors = {
            "ema_12": 51000,
            "ema_26": 50000,
            "sma_200": 49000,
            "close": 50500,
            "rsi_14": 55,
            "atr_14": 500,
        }
        signal = await strat.analyze("BTCUSDT", factors)
        assert signal is not None
        assert signal.direction == "long"
        assert signal.confidence > 0
        assert signal.stop_loss is not None
        assert signal.take_profit is not None

    @pytest.mark.asyncio
    async def test_bearish_signal(self):
        strat = TrendFollowingStrategy()
        factors = {
            "ema_12": 49000,
            "ema_26": 50000,
            "sma_200": 51000,
            "close": 49500,
            "rsi_14": 45,
            "atr_14": 500,
        }
        signal = await strat.analyze("BTCUSDT", factors)
        assert signal is not None
        assert signal.direction == "short"

    @pytest.mark.asyncio
    async def test_no_signal_neutral(self):
        strat = TrendFollowingStrategy()
        factors = {
            "ema_12": 50000,
            "ema_26": 50000,
            "sma_200": 50000,
            "close": 50000,
            "rsi_14": 50,
            "atr_14": 500,
        }
        signal = await strat.analyze("BTCUSDT", factors)
        assert signal is None


class TestBreakout:
    @pytest.mark.asyncio
    async def test_upside_breakout(self):
        strat = BreakoutStrategy()
        factors = {
            "close": 52000,
            "boll_ub": 51000,
            "boll_lb": 49000,
            "boll_mb": 50000,
            "rsi_14": 60,
            "volume_ratio": 2.0,
            "atr_14": 500,
        }
        signal = await strat.analyze("BTCUSDT", factors)
        assert signal is not None
        assert signal.direction == "long"


class TestMeanReversion:
    @pytest.mark.asyncio
    async def test_oversold_bounce(self):
        strat = MeanReversionStrategy()
        factors = {
            "close": 48000,
            "boll_ub": 52000,
            "boll_lb": 48500,
            "boll_mb": 50250,
            "rsi_14": 20,
            "atr_14": 500,
        }
        signal = await strat.analyze("BTCUSDT", factors)
        assert signal is not None
        assert signal.direction == "long"
        assert signal.confidence > 0.6
