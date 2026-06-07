"""Factor snapshot ORM model — stores pre-computed technical & market factors."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Float, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class FactorSnapshotModel(Base):
    """Pre-computed technical and market factors for a symbol + timeframe + bar.

    Each row stores a JSON dict of computed indicators that would otherwise be
    expensive to re-derive on every inference call::

        {
            "sma": ...,
            "ema": ...,
            "macd": ...,
            "rsi": ...,
            "atr": ...,
            "boll_ub": ...,
            "boll_mb": ...,
            "boll_lb": ...,
            "funding_rate": ...,
            "oi_change": ...,
            "volume_delta": ...,
        }
    """

    __tablename__ = "factor_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)
    timestamp: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    factors: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=datetime.utcnow
    )

    __table_args__ = (
        UniqueConstraint(
            "symbol", "timeframe", "timestamp", name="uq_factor_snapshot"
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<FactorSnapshotModel {self.symbol} {self.timeframe}"
            f" @ {self.timestamp}>"
        )
