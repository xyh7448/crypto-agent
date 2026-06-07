"""Market data manager - orchestrates REST, WebSocket, and repository."""
from __future__ import annotations
import logging
import time
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.market_data.binance_rest import BinanceRestClient
from app.market_data.binance_ws import BinanceWebSocketManager
from app.market_data.repository import MarketDataRepository
from app.models.market_data import KlineModel, FundingRateModel, OpenInterestModel

logger = logging.getLogger(__name__)

INTERVAL_MS = {
    "1m": 60_000, "5m": 300_000, "15m": 900_000,
    "30m": 1_800_000, "1h": 3_600_000, "4h": 14_400_000,
    "1d": 86_400_000, "1w": 604_800_000,
}


class MarketDataManager:
    """Orchestrates market data ingestion from REST and WebSocket."""

    def __init__(
        self,
        session: AsyncSession | None = None,
        repo: MarketDataRepository | None = None,
        rest: BinanceRestClient | None = None,
        ws: BinanceWebSocketManager | None = None,
    ) -> None:
        self.repo = repo or (MarketDataRepository(session) if session else None)
        self.rest = rest or BinanceRestClient()
        self.ws = ws or BinanceWebSocketManager()
        self._running = False

    async def sync_historical_klines(
        self,
        symbol: str,
        interval: str,
        start_str: str,
        end_str: str | None = None,
        batch_size: int = 1000,
    ) -> int:
        """Sync historical klines from Binance REST to database."""
        total = 0
        start_ms = int(
            time.mktime(time.strptime(start_str, "%Y-%m-%d")) * 1000
        )
        end_ms = (
            int(time.mktime(time.strptime(end_str, "%Y-%m-%d")) * 1000)
            if end_str else int(time.time() * 1000)
        )

        current_start = start_ms
        while current_start < end_ms:
            try:
                raw = await self.rest.get_klines(
                    symbol=symbol,
                    interval=interval,
                    start_time=current_start,
                    end_time=min(current_start + batch_size * INTERVAL_MS.get(interval, 60_000), end_ms),
                    limit=batch_size,
                )
            except Exception as e:
                logger.error("Failed to fetch klines for %s: %s", symbol, e)
                break

            if not raw:
                break

            models = []
            for k in raw:
                models.append(KlineModel(
                    symbol=symbol.upper(),
                    timeframe=interval,
                    open_time=k[0],
                    open=float(k[1]),
                    high=float(k[2]),
                    low=float(k[3]),
                    close=float(k[4]),
                    volume=float(k[5]),
                    quote_vol=float(k[7]),
                    trades=int(k[8]),
                    taker_buy_vol=float(k[9]),
                    taker_buy_quote_vol=float(k[10]),
                ))

            if self.repo:
                await self.repo.batch_save_kline(models)
            total += len(models)
            current_start = raw[-1][0] + 1

            if len(raw) < batch_size:
                break

            await asyncio.sleep(0.1)

        logger.info("Synced %d klines for %s %s", total, symbol, interval)
        return total

    async def start_realtime_updates(
        self, symbols: list[str], intervals: list[str] | None = None
    ) -> None:
        """Start real-time WebSocket subscriptions for given symbols."""
        self._running = True
        streams = []

        for symbol in symbols:
            if intervals:
                for interval in intervals:
                    streams.append(f"{symbol.lower()}@kline_{interval}")
            streams.append(f"{symbol.lower()}@depth20@100ms")
            streams.append(f"{symbol.lower()}@markPrice@1s")

        self.ws.on_message("kline", self._handle_kline)
        self.ws.on_message("depth", self._handle_depth)
        self.ws.on_message("markPrice", self._handle_mark_price)

        await self.ws.connect(streams)
        logger.info("Real-time updates started for %d symbols", len(symbols))

    async def _handle_kline(self, data: dict[str, Any]) -> None:
        k = data.get("k", {})
        model = KlineModel(
            symbol=k.get("s", ""),
            timeframe=k.get("i", ""),
            open_time=k.get("t", 0),
            open=float(k.get("o", 0)),
            high=float(k.get("h", 0)),
            low=float(k.get("l", 0)),
            close=float(k.get("c", 0)),
            volume=float(k.get("v", 0)),
            quote_vol=float(k.get("q", 0)),
            trades=int(k.get("n", 0)),
            taker_buy_vol=float(k.get("V", 0)),
            taker_buy_quote_vol=float(k.get("Q", 0)),
        )
        if self.repo:
            await self.repo.save_kline(model)

    async def _handle_depth(self, data: dict[str, Any]) -> None:
        pass  # Depth data consumed in-memory by strategies

    async def _handle_mark_price(self, data: dict[str, Any]) -> None:
        fr = FundingRateModel(
            symbol=data.get("s", ""),
            funding_time=data.get("E", 0),
            funding_rate=float(data.get("r", 0)),
            mark_price=float(data.get("p", 0)),
            index_price=float(data.get("i", 0)),
            settle_time=data.get("T", 0),
        )
        if self.repo:
            await self.repo.save_funding_rate(fr)

    async def stop(self) -> None:
        self._running = False
        if self.ws:
            await self.ws.close()
        if self.rest:
            await self.rest.close()
        logger.info("Market data manager stopped")


import asyncio
