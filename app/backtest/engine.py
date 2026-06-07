"""Backtest engine - runs strategies against historical factor data."""
from __future__ import annotations
import asyncio
import logging
import numpy as np
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from app.strategies.base import StrategyBase, Signal

logger = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    """Backtest performance metrics."""
    strategy_name: str
    symbol: str
    timeframe: str
    start_date: str
    end_date: str
    total_return: float = 0.0
    annual_return: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    trades: list[dict] = field(default_factory=list)
    equity_curve: list[float] = field(default_factory=list)
    params: dict[str, Any] = field(default_factory=dict)


class BacktestEngine:
    """Runs strategy backtest on historical factor data."""

    def __init__(self, initial_capital: float = 10000.0, commission_pct: float = 0.04) -> None:
        self.initial_capital = initial_capital
        self.commission_pct = commission_pct

    async def run(
        self,
        strategy: StrategyBase,
        symbol: str,
        timeframe: str,
        factor_series: list[dict[str, Any]],
        start_date: str = "",
        end_date: str = "",
    ) -> BacktestResult:
        """Run backtest for a strategy on factor data. Returns performance metrics."""
        if not factor_series:
            logger.warning("No factor data for backtest")
            return BacktestResult(
                strategy_name=strategy.name,
                symbol=symbol,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date,
            )

        signals = await strategy.analyze_series(symbol, factor_series)
        if not signals:
            return BacktestResult(
                strategy_name=strategy.name,
                symbol=symbol,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date,
                total_trades=0,
            )

        # Simulate trading
        capital = self.initial_capital
        position = 0  # 1: long, -1: short, 0: flat
        entry_price = 0.0
        entry_idx = 0
        trades = []
        equity_curve = [capital]
        trade_idx = 0

        for i, fs in enumerate(factor_series):
            price = fs.get("close", 0)
            if price == 0:
                equity_curve.append(equity_curve[-1] if equity_curve else capital)
                continue

            # Check for signal
            signal = None
            while trade_idx < len(signals) and (
                trade_idx == 0 or
                (
                    hasattr(factor_series[i], "get") and
                    factor_series[i].get("timestamp", 0) >= getattr(signals[trade_idx], "metadata", {}).get("timestamp", 0)
                )
            ):
                if i >= len(factor_series):
                    break
                sig = signals[trade_idx]
                sig_price = getattr(sig, "price", price)
                sig_dir = getattr(sig, "direction", "close")

                # Check if signal timestamp matches or precedes current bar
                signal = sig
                trade_idx += 1
                break

            if signal:
                sig_dir = signal.direction
                sig_price = signal.price or price

                # Close existing position
                if position != 0:
                    pnl = (sig_price - entry_price) * position - self.commission_pct / 100 * abs(sig_price - entry_price) * abs(position)
                    trades.append({
                        "entry_time": factor_series[entry_idx]["timestamp"] if entry_idx < len(factor_series) else 0,
                        "exit_time": fs["timestamp"],
                        "direction": "long" if position > 0 else "short",
                        "entry_price": entry_price,
                        "exit_price": sig_price,
                        "pnl": round(pnl, 2),
                        "return_pct": round(pnl / capital * 100, 4),
                    })
                    capital += pnl
                    position = 0

                # Open new position
                if sig_dir in ("long", "short"):
                    position = 1 if sig_dir == "long" else -1
                    entry_price = sig_price
                    entry_idx = i

            if position != 0:
                unrealized_pnl = (price - entry_price) * position
                equity = capital + unrealized_pnl
            else:
                equity = capital
            equity_curve.append(equity)

        # Close any remaining position at last price
        if position != 0 and factor_series:
            last_price = factor_series[-1].get("close", 0)
            if last_price:
                pnl = (last_price - entry_price) * position
                trades.append({
                    "entry_time": factor_series[entry_idx]["timestamp"] if entry_idx < len(factor_series) else 0,
                    "exit_time": factor_series[-1]["timestamp"],
                    "direction": "long" if position > 0 else "short",
                    "entry_price": entry_price,
                    "exit_price": last_price,
                    "pnl": round(pnl, 2),
                    "return_pct": round(pnl / capital * 100, 4),
                })
                capital += pnl

        # Calculate metrics
        total_return = (capital / self.initial_capital - 1) * 100
        years = len(factor_series) / 365 if len(factor_series) > 0 else 1
        annual_return = ((1 + total_return / 100) ** (1 / max(years, 0.01)) - 1) * 100

        equity_arr = np.array(equity_curve, dtype=np.float64)
        peak = np.maximum.accumulate(equity_arr)
        drawdowns = (peak - equity_arr) / peak * 100
        max_dd = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0.0

        # Sharpe
        if len(equity_curve) > 1:
            returns = np.diff(equity_arr) / equity_arr[:-1]
            sharpe = float(np.mean(returns) / np.std(returns) * np.sqrt(365)) if np.std(returns) > 0 else 0.0
        else:
            sharpe = 0.0

        wins = [t for t in trades if t["pnl"] > 0]
        losses = [t for t in trades if t["pnl"] <= 0]
        win_rate = len(wins) / len(trades) * 100 if trades else 0.0
        total_wins = sum(t["pnl"] for t in wins)
        total_losses = abs(sum(t["pnl"] for t in losses))
        profit_factor = total_wins / total_losses if total_losses > 0 else (total_wins if total_wins > 0 else 1.0)

        return BacktestResult(
            strategy_name=strategy.name,
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            total_return=round(total_return, 4),
            annual_return=round(annual_return, 4),
            max_drawdown=round(max_dd, 4),
            sharpe_ratio=round(sharpe, 4),
            win_rate=round(win_rate, 2),
            profit_factor=round(profit_factor, 4),
            total_trades=len(trades),
            winning_trades=len(wins),
            losing_trades=len(losses),
            avg_win=round(np.mean([t["pnl"] for t in wins]), 2) if wins else 0.0,
            avg_loss=round(np.mean([t["pnl"] for t in losses]), 2) if losses else 0.0,
            trades=trades,
            equity_curve=[round(e, 2) for e in equity_curve],
            params=strategy.params,
        )
