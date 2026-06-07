"""Market analysis request/response schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class DailyAnalysisRequest(BaseModel):
    """Payload for requesting a daily market analysis."""

    symbols: list[str]
    include_factors: bool = True


class DailyAnalysisReport(BaseModel):
    """A daily market analysis report returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    date: str
    symbols: list[str]
    summary: str
    risk_level: str = "LOW"  # LOW / MEDIUM / HIGH / CRITICAL
    recommendations: list[str]
