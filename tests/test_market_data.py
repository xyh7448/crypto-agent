"""Test market data repository and models."""
from __future__ import annotations
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market_data import KlineModel


class TestKlineModel:
    async def test_create_kline(self, db_session: AsyncSession):
        kline = KlineModel(
            symbol="BTCUSDT",
            timeframe="1h",
            open_time=1700000000000,
            open=50000.0,
            high=51000.0,
            low=49000.0,
            close=50500.0,
            volume=1000.5,
            quote_vol=50000000.0,
            trades=10000,
            taker_buy_vol=600.0,
            taker_buy_quote_vol=30000000.0,
        )
        db_session.add(kline)
        await db_session.commit()

        result = await db_session.execute(
            select(KlineModel).where(KlineModel.symbol == "BTCUSDT")
        )
        saved = result.scalar_one()
        assert saved.symbol == "BTCUSDT"
        assert saved.close == 50500.0
        assert saved.open_time == 1700000000000

    async def test_unique_constraint(self, db_session: AsyncSession):
        k1 = KlineModel(symbol="ETHUSDT", timeframe="1h", open_time=1700000000000,
                        open=3000.0, high=3100.0, low=2900.0, close=3050.0,
                        volume=100.0, quote_vol=300000.0, trades=1000,
                        taker_buy_vol=50.0, taker_buy_quote_vol=150000.0)
        k2 = KlineModel(symbol="ETHUSDT", timeframe="1h", open_time=1700000000000,
                        open=3010.0, high=3110.0, low=2910.0, close=3060.0,
                        volume=110.0, quote_vol=310000.0, trades=1100,
                        taker_buy_vol=55.0, taker_buy_quote_vol=160000.0)
        db_session.add(k1)
        await db_session.commit()
        db_session.add(k2)
        await db_session.commit()  # Upsert - should not raise

        result = await db_session.execute(
            select(KlineModel).where(KlineModel.symbol == "ETHUSDT")
        )
        rows = result.scalars().all()
        assert len(rows) == 1  # Only one row due to upsert
