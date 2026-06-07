"""Binance Futures WebSocket stream manager with auto-reconnection."""
from __future__ import annotations
import asyncio
import json
import logging
from typing import Any, AsyncIterator, Callable, Optional

import websockets.asyncio.client as ws_client
from websockets.asyncio.client import ClientConnection

logger = logging.getLogger(__name__)

WS_BASE = "wss://fstream.binance.com/ws"

STREAM_KLINE = "{symbol}@kline_{interval}"
STREAM_DEPTH = "{symbol}@depth20@100ms"
STREAM_MARK_PRICE = "{symbol}@markPrice@1s"


class BinanceWebSocketManager:
    """Manages multiple Binance WebSocket streams with auto-reconnect."""

    def __init__(self, urls: list[str] | None = None) -> None:
        self._connections: dict[str, ClientConnection] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._handlers: dict[str, list[Callable]] = {}
        self._running = False
        self._lock = asyncio.Lock()
        self._reconnect_delay = 1.0
        self._max_reconnect_delay = 64.0

    def on_message(self, stream: str, handler: Callable) -> None:
        if stream not in self._handlers:
            self._handlers[stream] = []
        self._handlers[stream].append(handler)

    async def connect(self, streams: list[str]) -> None:
        """Connect to multiple streams. Each stream gets its own connection."""
        self._running = True
        tasks = []
        for stream in streams:
            tasks.append(self._connect_single(stream))
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _connect_single(self, stream: str) -> None:
        url = f"{WS_BASE}/{stream}"
        while self._running:
            try:
                logger.info("Connecting to stream: %s", stream)
                async with ws_client.connect(url) as ws:
                    self._reconnect_delay = 1.0
                    async for message in ws:
                        if not self._running:
                            break
                        data = json.loads(message)
                        await self._dispatch(stream, data)
            except (websockets.exceptions.ConnectionClosed, OSError) as e:
                logger.warning("Stream %s disconnected: %s. Reconnecting in %.1fs", stream, e, self._reconnect_delay)
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(self._reconnect_delay * 2, self._max_reconnect_delay)
            except Exception as e:
                logger.error("Stream %s error: %s", stream, e, exc_info=True)
                await asyncio.sleep(self._reconnect_delay)

    async def _dispatch(self, stream: str, data: dict[str, Any]) -> None:
        handlers = self._handlers.get(stream, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(data)
                else:
                    handler(data)
            except Exception as e:
                logger.error("Handler error for stream %s: %s", stream, e, exc_info=True)

    async def subscribe_kline(self, symbol: str, interval: str) -> str:
        stream = STREAM_KLINE.format(symbol=symbol.lower(), interval=interval)
        asyncio.create_task(self._connect_single(stream))
        return stream

    async def subscribe_depth(self, symbol: str) -> str:
        stream = STREAM_DEPTH.format(symbol=symbol.lower())
        asyncio.create_task(self._connect_single(stream))
        return stream

    async def subscribe_continuous(self, symbol: str) -> str:
        stream = STREAM_MARK_PRICE.format(symbol=symbol.lower())
        asyncio.create_task(self._connect_single(stream))
        return stream

    async def close(self) -> None:
        self._running = False
        for task in self._tasks.values():
            task.cancel()
        self._tasks.clear()
        self._connections.clear()
        logger.info("WebSocket manager closed")
