"""Order and trade ORM models — mirrors Binogram order lifecycle."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class OrderModel(Base):
    """A Binance order placed by the agent.

    Tracks the full lifecycle from creation through fill / cancel.  Fields
    mirror the Binance REST ``newOrder`` response shape where possible.
    """

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(8), nullable=False)  # BUY / SELL
    position_side: Mapped[str] = mapped_column(
        String(8), nullable=False
    )  # LONG / SHORT (UM futures)
    order_type: Mapped[str] = mapped_column(String(16), nullable=False)  # LIMIT / MARKET / STOP
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    orig_qty: Mapped[float] = mapped_column(Float, nullable=False)
    executed_qty: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(String(16), nullable=False)  # NEW / FILLED / CANCELED / ...
    reduce_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    client_order_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    binance_order_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    stop_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        return (
            f"<OrderModel {self.client_order_id} {self.symbol} "
            f"{self.side} {self.status}>"
        )


class TradeModel(Base):
    """A single fill (partial or full) against an order."""

    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    order_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    side: Mapped[str] = mapped_column(String(8), nullable=False)  # BUY / SELL
    position_side: Mapped[str] = mapped_column(String(8), nullable=False)
    qty: Mapped[float] = mapped_column(Float, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    realized_pnl: Mapped[float | None] = mapped_column(Float, nullable=True)
    commission: Mapped[float | None] = mapped_column(Float, nullable=True)
    commission_asset: Mapped[str] = mapped_column(String(16), nullable=False)
    trade_time: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=datetime.utcnow
    )

    def __repr__(self) -> str:
        return (
            f"<TradeModel id={self.id} order={self.order_id} "
            f"{self.symbol} {self.side} qty={self.qty} @ {self.price}>"
        )
