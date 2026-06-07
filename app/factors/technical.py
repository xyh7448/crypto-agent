"""Technical indicator calculations (pure math, no DB)."""
from __future__ import annotations
import numpy as np
from typing import Any


def sma(prices: list[float], period: int) -> list[float | None]:
    """Simple Moving Average."""
    if not prices or period <= 0:
        return [None] * len(prices)
    arr = np.array(prices, dtype=np.float64)
    result: list[float | None] = [None] * (period - 1)
    for i in range(period - 1, len(arr)):
        result.append(float(np.mean(arr[i - period + 1 : i + 1])))
    return result


def ema(prices: list[float], period: int) -> list[float | None]:
    """Exponential Moving Average."""
    if not prices or period <= 0:
        return [None] * len(prices)
    arr = np.array(prices, dtype=np.float64)
    result: list[float | None] = [None] * (period - 1)
    multiplier = 2.0 / (period + 1)
    ema_val = float(np.mean(arr[:period]))
    result.append(ema_val)
    for i in range(period, len(arr)):
        ema_val = (arr[i] - ema_val) * multiplier + ema_val
        result.append(ema_val)
    return result


def macd(
    prices: list[float], fast: int = 12, slow: int = 26, signal: int = 9,
) -> dict[str, list[float | None]]:
    """MACD indicator. Returns {macd_line, signal_line, histogram}."""
    ema_fast = ema(prices, fast)
    ema_slow = ema(prices, slow)
    macd_line: list[float | None] = []
    for f, s in zip(ema_fast, ema_slow):
        if f is not None and s is not None:
            macd_line.append(f - s)
        else:
            macd_line.append(None)
    sig_line = ema([x for x in macd_line if x is not None], signal)
    # Pad front of signal line
    sig_padded: list[float | None] = [None] * len(macd_line)
    sig_idx = 0
    for i in range(len(macd_line)):
        if macd_line[i] is not None:
            if sig_idx < len(sig_line) and sig_line[sig_idx] is not None:
                sig_padded[i] = sig_line[sig_idx]
            sig_idx += 1
    histogram: list[float | None] = []
    for m, s in zip(macd_line, sig_padded):
        if m is not None and s is not None:
            histogram.append(m - s)
        else:
            histogram.append(None)
    return {"macd_line": macd_line, "signal_line": sig_padded, "histogram": histogram}


def rsi(prices: list[float], period: int = 14) -> list[float | None]:
    """Relative Strength Index."""
    if not prices or len(prices) < period + 1:
        return [None] * len(prices)
    arr = np.array(prices, dtype=np.float64)
    deltas = np.diff(arr)
    result: list[float | None] = [None] * period
    gains = np.maximum(deltas[:period], 0)
    losses = np.maximum(-deltas[:period], 0)
    avg_gain = float(np.mean(gains))
    avg_loss = float(np.mean(losses))
    if avg_loss == 0:
        result.append(100.0 if avg_gain > 0 else 50.0)
    else:
        rs = avg_gain / avg_loss
        result.append(100.0 - 100.0 / (1.0 + rs))
    for i in range(period + 1, len(arr)):
        delta = deltas[i - 1]
        gain = max(delta, 0)
        loss = max(-delta, 0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        if avg_loss == 0:
            result.append(100.0 if avg_gain > 0 else 50.0)
        else:
            rs = avg_gain / avg_loss
            result.append(100.0 - 100.0 / (1.0 + rs))
    return result


def atr(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> list[float | None]:
    """Average True Range."""
    if not highs or len(highs) < 2:
        return [None] * len(highs)
    high_arr = np.array(highs, dtype=np.float64)
    low_arr = np.array(lows, dtype=np.float64)
    close_arr = np.array(closes, dtype=np.float64)
    tr = np.maximum(
        high_arr[1:] - low_arr[1:],
        np.maximum(
            np.abs(high_arr[1:] - close_arr[:-1]),
            np.abs(low_arr[1:] - close_arr[:-1]),
        ),
    )
    result: list[float | None] = [None]
    for i in range(len(tr)):
        if i < period - 1:
            result.append(None)
        elif i == period - 1:
            result.append(float(np.mean(tr[: period])))
        else:
            result.append((result[-1] * (period - 1) + tr[i]) / period)
    return result


def bollinger_bands(prices: list[float], period: int = 20, std_dev: float = 2.0) -> dict[str, list[float | None]]:
    """Bollinger Bands. Returns {upper, middle, lower}."""
    mid = sma(prices, period)
    arr = np.array(prices, dtype=np.float64)
    upper: list[float | None] = []
    lower: list[float | None] = []
    for i in range(len(prices)):
        if mid[i] is None or i < period - 1:
            upper.append(None)
            lower.append(None)
        else:
            sd = float(np.std(arr[i - period + 1 : i + 1]))
            upper.append(mid[i] + std_dev * sd)
            lower.append(mid[i] - std_dev * sd)
    return {"upper": upper, "middle": mid, "lower": lower}
