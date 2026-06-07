"""Trading signal ORM model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SignalModel(Base):
    """A trading signal emitted by a strategy.

    Direction is one of ``"long"``, ``"short"``, or ``"close"``.  Confidence
    is a float in the ``[0, 1]`` range.  ``stop_loss`` and ``take_profit`` are
    optional price levels, and ``reason`` holds free-form text explaining the
    rationale.
    """

    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)
    timestamp: Mapped[int] = mapped_column(BigInteger, nullable=False)
    strategy: Mapped[str] = mapped_column(String(64), nullable=False)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)  # long / short / close
    confidence: Mapped[float] = mapped_column(Float, nullable=False)  # 0.0 – 1.0
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    stop_loss: Mapped[float | None] = mapped_column(Float, nullable=True)
    take_profit: Mapped[float | None] = mapped_column(Float, nullable=True)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=datetime.utcnow
    )

    def __repr__(self) -> str:
        return (
            f"<SignalModel {self.symbol} {self.direction} "
            f"({self.strategy}) @ {self.timestamp}>"
        )
