"""Scheduled tasks - daily analysis and report generation."""
from __future__ import annotations
import asyncio
import json
import logging
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select, desc

from app.core.config import settings
from app.core.logger import get_logger
from app.market_data.binance_rest import BinanceRestClient
from app.market_data.data_manager import MarketDataManager
from app.factors.engine import FactorEngine
from app.analyst.agent import AnalystAgent
from app.notification.feishu import FeishuNotifier
from app.memory.store import MemoryStore
from app.models.market_data import KlineModel

logger = get_logger(__name__)

# Symbols to analyze daily
DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
TIMEFRAME = "1h"
LOOKBACK_BARS = 200


async def run_daily_analysis(
    symbols: list[str] | None = None,
    db_session: AsyncSession | None = None,
) -> str:
    """Run daily market analysis for all configured symbols."""
    symbols = symbols or DEFAULT_SYMBOLS
    engine = create_async_engine(settings.POSTGRES_URI)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    rest = BinanceRestClient()
    analyst = AnalystAgent()
    notifier = FeishuNotifier()

    reports = []

    for symbol in symbols:
        try:
            async with session_factory() as session:
                factor_engine = FactorEngine(session=session)
                store = MemoryStore(session)

                # Fetch recent klines
                raw = await rest.get_klines(symbol, TIMEFRAME, limit=LOOKBACK_BARS)
                klines = []
                for k in raw:
                    klines.append(KlineModel(
                        symbol=symbol,
                        timeframe=TIMEFRAME,
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

                # Get funding rates
                fr_raw = await rest.get_funding_rate(symbol, limit=24)
                funding_rate_models = []
                for f in fr_raw:
                    from app.models.market_data import FundingRateModel
                    funding_rate_models.append(FundingRateModel(
                        symbol=symbol,
                        funding_time=f.get("fundingTime", 0),
                        funding_rate=float(f.get("fundingRate", 0)),
                    ))

                fr_values = [float(f.get("fundingRate", 0)) for f in fr_raw] if fr_raw else []

                # Get OI data
                oi_raw = await rest.get_open_interest(symbol, period="1h", limit=24)
                oi_series = [float(o['sumOpenInterest']) for o in oi_raw] if oi_raw else []

                # Compute factors with ALL data
                factors = factor_engine.compute_factors(
                    symbol, TIMEFRAME, klines,
                    funding_rates=funding_rate_models,
                    oi_series=oi_series,
                )
                await factor_engine.compute_and_save(
                    symbol, TIMEFRAME, klines,
                    funding_rates=funding_rate_models,
                    oi_series=oi_series,
                )

                # 24h price change
                price_change_24h = 0.0
                if len(klines) >= 24:
                    price_change_24h = (klines[-1].close - klines[-24].close) / klines[-24].close * 100
                factors["price_change_24h"] = round(price_change_24h, 2)

                # Additional structure data
                structure = {
                    "funding_rate": factors.get("funding_rate", 0),
                    "funding_sentiment": factors.get("funding_sentiment", "neutral"),
                    "oi_change_pct": factors.get("oi_change_pct", 0),
                    "volume_ratio": factors.get("volume_ratio", 1.0),
                    "price_change_24h": factors.get("price_change_24h", 0),
                    "recent_funding_rates": [{
                        "time": f.funding_time,
                        "rate": f.funding_rate,
                    } for f in funding_rate_models[-8:]] if funding_rate_models else [],
                }

                # Generate analysis report
                report = await analyst.generate_daily_report(
                    symbol=symbol,
                    factors=factors,
                    signals=[],
                    structure=structure,
                    positions={},
                )
                reports.append(report)

                # Save to memory
                await store.save(
                    agent_id="crypto-analyst",
                    content=report,
                    metadata={
                        "type": "daily_analysis",
                        "symbol": symbol,
                        "timestamp": datetime.utcnow().isoformat(),
                        "factors": {k: v for k, v in factors.items() if isinstance(v, (int, float, str))},
                    },
                )

                logger.info("Analysis complete for %s", symbol)

        except Exception as e:
            logger.error("Analysis failed for %s: %s", symbol, e, exc_info=True)
            reports.append(f"❌ {symbol}: Analysis failed - {e}")

    # Combine and send report
    full_report = "\n\n".join(reports)
    header = f"📊 **Daily Crypto Analysis**\n{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n\n"
    full_report = header + full_report

    await notifier.send_markdown("Crypto Daily Report", full_report)

    # Cleanup
    await rest.close()
    await notifier.close()

    return full_report
