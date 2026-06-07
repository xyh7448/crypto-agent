"""Risk engine - validates orders against risk parameters."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from app.core.config import settings


@dataclass
class RiskCheckResult:
    passed: bool
    reason: str = ""
    risk_score: float = 0.0


class RiskEngine:
    """Validates trading orders against risk parameters."""

    def __init__(self) -> None:
        self.max_position = settings.RISK_MAX_POSITION
        self.max_drawdown = settings.RISK_MAX_DRAWDOWN
        self.max_daily_loss = settings.RISK_MAX_DAILY_LOSS
        self._daily_pnl: float = 0.0
        self._peak_capital: float = 100000.0
        self._current_capital: float = 100000.0

    def update_capital(self, capital: float) -> None:
        self._current_capital = capital
        if capital > self._peak_capital:
            self._peak_capital = capital

    def update_daily_pnl(self, pnl: float) -> None:
        self._daily_pnl += pnl

    def reset_daily_pnl(self) -> None:
        self._daily_pnl = 0.0

    @property
    def current_drawdown(self) -> float:
        if self._peak_capital <= 0:
            return 0.0
        return (self._peak_capital - self._current_capital) / self._peak_capital

    async def check_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        current_position: float = 0.0,
        account_balance: float = 100000.0,
    ) -> RiskCheckResult:
        entry_value = quantity * price

        # Max position check
        position_value = current_position * price
        total_exposure = abs(position_value + (entry_value if side == "BUY" else -entry_value))
        position_ratio = total_exposure / account_balance if account_balance > 0 else 1.0
        if position_ratio > self.max_position:
            return RiskCheckResult(
                passed=False,
                reason=f"Position {position_ratio:.1%} exceeds max {self.max_position:.1%}",
                risk_score=1.0,
            )

        # Daily loss limit
        daily_loss_ratio = abs(self._daily_pnl) / account_balance if account_balance > 0 else 0
        if self._daily_pnl < 0 and daily_loss_ratio > self.max_daily_loss:
            return RiskCheckResult(
                passed=False,
                reason=f"Daily loss {daily_loss_ratio:.2%} exceeds limit {self.max_daily_loss:.2%}",
                risk_score=1.0,
            )

        # Max drawdown
        if self.current_drawdown > self.max_drawdown:
            return RiskCheckResult(
                passed=False,
                reason=f"Drawdown {self.current_drawdown:.2%} exceeds max {self.max_drawdown:.2%}",
                risk_score=1.0,
            )

        # Compute risk score
        risk_score = position_ratio / self.max_position * 0.5
        if self.current_drawdown > 0:
            risk_score += (self.current_drawdown / self.max_drawdown) * 0.5

        return RiskCheckResult(
            passed=True,
            reason=f"Risk score {risk_score:.2f}",
            risk_score=round(risk_score, 4),
        )
