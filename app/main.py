"""Crypto Quant Agent OS - FastAPI entry point."""
from __future__ import annotations
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import Base, get_db, engine
from app.core.redis import get_redis, close_redis
from app.core.logger import get_logger
from app.market_data.repository import MarketDataRepository
from app.market_data.binance_rest import BinanceRestClient
from app.factors.engine import FactorEngine
from app.strategies.trend_following import TrendFollowingStrategy
from app.strategies.breakout import BreakoutStrategy
from app.strategies.mean_reversion import MeanReversionStrategy
from app.backtest.engine import BacktestEngine
from app.execution.sandbox import TradingSandbox
from app.execution.risk import RiskEngine
from app.memory.store import MemoryStore
from app.analyst.agent import AnalystAgent
from app.notification.feishu import FeishuNotifier
from app.scheduler.tasks import run_daily_analysis

logger = get_logger(__name__)

# Global state
sandbox = TradingSandbox()
risk_engine = RiskEngine()
analyst = AnalystAgent()
rest_client: BinanceRestClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan - startup and shutdown."""
    global rest_client

    logger.info("Starting Crypto Quant Agent OS")

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    rest_client = BinanceRestClient()

    yield

    # Shutdown
    if rest_client:
        await rest_client.close()
    await close_redis()
    logger.info("Crypto Quant Agent OS shutdown")


app = FastAPI(
    title="Crypto Quant Agent OS",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# === Health Check ===
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "sandbox_orders": len(sandbox.orders),
        "sandbox_positions": len(sandbox.positions),
    }


@app.get("/health/db")
async def health_db(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database error: {e}")


# === Market Data ===
@app.get("/api/v1/market/klines/{symbol}")
async def get_klines(
    symbol: str,
    interval: str = "1h",
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    if not rest_client:
        raise HTTPException(status_code=503, detail="REST client not initialized")
    raw = await rest_client.get_klines(symbol.upper(), interval, limit=min(limit, 500))
    return {
        "symbol": symbol.upper(),
        "interval": interval,
        "count": len(raw),
        "data": [
            {"time": k[0], "open": float(k[1]), "high": float(k[2]), "low": float(k[3]),
             "close": float(k[4]), "volume": float(k[5])}
            for k in raw
        ],
    }


@app.get("/api/v1/market/funding/{symbol}")
async def get_funding_rate(symbol: str, limit: int = 24):
    if not rest_client:
        raise HTTPException(status_code=503, detail="REST client not initialized")
    fr = await rest_client.get_funding_rate(symbol.upper(), limit=min(limit, 100))
    return {"symbol": symbol.upper(), "data": [{"time": f[0], "rate": float(f[4])} for f in fr]}


@app.get("/api/v1/market/oi/{symbol}")
async def get_open_interest(symbol: str, period: str = "1h", limit: int = 24):
    if not rest_client:
        raise HTTPException(status_code=503, detail="REST client not initialized")
    oi = await rest_client.get_open_interest(symbol.upper(), period=period, limit=min(limit, 500))
    return {"symbol": symbol.upper(), "data": [{"time": o[0], "value": float(o[4])} for o in oi]}


# === Factors ===
@app.get("/api/v1/factors/{symbol}")
async def get_factors(symbol: str, interval: str = "1h", limit: int = 200):
    if not rest_client:
        raise HTTPException(status_code=503, detail="REST client not initialized")
    raw = await rest_client.get_klines(symbol.upper(), interval, limit=min(limit, 500))
    if not raw:
        raise HTTPException(status_code=404, detail="No data found")
    from app.models.market_data import KlineModel
    klines = [
        KlineModel(symbol=symbol.upper(), timeframe=interval, open_time=k[0],
                   open=float(k[1]), high=float(k[2]), low=float(k[3]),
                   close=float(k[4]), volume=float(k[5]), quote_vol=float(k[7]),
                   trades=int(k[8]), taker_buy_vol=float(k[9]), taker_buy_quote_vol=float(k[10]))
        for k in raw
    ]
    engine = FactorEngine()
    factors = engine.compute_factors(symbol.upper(), interval, klines)
    return {"symbol": symbol.upper(), "interval": interval, "factors": factors}


# === Strategies & Signals ===
@app.get("/api/v1/signals/{symbol}")
async def get_signals(symbol: str, interval: str = "1h"):
    if not rest_client:
        raise HTTPException(status_code=503, detail="REST client not initialized")
    raw = await rest_client.get_klines(symbol.upper(), interval, limit=200)
    if not raw:
        raise HTTPException(status_code=404, detail="No data")
    from app.models.market_data import KlineModel
    klines = [
        KlineModel(symbol=symbol.upper(), timeframe=interval, open_time=k[0],
                   open=float(k[1]), high=float(k[2]), low=float(k[3]),
                   close=float(k[4]), volume=float(k[5]), quote_vol=0, trades=0,
                   taker_buy_vol=0, taker_buy_quote_vol=0)
        for k in raw
    ]
    engine = FactorEngine()
    factors = engine.compute_factors(symbol.upper(), interval, klines)
    signals = []
    for strat_cls in [TrendFollowingStrategy, BreakoutStrategy, MeanReversionStrategy]:
        try:
            strat = strat_cls()
            sig = await strat.analyze(symbol.upper(), factors)
            if sig:
                signals.append({
                    "strategy": strat.name,
                    "direction": sig.direction,
                    "confidence": sig.confidence,
                    "reason": sig.reason,
                    "price": sig.price,
                    "stop_loss": sig.stop_loss,
                    "take_profit": sig.take_profit,
                })
        except Exception:
            pass
    return {"symbol": symbol.upper(), "factors_summary": factors, "signals": signals}


# === Backtest ===
@app.post("/api/v1/backtest")
async def run_backtest(
    symbol: str,
    strategy: str = "trend_following",
    interval: str = "1h",
    initial_capital: float = 10000,
):
    if not rest_client:
        raise HTTPException(status_code=503, detail="REST client not initialized")
    raw = await rest_client.get_klines(symbol.upper(), interval, limit=500)
    if not raw:
        raise HTTPException(status_code=404, detail="No data")
    from app.models.market_data import KlineModel
    klines = [
        KlineModel(symbol=symbol.upper(), timeframe=interval, open_time=k[0],
                   open=float(k[1]), high=float(k[2]), low=float(k[3]),
                   close=float(k[4]), volume=float(k[5]), quote_vol=0, trades=0,
                   taker_buy_vol=0, taker_buy_quote_vol=0)
        for k in raw
    ]
    engine = FactorEngine()
    factor_series = engine.compute_factor_series(klines)
    strategy_map = {
        "trend_following": TrendFollowingStrategy,
        "breakout": BreakoutStrategy,
        "mean_reversion": MeanReversionStrategy,
    }
    strat_cls = strategy_map.get(strategy, TrendFollowingStrategy)
    strat = strat_cls()
    bt = BacktestEngine(initial_capital=initial_capital)
    result = await bt.run(strat, symbol.upper(), interval, factor_series)
    return {
        "symbol": symbol.upper(),
        "strategy": strategy,
        "total_return": result.total_return,
        "annual_return": result.annual_return,
        "max_drawdown": result.max_drawdown,
        "sharpe_ratio": result.sharpe_ratio,
        "win_rate": result.win_rate,
        "profit_factor": result.profit_factor,
        "total_trades": result.total_trades,
    }


# === Sandbox ===
@app.post("/api/v1/sandbox/order")
async def sandbox_order(symbol: str, side: str, quantity: float, price: float):
    from app.strategies.base import Signal
    signal = Signal(symbol=symbol.upper(), direction=side.lower(), confidence=0.5, reason="Manual", price=price)
    order = await sandbox.open_position(symbol.upper(), side.upper(), quantity, price, signal)
    return {
        "order_id": order.id,
        "status": order.status,
        "symbol": order.symbol,
        "side": order.side,
        "quantity": order.quantity,
        "price": order.price,
        "pnl": order.pnl,
    }


@app.post("/api/v1/sandbox/close/{symbol}")
async def sandbox_close(symbol: str, price: float):
    order = await sandbox.close_position(symbol.upper(), price)
    if not order:
        raise HTTPException(status_code=404, detail="No open position")
    return {"status": "closed", "pnl": order.pnl}


@app.get("/api/v1/sandbox/portfolio")
async def sandbox_portfolio():
    return sandbox.get_portfolio_summary()


@app.post("/api/v1/sandbox/reset")
async def sandbox_reset():
    sandbox.reset()
    return {"status": "reset"}


# === Memory ===
@app.post("/api/v1/memory/save")
async def save_memory(agent_id: str, content: str, metadata: str = "{}", db: AsyncSession = Depends(get_db)):
    import json
    store = MemoryStore(db)
    entry = await store.save(agent_id=agent_id, content=content, metadata=json.loads(metadata))
    return {"id": entry.id, "status": "saved"}


@app.get("/api/v1/memory/search")
async def search_memory(query: str, agent_id: str = "", top_k: int = 10, db: AsyncSession = Depends(get_db)):
    store = MemoryStore(db)
    results = await store.search(query=query, agent_id=agent_id or None, top_k=min(top_k, 50))
    return {"results": results}


# === Analysis ===
@app.get("/api/v1/analysis/daily/{symbol}")
async def daily_analysis(symbol: str):
    if not rest_client:
        raise HTTPException(status_code=503, detail="REST client not initialized")
    raw = await rest_client.get_klines(symbol.upper(), "1h", limit=200)
    if not raw:
        raise HTTPException(status_code=404, detail="No data")
    from app.models.market_data import KlineModel
    klines = [
        KlineModel(symbol=symbol.upper(), timeframe="1h", open_time=k[0],
                   open=float(k[1]), high=float(k[2]), low=float(k[3]),
                   close=float(k[4]), volume=float(k[5]), quote_vol=0, trades=0,
                   taker_buy_vol=0, taker_buy_quote_vol=0)
        for k in raw
    ]
    engine = FactorEngine()
    factors = engine.compute_factors(symbol.upper(), "1h", klines)
    report = await analyst.generate_daily_report(
        symbol=symbol.upper(),
        factors=factors,
        signals=[],
        structure={"funding_rate": 0, "funding_sentiment": "neutral", "oi_change_pct": 0, "volume_ratio": 1.0},
        positions=sandbox.get_portfolio_summary(),
    )
    return {"symbol": symbol.upper(), "report": report}


# === Scheduler (manual trigger) ===
@app.post("/api/v1/scheduler/trigger-daily")
async def trigger_daily_analysis(symbols: str = "BTCUSDT,ETHUSDT,SOLUSDT"):
    sym_list = [s.strip().upper() for s in symbols.split(",")]
    report = await run_daily_analysis(symbols=sym_list)
    return {"status": "completed", "symbols": sym_list}
