"""Market data request/response schemas — klines, funding rates, open interest."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict


class KlineResponse(BaseModel):
    """Kline / candlestick data returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    symbol: str
    timeframe: str
    open_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class KlineQuery(BaseModel):
    """Query parameters for fetching kline/candlestick data."""

    symbol: str
    timeframe: str
    start_time: Optional[int] = None
    end_time: Optional[int] = None
    limit: int = 200


class FundingRateResponse(BaseModel):
    """Perpetual funding rate observation returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    symbol: str
    funding_time: int
    funding_rate: float
    mark_price: float


class OpenInterestResponse(BaseModel):
    """Open interest snapshot returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    symbol: str
    oi_time: int
    open_interest: float
    open_interest_value: float
