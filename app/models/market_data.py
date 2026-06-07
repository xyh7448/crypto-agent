"""Market data ORM models — klines, order books, funding rates, open interest."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Float,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class KlineModel(Base):
    """Candlestick / kline data for a symbol + timeframe pair."""

    __tablename__ = "klines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)
    open_time: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float] = mapped_column(Float, nullable=False)
    quote_vol: Mapped[float] = mapped_column(Float, nullable=False)
    trades: Mapped[int] = mapped_column(Integer, nullable=False)
    taker_buy_vol: Mapped[float] = mapped_column(Float, nullable=False)
    taker_buy_quote_vol: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=datetime.utcnow
    )

    __table_args__ = (
        UniqueConstraint("symbol", "timeframe", "open_time", name="uq_kline"),
    )

    def __repr__(self) -> str:
        return (
            f"<KlineModel {self.symbol} {self.timeframe} @ {self.open_time}>"
        )


class OrderBookModel(Base):
    """Snapshot of the order book at a given timestamp."""

    __tablename__ = "order_books"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    ts: Mapped[int] = mapped_column(BigInteger, nullable=False)
    bids: Mapped[dict] = mapped_column(JSON, nullable=False)
    asks: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<OrderBookModel {self.symbol} @ {self.ts}>"


class FundingRateModel(Base):
    """Perpetual funding rate observations."""

    __tablename__ = "funding_rates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    funding_time: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    funding_rate: Mapped[float] = mapped_column(Float, nullable=False)
    mark_price: Mapped[float] = mapped_column(Float, nullable=False)
    index_price: Mapped[float] = mapped_column(Float, nullable=False)
    settle_time: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=datetime.utcnow
    )

    __table_args__ = (
        UniqueConstraint("symbol", "funding_time", name="uq_funding_rate"),
    )

    def __repr__(self) -> str:
        return (
            f"<FundingRateModel {self.symbol} @ {self.funding_time}>"
        )


class OpenInterestModel(Base):
    """Open interest snapshots per symbol."""

    __tablename__ = "open_interests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    oi_time: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    open_interest: Mapped[float] = mapped_column(Float, nullable=False)
    open_interest_value: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=datetime.utcnow
    )

    __table_args__ = (
        UniqueConstraint("symbol", "oi_time", name="uq_open_interest"),
    )

    def __repr__(self) -> str:
        return (
            f"<OpenInterestModel {self.symbol} @ {self.oi_time}>"
        )
