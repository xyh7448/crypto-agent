"""Factor snapshot request/response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class FactorSnapshotResponse(BaseModel):
    """A pre-computed factor snapshot for a symbol + timeframe + bar."""

    model_config = ConfigDict(from_attributes=True)

    symbol: str
    timeframe: str
    timestamp: int
    factors: dict
    created_at: datetime
