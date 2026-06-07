"""Execution sandbox - simulated trading environment for testing orders."""
from __future__ import annotations
import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from app.execution.risk import RiskEngine, RiskCheckResult
from app.strategies.base import Signal

logger = logging.getLogger(__name__)


@dataclass
class SandboxOrder:
    id: str
    symbol: str
    side: str  # "BUY" | "SELL"
    quantity: float
    price: float
    status: str = "pending"  # pending, filled, cancelled, rejected
    pnl: float = 0.0
    filled_qty: float = 0.0
    created_at: str = ""
    filled_at: str = ""


@dataclass
class SandboxPosition:
    symbol: str
    side: str  # "LONG" | "SHORT"
    quantity: float
    entry_price: float
    current_price: float = 0.0
    unrealized_pnl: float = 0.0


class TradingSandbox:
    """Simulated trading environment. No real orders are ever placed."""

    def __init__(self, initial_balance: float = 100000.0) -> None:
        self.balance = initial_balance
        self.initial_balance = initial_balance
        self.positions: dict[str, SandboxPosition] = {}
        self.orders: list[SandboxOrder] = []
        self.trades: list[dict] = []
        self.risk = RiskEngine()
        self._order_counter = 0

    def _next_order_id(self) -> str:
        self._order_counter += 1
        return f"sandbox_{int(time.time())}_{self._order_counter}"

    async def open_position(
        self, symbol: str, side: str, quantity: float, price: float, signal: Signal | None = None
    ) -> SandboxOrder:
        """Open a simulated position. Validates via risk engine first."""
        current_pos = self.positions.get(symbol, SandboxPosition(symbol=symbol, side="LONG", quantity=0, entry_price=0)).quantity

        risk_check = await self.risk.check_order(
            symbol=symbol,
            side="BUY" if side == "LONG" else "SELL",
            quantity=quantity,
            price=price,
            current_position=current_pos,
            account_balance=self.balance,
        )

        if not risk_check.passed:
            order = SandboxOrder(
                id=self._next_order_id(),
                symbol=symbol,
                side="BUY" if side == "LONG" else "SELL",
                quantity=quantity,
                price=price,
                status="rejected",
                created_at=datetime.utcnow().isoformat(),
            )
            self.orders.append(order)
            logger.warning("Order rejected: %s", risk_check.reason)
            return order

        cost = quantity * price
        if side == "LONG":
            self.balance -= cost
            self.positions[symbol] = SandboxPosition(
                symbol=symbol, side="LONG",
                quantity=quantity, entry_price=price,
            )
        else:
            self.balance += cost  # short receives quote currency
            self.positions[symbol] = SandboxPosition(
                symbol=symbol, side="SHORT",
                quantity=quantity, entry_price=price,
            )

        order = SandboxOrder(
            id=self._next_order_id(),
            symbol=symbol,
            side="BUY" if side == "LONG" else "SELL",
            quantity=quantity,
            price=price,
            status="filled",
            filled_qty=quantity,
            created_at=datetime.utcnow().isoformat(),
            filled_at=datetime.utcnow().isoformat(),
        )
        self.orders.append(order)
        self.risk.update_capital(self.get_equity(price))

        logger.info("Sandbox position opened: %s %s %f @ %.2f", symbol, side, quantity, price)
        return order

    async def close_position(self, symbol: str, price: float) -> SandboxOrder | None:
        """Close an existing position."""
        pos = self.positions.get(symbol)
        if not pos:
            logger.warning("No position to close for %s", symbol)
            return None

        if pos.side == "LONG":
            pnl = (price - pos.entry_price) * pos.quantity
            self.balance += pos.quantity * price
            side = "SELL"
        else:
            pnl = (pos.entry_price - price) * pos.quantity
            self.balance -= pos.quantity * price  # Buy back to cover
            side = "BUY"

        self.trades.append({
            "symbol": symbol,
            "side": side,
            "quantity": pos.quantity,
            "entry_price": pos.entry_price,
            "exit_price": price,
            "pnl": round(pnl, 2),
            "timestamp": datetime.utcnow().isoformat(),
        })

        self.risk.update_daily_pnl(pnl)
        self.risk.update_capital(self.get_equity(price))
        self._daily_pnl = pnl

        order = SandboxOrder(
            id=self._next_order_id(),
            symbol=symbol,
            side=side,
            quantity=pos.quantity,
            price=price,
            status="filled",
            filled_qty=pos.quantity,
            pnl=round(pnl, 2),
            created_at=datetime.utcnow().isoformat(),
            filled_at=datetime.utcnow().isoformat(),
        )
        self.orders.append(order)
        del self.positions[symbol]

        logger.info("Sandbox position closed: %s PnL=%.2f", symbol, pnl)
        return order

    def update_prices(self, prices: dict[str, float]) -> None:
        """Update current prices for unrealized PnL calculation."""
        for symbol, pos in self.positions.items():
            if symbol in prices:
                pos.current_price = prices[symbol]
                if pos.side == "LONG":
                    pos.unrealized_pnl = (pos.current_price - pos.entry_price) * pos.quantity
                else:
                    pos.unrealized_pnl = (pos.entry_price - pos.current_price) * pos.quantity

    def get_equity(self, current_price: float = 0.0) -> float:
        equity = self.balance
        for symbol, pos in self.positions.items():
            price = current_price if current_price > 0 else pos.current_price or pos.entry_price
            if price > 0 and pos.quantity > 0:
                if pos.side == "LONG":
                    equity += (price - pos.entry_price) * pos.quantity
                else:
                    equity += (pos.entry_price - price) * pos.quantity
        return equity

    def get_portfolio_summary(self) -> dict[str, Any]:
        return {
            "balance": round(self.balance, 2),
            "equity": round(self.get_equity(), 2),
            "total_return_pct": round((self.balance / self.initial_balance - 1) * 100, 2),
            "open_positions": len(self.positions),
            "total_trades": len(self.trades),
            "positions": {
                s: {"side": p.side, "qty": p.quantity, "entry": p.entry_price, "upnl": round(p.unrealized_pnl, 2)}
                for s, p in self.positions.items()
            },
        }

    def reset(self) -> None:
        self.balance = self.initial_balance
        self.positions.clear()
        self.orders.clear()
        self.trades.clear()
        self.risk = RiskEngine()
        self._order_counter = 0
        logger.info("Sandbox reset")
