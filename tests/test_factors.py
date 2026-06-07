"""Test factor calculations."""
from __future__ import annotations
import pytest
from app.factors.technical import sma, ema, macd, rsi, atr, bollinger_bands


class TestSMA:
    def test_sma_basic(self):
        prices = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = sma(prices, 3)
        assert result[0] is None
        assert result[1] is None
        assert result[2] == pytest.approx(2.0)
        assert result[3] == pytest.approx(3.0)
        assert result[4] == pytest.approx(4.0)

    def test_sma_empty(self):
        assert sma([], 10) == []

    def test_sma_period_one(self):
        prices = [10.0, 20.0, 30.0]
        result = sma(prices, 1)
        assert result == [10.0, 20.0, 30.0]


class TestEMA:
    def test_ema_basic(self):
        prices = [10.0, 20.0, 30.0, 40.0, 50.0]
        result = ema(prices, 3)
        assert result[0] is None
        assert result[1] is None
        assert result[2] is not None
        assert result[3] > result[2]

    def test_ema_empty(self):
        assert ema([], 10) == []


class TestRSI:
    def test_rsi_constant_price(self):
        prices = [100.0] * 20
        result = rsi(prices, 14)
        assert result[-1] == 50.0  # No change = neutral RSI

    def test_rsi_up_trend(self):
        prices = [100 + i for i in range(30)]
        result = rsi(prices, 14)
        assert result[-1] > 50
        assert result[-1] < 100

    def test_rsi_down_trend(self):
        prices = [100 - i for i in range(30)]
        result = rsi(prices, 14)
        assert result[-1] < 50
        assert result[-1] > 0

    def test_rsi_empty(self):
        assert rsi([], 14) == []
        assert rsi([100.0], 14) == [None]


class TestATR:
    def test_atr_basic(self):
        highs = [110, 120, 130, 125, 135]
        lows = [90, 100, 110, 105, 115]
        closes = [105, 115, 125, 120, 130]
        result = atr(highs, lows, closes, 3)
        assert len(result) == 5
        assert result[0] is None
        assert result[3] is not None

    def test_atr_empty(self):
        assert atr([], [], []) == []


class TestBollingerBands:
    def test_bb_basic(self):
        prices = [100 + i * 0.5 for i in range(30)]
        bb = bollinger_bands(prices, 20)
        assert bb["upper"][-1] is not None
        assert bb["middle"][-1] is not None
        assert bb["lower"][-1] is not None
        assert bb["upper"][-1] > bb["middle"][-1] > bb["lower"][-1]

    def test_bb_empty(self):
        bb = bollinger_bands([])
        assert len(bb["upper"]) == 0


class TestMACD:
    def test_macd_basic(self):
        prices = [100 + i * 0.5 for i in range(50)]
        result = macd(prices)
        assert "macd_line" in result
        assert "signal_line" in result
        assert "histogram" in result
        assert result["macd_line"][-1] is not None

    def test_macd_empty(self):
        result = macd([])
        assert all(v == [] for v in result.values())
