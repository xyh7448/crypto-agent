"""Market data repository - async CRUD for market data models."""
from __future__ import annotations
import logging
from typing import Optional
from sqlalchemy import select, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.market_data import KlineModel, FundingRateModel, OpenInterestModel

logger = logging.getLogger(__name__)


class MarketDataRepository:
    """Async repository for market data persistence."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save_kline(self, kline: KlineModel) -> KlineModel:
        stmt = pg_insert(KlineModel).values(
            symbol=kline.symbol,
            timeframe=kline.timeframe,
            open_time=kline.open_time,
            open=kline.open,
            high=kline.high,
            low=kline.low,
            close=kline.close,
            volume=kline.volume,
            quote_vol=kline.quote_vol,
            trades=kline.trades,
            taker_buy_vol=kline.taker_buy_vol,
            taker_buy_quote_vol=kline.taker_buy_quote_vol,
        ).on_conflict_do_update(
            constraint="uq_kline_symbol_timeframe_open_time",
            set_={
                "open": kline.open,
                "high": kline.high,
                "low": kline.low,
                "close": kline.close,
                "volume": kline.volume,
                "quote_vol": kline.quote_vol,
                "trades": kline.trades,
                "taker_buy_vol": kline.taker_buy_vol,
                "taker_buy_quote_vol": kline.taker_buy_quote_vol,
            },
        )
        await self.session.execute(stmt)
        await self.session.commit()
        return kline

    async def batch_save_kline(self, klines: list[KlineModel]) -> int:
        if not klines:
            return 0
        values = [
            {
                "symbol": k.symbol,
                "timeframe": k.timeframe,
                "open_time": k.open_time,
                "open": k.open,
                "high": k.high,
                "low": k.low,
                "close": k.close,
                "volume": k.volume,
                "quote_vol": k.quote_vol,
                "trades": k.trades,
                "taker_buy_vol": k.taker_buy_vol,
                "taker_buy_quote_vol": k.taker_buy_quote_vol,
            }
            for k in klines
        ]
        stmt = pg_insert(KlineModel).values(values)
        stmt = stmt.on_conflict_do_nothing(constraint="uq_kline_symbol_timeframe_open_time")
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount

    async def get_klines(
        self,
        symbol: str,
        timeframe: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 200,
    ) -> list[KlineModel]:
        query = select(KlineModel).where(
            KlineModel.symbol == symbol,
            KlineModel.timeframe == timeframe,
        )
        if start_time:
            query = query.where(KlineModel.open_time >= start_time)
        if end_time:
            query = query.where(KlineModel.open_time <= end_time)
        query = query.order_by(KlineModel.open_time.desc()).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def save_funding_rate(self, fr: FundingRateModel) -> FundingRateModel:
        stmt = pg_insert(FundingRateModel).values(
            symbol=fr.symbol,
            funding_time=fr.funding_time,
            funding_rate=fr.funding_rate,
            mark_price=fr.mark_price,
            index_price=fr.index_price,
            settle_time=fr.settle_time,
        ).on_conflict_do_update(
            constraint="uq_funding_rate_symbol_time",
            set_={
                "funding_rate": fr.funding_rate,
                "mark_price": fr.mark_price,
                "index_price": fr.index_price,
            },
        )
        await self.session.execute(stmt)
        await self.session.commit()
        return fr

    async def get_funding_rates(self, symbol: str, limit: int = 100) -> list[FundingRateModel]:
        query = (
            select(FundingRateModel)
            .where(FundingRateModel.symbol == symbol)
            .order_by(FundingRateModel.funding_time.desc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def save_open_interest(self, oi: OpenInterestModel) -> OpenInterestModel:
        stmt = pg_insert(OpenInterestModel).values(
            symbol=oi.symbol,
            oi_time=oi.oi_time,
            open_interest=oi.open_interest,
            open_interest_value=oi.open_interest_value,
        ).on_conflict_do_update(
            constraint="uq_oi_symbol_time",
            set_={
                "open_interest": oi.open_interest,
                "open_interest_value": oi.open_interest_value,
            },
        )
        await self.session.execute(stmt)
        await self.session.commit()
        return oi

    async def get_latest_oi(self, symbol: str) -> Optional[OpenInterestModel]:
        query = (
            select(OpenInterestModel)
            .where(OpenInterestModel.symbol == symbol)
            .order_by(OpenInterestModel.oi_time.desc())
            .limit(1)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
