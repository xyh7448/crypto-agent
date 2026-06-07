"""Trading signal request/response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class SignalResponse(BaseModel):
    """A trading signal emitted by a strategy."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    symbol: str
    timeframe: str
    timestamp: int
    strategy: str
    direction: str
    confidence: float
    reason: str
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    price: float
    created_at: datetime
