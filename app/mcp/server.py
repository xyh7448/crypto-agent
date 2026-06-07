"""MCP Protocol Server - exposes all agent tools via MCP stdio transport."""
from __future__ import annotations
import asyncio
import json
import logging
import sys
import time
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.core.config import settings
from app.core.logger import get_logger
from app.market_data.binance_rest import BinanceRestClient
from app.market_data.repository import MarketDataRepository
from app.factors.engine import FactorEngine
from app.factors.technical import sma, ema, macd, rsi, atr, bollinger_bands
from app.strategies.trend_following import TrendFollowingStrategy
from app.strategies.breakout import BreakoutStrategy
from app.strategies.mean_reversion import MeanReversionStrategy
from app.backtest.engine import BacktestEngine
from app.execution.sandbox import TradingSandbox
from app.execution.risk import RiskEngine
from app.memory.store import MemoryStore
from app.analyst.agent import AnalystAgent
from app.models.market_data import KlineModel

logger = get_logger(__name__)


class MCPServer:
    """MCP stdio server exposing quant agent tools."""

    def __init__(self) -> None:
        self._engine = create_async_engine(settings.POSTGRES_URI)
        self._session_factory = async_sessionmaker(self._engine, expire_on_commit=False)
        self._sandbox = TradingSandbox()
        self._risk = RiskEngine()
        self._backtest = BacktestEngine()
        self._analyst = AnalystAgent()
        self._rest = BinanceRestClient()

    async def _get_session(self) -> AsyncSession:
        return self._session_factory()

    async def _get_repo(self, session: AsyncSession) -> MarketDataRepository:
        return MarketDataRepository(session)

    async def handle_request(self, req: dict[str, Any]) -> dict[str, Any]:
        """Handle an MCP JSON-RPC request."""
        method = req.get("method", "")
        req_id = req.get("id", 1)
        params = req.get("params", {})
        args = params.get("arguments", {}) if isinstance(params, dict) and "arguments" in params else params

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "crypto-agent", "version": "1.0.0"},
                },
            }

        if method == "list_tools":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": [
                        {
                            "name": "get_market_data",
                            "description": "Get kline market data for a symbol",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "symbol": {"type": "string"},
                                    "interval": {"type": "string"},
                                    "limit": {"type": "integer", "default": 100},
                                },
                                "required": ["symbol"],
                            },
                        },
                        {
                            "name": "calculate_factors",
                            "description": "Calculate technical factors for a symbol",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "symbol": {"type": "string"},
                                    "interval": {"type": "string", "default": "1h"},
                                    "limit": {"type": "integer", "default": 200},
                                },
                                "required": ["symbol"],
                            },
                        },
                        {
                            "name": "run_backtest",
                            "description": "Run strategy backtest on historical data",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "symbol": {"type": "string"},
                                    "strategy": {"type": "string", "enum": ["trend_following", "breakout", "mean_reversion"]},
                                    "interval": {"type": "string", "default": "1h"},
                                    "initial_capital": {"type": "number", "default": 10000},
                                },
                                "required": ["symbol", "strategy"],
                            },
                        },
                        {
                            "name": "generate_signal",
                            "description": "Generate trading signal using all strategies",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "symbol": {"type": "string"},
                                    "interval": {"type": "string", "default": "1h"},
                                },
                                "required": ["symbol"],
                            },
                        },
                        {
                            "name": "save_memory",
                            "description": "Save a memory entry for an agent",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "agent_id": {"type": "string"},
                                    "content": {"type": "string"},
                                    "metadata": {"type": "object"},
                                },
                                "required": ["agent_id", "content"],
                            },
                        },
                        {
                            "name": "query_memory",
                            "description": "Search memories by semantic similarity",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "query": {"type": "string"},
                                    "agent_id": {"type": "string"},
                                    "top_k": {"type": "integer", "default": 10},
                                },
                                "required": ["query"],
                            },
                        },
                        {
                            "name": "execute_sandbox_order",
                            "description": "Execute a simulated order in sandbox",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "symbol": {"type": "string"},
                                    "side": {"type": "string", "enum": ["LONG", "SHORT"]},
                                    "quantity": {"type": "number"},
                                    "price": {"type": "number"},
                                },
                                "required": ["symbol", "side", "quantity", "price"],
                            },
                        },
                        {
                            "name": "generate_daily_report",
                            "description": "Generate daily analysis report for a symbol",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "symbol": {"type": "string"},
                                },
                                "required": ["symbol"],
                            },
                        },
                        {
                            "name": "get_portfolio",
                            "description": "Get sandbox portfolio summary",
                            "inputSchema": {"type": "object", "properties": {}},
                        },
                        {
                            "name": "get_funding_rate",
                            "description": "Get current funding rate and OI data",
                            "inputSchema": {
                                "type": "object",
                                "properties": {"symbol": {"type": "string"}},
                                "required": ["symbol"],
                            },
                        },
                    ],
                },
            }

        if method == "call_tool":
            tool = params.get("name", "") if isinstance(params, dict) else ""
            tool_args = args

            try:
                if tool == "get_market_data":
                    return await self._tool_get_market_data(tool_args, req_id)
                elif tool == "calculate_factors":
                    return await self._tool_calculate_factors(tool_args, req_id)
                elif tool == "run_backtest":
                    return await self._tool_run_backtest(tool_args, req_id)
                elif tool == "generate_signal":
                    return await self._tool_generate_signal(tool_args, req_id)
                elif tool == "save_memory":
                    return await self._tool_save_memory(tool_args, req_id)
                elif tool == "query_memory":
                    return await self._tool_query_memory(tool_args, req_id)
                elif tool == "execute_sandbox_order":
                    return await self._tool_sandbox_order(tool_args, req_id)
                elif tool == "generate_daily_report":
                    return await self._tool_daily_report(tool_args, req_id)
                elif tool == "get_portfolio":
                    return self._make_response(req_id, {"content": [{"type": "text", "text": json.dumps(self._sandbox.get_portfolio_summary(), default=str)}]})
                elif tool == "get_funding_rate":
                    return await self._tool_funding_rate(tool_args, req_id)
                else:
                    return self._make_response(req_id, {"content": [{"type": "text", "text": json.dumps({"error": f"Unknown tool: {tool}"})}]})
            except Exception as e:
                logger.error("Tool error: %s", e, exc_info=True)
                return self._make_error(req_id, str(e))

        return self._make_error(req_id, f"Unknown method: {method}")

    def _make_response(self, req_id: int, result: dict) -> dict:
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    def _make_error(self, req_id: int, message: str) -> dict:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32000, "message": message}}

    async def _tool_get_market_data(self, args: dict, req_id: int) -> dict:
        symbol = args.get("symbol", "BTCUSDT").upper()
        interval = args.get("interval", "1h")
        limit = min(args.get("limit", 100), 500)
        raw = await self._rest.get_klines(symbol, interval, limit=limit)
        data = [
            {"time": k[0], "open": float(k[1]), "high": float(k[2]), "low": float(k[3]),
             "close": float(k[4]), "volume": float(k[5])}
            for k in raw
        ]
        return self._make_response(req_id, {"content": [{"type": "text", "text": json.dumps(data, default=str)}]})

    async def _tool_calculate_factors(self, args: dict, req_id: int) -> dict:
        symbol = args.get("symbol", "BTCUSDT").upper()
        interval = args.get("interval", "1h")
        limit = min(args.get("limit", 200), 500)
        raw = await self._rest.get_klines(symbol, interval, limit=limit)
        klines = [
            KlineModel(symbol=symbol, timeframe=interval, open_time=k[0],
                       open=float(k[1]), high=float(k[2]), low=float(k[3]),
                       close=float(k[4]), volume=float(k[5]), quote_vol=0, trades=0,
                       taker_buy_vol=0, taker_buy_quote_vol=0)
            for k in raw
        ]
        async with await self._get_session() as session:
            engine = FactorEngine(session=session)
            factors = engine.compute_factors(symbol, interval, klines)
        return self._make_response(req_id, {"content": [{"type": "text", "text": json.dumps(factors, default=str)}]})

    async def _tool_run_backtest(self, args: dict, req_id: int) -> dict:
        symbol = args.get("symbol", "BTCUSDT").upper()
        strategy_name = args.get("strategy", "trend_following")
        interval = args.get("interval", "1h")
        initial_capital = args.get("initial_capital", 10000)
        limit = 500

        raw = await self._rest.get_klines(symbol, interval, limit=limit)
        klines = [
            KlineModel(symbol=symbol, timeframe=interval, open_time=k[0],
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
        strategy_cls = strategy_map.get(strategy_name, TrendFollowingStrategy)
        strategy = strategy_cls()

        bt = BacktestEngine(initial_capital=initial_capital)
        result = await bt.run(strategy, symbol, interval, factor_series)
        return self._make_response(req_id, {
            "content": [{"type": "text", "text": json.dumps({
                "total_return": result.total_return,
                "annual_return": result.annual_return,
                "max_drawdown": result.max_drawdown,
                "sharpe_ratio": result.sharpe_ratio,
                "win_rate": result.win_rate,
                "profit_factor": result.profit_factor,
                "total_trades": result.total_trades,
            }, default=str)}]
        })

    async def _tool_generate_signal(self, args: dict, req_id: int) -> dict:
        symbol = args.get("symbol", "BTCUSDT").upper()
        interval = args.get("interval", "1h")
        raw = await self._rest.get_klines(symbol, interval, limit=200)
        klines = [
            KlineModel(symbol=symbol, timeframe=interval, open_time=k[0],
                       open=float(k[1]), high=float(k[2]), low=float(k[3]),
                       close=float(k[4]), volume=float(k[5]), quote_vol=0, trades=0,
                       taker_buy_vol=0, taker_buy_quote_vol=0)
            for k in raw
        ]
        engine = FactorEngine()
        factors = engine.compute_factors(symbol, interval, klines)

        signals = []
        for strategy_cls in [TrendFollowingStrategy, BreakoutStrategy, MeanReversionStrategy]:
            try:
                strat = strategy_cls()
                sig = await strat.analyze(symbol, factors)
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
            except Exception as e:
                logger.warning("Strategy %s error: %s", strategy_cls.__name__, e)

        return self._make_response(req_id, {
            "content": [{"type": "text", "text": json.dumps({
                "symbol": symbol,
                "factors": {k: v for k, v in factors.items() if isinstance(v, (int, float))},
                "signals": signals,
            }, default=str)}]
        })

    async def _tool_save_memory(self, args: dict, req_id: int) -> dict:
        async with await self._get_session() as session:
            store = MemoryStore(session)
            entry = await store.save(
                agent_id=args.get("agent_id", "crypto-agent"),
                content=args.get("content", ""),
                metadata=args.get("metadata", {}),
            )
        return self._make_response(req_id, {
            "content": [{"type": "text", "text": json.dumps({"id": entry.id, "status": "saved"}, default=str)}]
        })

    async def _tool_query_memory(self, args: dict, req_id: int) -> dict:
        async with await self._get_session() as session:
            store = MemoryStore(session)
            results = await store.search(
                query=args.get("query", ""),
                agent_id=args.get("agent_id"),
                top_k=args.get("top_k", 10),
            )
        return self._make_response(req_id, {
            "content": [{"type": "text", "text": json.dumps(results, default=str)}]
        })

    async def _tool_sandbox_order(self, args: dict, req_id: int) -> dict:
        order = await self._sandbox.open_position(
            symbol=args.get("symbol", "").upper(),
            side=args.get("side", "LONG").upper(),
            quantity=float(args.get("quantity", 0)),
            price=float(args.get("price", 0)),
        )
        return self._make_response(req_id, {
            "content": [{"type": "text", "text": json.dumps({
                "order_id": order.id,
                "status": order.status,
                "symbol": order.symbol,
                "side": order.side,
                "quantity": order.quantity,
                "price": order.price,
            }, default=str)}]
        })

    async def _tool_daily_report(self, args: dict, req_id: int) -> dict:
        symbol = args.get("symbol", "BTCUSDT").upper()
        raw = await self._rest.get_klines(symbol, "1h", limit=200)
        klines = [
            KlineModel(symbol=symbol, timeframe="1h", open_time=k[0],
                       open=float(k[1]), high=float(k[2]), low=float(k[3]),
                       close=float(k[4]), volume=float(k[5]), quote_vol=0, trades=0,
                       taker_buy_vol=0, taker_buy_quote_vol=0)
            for k in raw
        ]
        engine = FactorEngine()
        factors = engine.compute_factors(symbol, "1h", klines)
        report = await self._analyst.generate_daily_report(
            symbol=symbol,
            factors=factors,
            signals=[],
            structure={"funding_rate": 0, "funding_sentiment": "neutral", "oi_change_pct": 0, "volume_ratio": 1.0},
            positions=self._sandbox.get_portfolio_summary(),
        )
        return self._make_response(req_id, {
            "content": [{"type": "text", "text": report}]
        })

    async def _tool_funding_rate(self, args: dict, req_id: int) -> dict:
        symbol = args.get("symbol", "BTCUSDT").upper()
        fr = await self._rest.get_funding_rate(symbol, limit=24)
        oi = await self._rest.get_open_interest(symbol, period="1h", limit=24)
        return self._make_response(req_id, {
            "content": [{"type": "text", "text": json.dumps({
                "funding_rates": [{"time": f[0], "rate": float(f[4])} for f in fr],
                "open_interest": [{"time": o[0], "value": float(o[4])} for o in oi],
            }, default=str)}]
        })

    async def run_stdio(self) -> None:
        """Run MCP server over stdin/stdout transport."""
        logger.info("MCP server starting on stdio")
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
                resp = await self.handle_request(req)
                sys.stdout.write(json.dumps(resp) + "\n")
                sys.stdout.flush()
            except json.JSONDecodeError as e:
                err = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": f"Parse error: {e}"}}
                sys.stdout.write(json.dumps(err) + "\n")
                sys.stdout.flush()
            except Exception as e:
                err = {"jsonrpc": "2.0", "id": None, "error": {"code": -32000, "message": str(e)}}
                sys.stdout.write(json.dumps(err) + "\n")
                sys.stdout.flush()
