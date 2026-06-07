"""Market structure indicators: funding rate, OI, volume."""
from __future__ import annotations
import numpy as np
from typing import Any


def funding_rate_signal(funding_rates: list[float]) -> dict[str, Any]:
    """Analyze funding rate for market sentiment."""
    if not funding_rates:
        return {"current_rate": 0.0, "avg_8h": 0.0, "sentiment": "neutral", "extreme": False, "signal": "neutral"}

    current = funding_rates[-1] if funding_rates else 0.0
    lookback = min(len(funding_rates), 8)
    avg = float(np.mean(funding_rates[-lookback:])) if lookback > 0 else 0.0

    if current > 0.01:
        sentiment = "positive"
        extreme = current > 0.05
        signal = "short" if extreme else "neutral"
    elif current < -0.01:
        sentiment = "negative"
        extreme = current < -0.05
        signal = "long" if extreme else "neutral"
    else:
        sentiment = "neutral"
        extreme = False
        signal = "neutral"

    return {
        "current_rate": current,
        "avg_8h": avg,
        "sentiment": sentiment,
        "extreme": extreme,
        "signal": signal,
    }


def oi_change(oi_series: list[float]) -> dict[str, Any]:
    """Analyze open interest changes."""
    if not oi_series:
        return {"current_oi": 0.0, "change_1h": 0.0, "change_24h": 0.0, "change_pct_1h": 0.0, "change_pct_24h": 0.0}

    current = oi_series[-1]
    idx_1h = max(0, len(oi_series) - 2)  # approximate
    idx_24h = max(0, len(oi_series) - 25)

    change_1h = current - oi_series[idx_1h] if idx_1h < len(oi_series) else 0
    change_24h = current - oi_series[idx_24h] if idx_24h < len(oi_series) else 0
    change_pct_1h = (change_1h / oi_series[idx_1h] * 100) if oi_series[idx_1h] != 0 else 0
    change_pct_24h = (change_24h / oi_series[idx_24h] * 100) if idx_24h < len(oi_series) and oi_series[idx_24h] != 0 else 0

    return {
        "current_oi": current,
        "change_1h": change_1h,
        "change_24h": change_24h,
        "change_pct_1h": round(change_pct_1h, 4),
        "change_pct_24h": round(change_pct_24h, 4),
    }


def volume_delta(volumes: list[float], period: int = 24) -> dict[str, Any]:
    """Volume analysis: current vs average."""
    if not volumes:
        return {"current_vol": 0.0, "avg_vol": 0.0, "ratio": 1.0}
    current = volumes[-1]
    lookback = min(len(volumes), period)
    avg = float(np.mean(volumes[-lookback:])) if lookback > 0 else current
    ratio = current / avg if avg > 0 else 1.0
    return {"current_vol": current, "avg_vol": avg, "ratio": round(ratio, 4)}
