"""Order and trade request/response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class OrderCreate(BaseModel):
    """Payload for placing a new order on Binance."""

    symbol: str
    side: str = "BUY"  # BUY / SELL
    position_side: str = "LONG"  # LONG / SHORT
    order_type: str = "MARKET"  # MARKET / LIMIT
    price: Optional[float] = None
    quantity: float
    reduce_only: bool = False
    stop_price: Optional[float] = None


class OrderResponse(BaseModel):
    """Full order representation returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    symbol: str
    side: str
    position_side: str
    order_type: str
    price: Optional[float] = None
    orig_qty: float
    executed_qty: float
    status: str
    reduce_only: bool
    client_order_id: str
    binance_order_id: Optional[str] = None
    stop_price: Optional[float] = None
    created_at: datetime
    updated_at: datetime


class TradeResponse(BaseModel):
    """A single fill (partial or full) against an order."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    symbol: str
    order_id: int
    side: str
    position_side: str
    qty: float
    price: float
    realized_pnl: Optional[float] = None
    commission: Optional[float] = None
    commission_asset: str
    trade_time: int
    created_at: datetime
