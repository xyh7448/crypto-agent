"""Backtest request/response schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class BacktestRequest(BaseModel):
    """Payload for initiating a backtest run."""

    strategy_name: str
    symbol: str
    timeframe: str
    start_date: str  # YYYYMMDD
    end_date: str  # YYYYMMDD
    fast_period: int = 5
    slow_period: int = 20
    initial_capital: float = 10000.0


class BacktestResponse(BaseModel):
    """Backtest performance metrics returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    total_return: float
    annual_return: float
    max_drawdown: float
    sharpe_ratio: float
    win_rate: float
    profit_factor: float
    total_trades: int
    trades: list[dict]
