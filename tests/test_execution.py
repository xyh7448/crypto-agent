"""Test execution sandbox and risk engine."""
from __future__ import annotations
import pytest
from app.execution.sandbox import TradingSandbox
from app.execution.risk import RiskEngine
from app.strategies.base import Signal


class TestTradingSandbox:
    @pytest.mark.asyncio
    async def test_open_long_position(self):
        sandbox = TradingSandbox(initial_balance=100000)
        signal = Signal(symbol="BTCUSDT", direction="long", confidence=0.8,
                       reason="Test", price=50000)
        order = await sandbox.open_position("BTCUSDT", "LONG", 0.5, 50000, signal)
        assert order.status == "filled"
        assert "BTCUSDT" in sandbox.positions
        assert sandbox.positions["BTCUSDT"].quantity == 0.5

    @pytest.mark.asyncio
    async def test_close_position(self):
        sandbox = TradingSandbox(initial_balance=100000)
        await sandbox.open_position("BTCUSDT", "LONG", 1.0, 50000)
        order = await sandbox.close_position("BTCUSDT", 51000)
        assert order is not None
        assert order.pnl > 0  # Should be profitable
        assert "BTCUSDT" not in sandbox.positions

    @pytest.mark.asyncio
    async def test_short_position(self):
        sandbox = TradingSandbox()
        await sandbox.open_position("ETHUSDT", "SHORT", 10.0, 3000)
        assert sandbox.positions["ETHUSDT"].side == "SHORT"
        order = await sandbox.close_position("ETHUSDT", 2900)
        assert order is not None
        assert order.pnl > 0

    def test_portfolio_summary(self):
        sandbox = TradingSandbox()
        summary = sandbox.get_portfolio_summary()
        assert summary["balance"] == 100000
        assert summary["total_return_pct"] == 0.0

    def test_reset(self):
        sandbox = TradingSandbox()
        sandbox.reset()
        assert sandbox.balance == sandbox.initial_balance
        assert len(sandbox.positions) == 0


class TestRiskEngine:
    def test_max_position_check(self):
        risk = RiskEngine()
        import pytest_asyncio
        result = risk.check_order("BTCUSDT", "BUY", 10, 50000, 0, 100000)
        # This is synchronous for now
        assert result is not None
