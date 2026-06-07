"""Binance Futures REST API client."""
from __future__ import annotations
import hashlib
import hmac
import time
import json
import logging
from typing import Any, Optional
from urllib.parse import urlencode

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

BASE_URL = "https://fapi.binance.com"


class BinanceRestClient:
    """Async Binance Futures REST API client with HMAC signing."""

    def __init__(self) -> None:
        self.api_key = settings.BINANCE_API_KEY
        self.api_secret = settings.BINANCE_API_SECRET
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=BASE_URL,
                headers={"X-MBX-APIKEY": self.api_key},
                timeout=httpx.Timeout(30.0),
            )
        return self._client

    def _sign(self, params: dict[str, Any]) -> dict[str, Any]:
        query = urlencode(params)
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            query.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        params["signature"] = signature
        return params

    async def _request(
        self, method: str, path: str, signed: bool = False, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        client = await self._get_client()
        req_params = params or {}
        if signed:
            req_params["timestamp"] = int(time.time() * 1000)
            req_params = self._sign(req_params)

        try:
            response = await client.request(method, path, params=req_params if not signed else None, data=req_params if signed else None)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error("Binance API error: %s %s - %s", method, path, e.response.text)
            raise
        except httpx.TimeoutException:
            logger.error("Binance API timeout: %s %s", method, path)
            raise

    async def get_klines(
        self, symbol: str, interval: str, start_time: int | None = None,
        end_time: int | None = None, limit: int = 1000,
    ) -> list[list[Any]]:
        params = {"symbol": symbol.upper(), "interval": interval, "limit": min(limit, 1500)}
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time
        return await self._request("GET", "/fapi/v1/klines", params=params)

    async def get_funding_rate(
        self, symbol: str, start_time: int | None = None,
        end_time: int | None = None, limit: int = 100,
    ) -> list[dict[str, Any]]:
        params = {"symbol": symbol.upper(), "limit": min(limit, 1000)}
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time
        return await self._request("GET", "/fapi/v1/fundingRate", params=params)

    async def get_open_interest(
        self, symbol: str, period: str = "1h", limit: int = 100,
    ) -> list[dict[str, Any]]:
        params = {"symbol": symbol.upper(), "period": period, "limit": min(limit, 500)}
        return await self._request("GET", "/futures/data/openInterestHist", params=params)

    async def get_exchange_info(self) -> dict[str, Any]:
        return await self._request("GET", "/fapi/v1/exchangeInfo")

    async def get_ticker(self, symbol: str) -> dict[str, Any]:
        return await self._request("GET", "/fapi/v1/ticker/24hr", params={"symbol": symbol.upper()})

    async def get_account_info(self) -> dict[str, Any]:
        return await self._request("GET", "/fapi/v2/account", signed=True)

    async def get_position_info(self, symbol: str | None = None) -> list[dict[str, Any]]:
        params = {}
        if symbol:
            params["symbol"] = symbol.upper()
        return await self._request("GET", "/fapi/v2/positionRisk", signed=True, params=params)

    async def place_order(self, params: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/fapi/v1/order", signed=True, params=params)

    async def cancel_order(self, symbol: str, order_id: int) -> dict[str, Any]:
        return await self._request(
            "DELETE", "/fapi/v1/order", signed=True,
            params={"symbol": symbol.upper(), "orderId": order_id},
        )

    async def get_open_orders(self, symbol: str | None = None) -> list[dict[str, Any]]:
        params = {}
        if symbol:
            params["symbol"] = symbol.upper()
        return await self._request("GET", "/fapi/v1/openOrders", signed=True, params=params)

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
