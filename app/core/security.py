"""
Risk engine parameter validation.

Provides Pydantic models and utility functions for validating risk
parameters (position sizing, drawdown limits, daily loss limits) before
they are consumed by the risk engine.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Any

from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
)

from app.core.config import settings

# ── Type aliases ───────────────────────────────────────────────────────────

PositiveFloat = Annotated[float, Field(gt=0.0)]
Probability = Annotated[float, Field(ge=0.0, le=1.0)]


# ── Risk parameter models ──────────────────────────────────────────────────

class RiskParameters(BaseModel):
    """Validated set of risk parameters for the trading engine.

    All parameters are enforced at construction time so the rest of the
    system can assume sane values.
    """

    max_position_size: PositiveFloat = Field(
        default=settings.RISK_MAX_POSITION,
        description="Maximum allowed position size in base currency units.",
    )
    max_drawdown: Probability = Field(
        default=settings.RISK_MAX_DRAWDOWN,
        description="Maximum fractional drawdown from peak portfolio value (0.0 – 1.0).",
    )
    max_daily_loss: Probability = Field(
        default=settings.RISK_MAX_DAILY_LOSS,
        description="Maximum fractional loss allowed in a single trading day (0.0 – 1.0).",
    )

    # ── Cross-field validation ─────────────────────────────────────────

    @model_validator(mode="after")
    def _ensure_loss_le_drawdown(self) -> RiskParameters:
        """Warn (but do not fail) if daily loss limit exceeds drawdown."""
        if self.max_daily_loss > self.max_drawdown:
            import warnings

            warnings.warn(
                f"max_daily_loss ({self.max_daily_loss:.2%}) exceeds "
                f"max_drawdown ({self.max_drawdown:.2%}): daily loss "
                "limit will never be hit before the drawdown stop.",
                stacklevel=2,
            )
        return self

    @field_validator("max_position_size")
    @classmethod
    def _reasonable_position(cls, v: float) -> float:
        """Reject obviously-unreasonable position sizes."""
        if v > 10_000_000:
            raise ValueError(
                f"max_position_size={v} exceeds 10M — likely a unit error. "
                "Use base currency units (e.g., 1.0 BTC, not satoshis)."
            )
        return v


class PositionSizingParams(BaseModel):
    """Leverage and margin parameters for per-trade position sizing."""

    leverage: PositiveFloat = Field(
        default=1.0,
        le=125.0,
        description="Leverage multiplier (1.0 = spot; max 125x per Binance specs).",
    )
    margin_buffer: Probability = Field(
        default=0.1,
        description="Fraction of available capital to reserve as a safety buffer.",
    )
    max_allocation_per_symbol: Probability = Field(
        default=0.25,
        description="Max fraction of total capital allocated to any single symbol.",
    )


class OrderRiskCheck(BaseModel):
    """Per-order risk validation result."""

    symbol: str = Field(..., min_length=1, pattern=r"^[A-Z0-9]{5,}$")
    side: str = Field(..., pattern=r"^(BUY|SELL)$")
    quantity: PositiveFloat
    price: PositiveFloat
    notional: PositiveFloat = Field(default=0.0, description="quantity × price")

    estimated_cost: PositiveFloat = Field(
        default=0.0,
        description="Estimated cost inclusive of leverage and fees.",
    )
    passes_risk: bool = False
    rejection_reason: str | None = None

    @model_validator(mode="after")
    def _compute_notional(self) -> OrderRiskCheck:
        """Auto-compute notional and estimated cost."""
        object.__setattr__(self, "notional", self.quantity * self.price)
        return self


# ── Public validation helpers ──────────────────────────────────────────────

def validate_risk_params(
    max_position: float | None = None,
    max_drawdown: float | None = None,
    max_daily_loss: float | None = None,
) -> RiskParameters:
    """Build and validate risk parameters, overriding defaults as needed.

    Parameters
    ----------
    max_position:
        Override for ``RISK_MAX_POSITION`` from config.
    max_drawdown:
        Override for ``RISK_MAX_DRAWDOWN`` from config.
    max_daily_loss:
        Override for ``RISK_MAX_DAILY_LOSS`` from config.

    Returns
    -------
    RiskParameters:
        Validated risk parameter object.
    """
    return RiskParameters(
        max_position_size=max_position or settings.RISK_MAX_POSITION,
        max_drawdown=max_drawdown or settings.RISK_MAX_DRAWDOWN,
        max_daily_loss=max_daily_loss or settings.RISK_MAX_DAILY_LOSS,
    )


def check_order(
    *,
    symbol: str,
    side: str,
    quantity: float,
    price: float,
    risk: RiskParameters | None = None,
    current_position: float = 0.0,
    current_drawdown: float = 0.0,
    current_daily_loss: float = 0.0,
) -> OrderRiskCheck:
    """Validate an order against the active risk parameters.

    Parameters
    ----------
    symbol:
        Trading pair symbol (e.g. ``"BTCUSDT"``).
    side:
        Order side, ``"BUY"`` or ``"SELL"``.
    quantity:
        Order quantity in base currency units.
    price:
        Expected execution price.
    risk:
        Risk parameters to validate against. Falls back to defaults from
        config when ``None``.
    current_position:
        Current absolute position size for the symbol.
    current_drawdown:
        Current drawdown fraction from peak.
    current_daily_loss:
        Cumulative daily loss fraction.

    Returns
    -------
    OrderRiskCheck:
        Validation result with ``passes_risk`` flag and optional rejection
        reason.
    """
    risk = risk or RiskParameters()

    notional = quantity * price
    estimated_cost = notional  # simplified; real fee calc would be more involved

    check = OrderRiskCheck(
        symbol=symbol,
        side=side,
        quantity=quantity,
        price=price,
        notional=notional,
        estimated_cost=estimated_cost,
    )

    reasons: list[str] = []

    # 1. Position size check
    new_position = current_position + (quantity if side == "BUY" else -quantity)
    if abs(new_position) > risk.max_position_size:
        reasons.append(
            f"New position {abs(new_position):.4f} exceeds "
            f"max_position_size {risk.max_position_size:.4f}"
        )

    # 2. Drawdown check
    if current_drawdown >= risk.max_drawdown:
        reasons.append(
            f"Current drawdown {current_drawdown:.2%} >= "
            f"max_drawdown {risk.max_drawdown:.2%}"
        )

    # 3. Daily loss check
    if current_daily_loss + (estimated_cost * 0.001) >= risk.max_daily_loss:
        reasons.append(
            f"Estimated daily loss would exceed "
            f"max_daily_loss {risk.max_daily_loss:.2%}"
        )

    if reasons:
        object.__setattr__(check, "passes_risk", False)
        object.__setattr__(check, "rejection_reason", "; ".join(reasons))
    else:
        object.__setattr__(check, "passes_risk", True)

    return check
