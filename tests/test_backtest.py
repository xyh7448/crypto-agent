"""Test backtest engine."""
from __future__ import annotations
import pytest
from app.strategies.trend_following import TrendFollowingStrategy
from app.backtest.engine import BacktestEngine


class TestBacktestEngine:
    @pytest.mark.asyncio
    async def test_empty_data(self):
        engine = BacktestEngine()
        strategy = TrendFollowingStrategy()
        result = await engine.run(strategy, "BTCUSDT", "1h", [])
        assert result.total_trades == 0
        assert result.total_return == 0.0

    @pytest.mark.asyncio
    async def test_basic_backtest(self):
        engine = BacktestEngine(initial_capital=10000)
        strategy = TrendFollowingStrategy()

        # Generate synthetic factor data
        factor_series = []
        for i in range(200):
            price = 50000 + i * 10  # Upward trend
            factor_series.append({
                "timestamp": 1700000000000 + i * 3600000,
                "close": price,
                "sma_20": price - 100,
                "sma_50": price - 300,
                "sma_200": price - 1000,
                "ema_12": price - 50,
                "ema_26": price - 150,
                "rsi_14": 55 + (i % 20),
                "macd_line": 100,
                "macd_signal": 50,
                "macd_histogram": 50,
                "atr_14": 400,
                "boll_ub": price + 1000,
                "boll_mb": price,
                "boll_lb": price - 1000,
                "volume_ratio": 1.0,
            })

        result = await engine.run(strategy, "BTCUSDT", "1h", factor_series)
        assert result.total_trades >= 0
        assert isinstance(result.total_return, float)
        assert isinstance(result.sharpe_ratio, float)
        assert 0 <= result.win_rate <= 100
