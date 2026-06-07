"""Factor computation engine - computes all technical + market structure factors."""
from __future__ import annotations
import logging
import time
from typing import Any, Optional

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market_data import KlineModel, FundingRateModel, OpenInterestModel
from app.models.factor import FactorSnapshotModel
from app.factors import technical as tech
from app.factors import market_structure as ms

logger = logging.getLogger(__name__)


class FactorEngine:
    """Computes and persists factor snapshots."""

    def __init__(self, session: AsyncSession | None = None) -> None:
        self.session = session

    def _extract_close(self, klines: list[KlineModel]) -> list[float]:
        return [k.close for k in klines]

    def _extract_high(self, klines: list[KlineModel]) -> list[float]:
        return [k.high for k in klines]

    def _extract_low(self, klines: list[KlineModel]) -> list[float]:
        return [k.low for k in klines]

    def _extract_volume(self, klines: list[KlineModel]) -> list[float]:
        return [k.volume for k in klines]

    def compute_factors(
        self,
        symbol: str,
        timeframe: str,
        klines: list[KlineModel],
        funding_rates: list[FundingRateModel] | None = None,
        oi_series: list[float] | None = None,
    ) -> dict[str, Any]:
        """Compute all factors for the latest bar. Returns a dict."""
        if not klines:
            return {}

        closes = self._extract_close(klines)
        highs = self._extract_high(klines)
        lows = self._extract_low(klines)
        volumes = self._extract_volume(klines)

        # Technical factors
        sma_20 = tech.sma(closes, 20)
        sma_50 = tech.sma(closes, 50)
        sma_200 = tech.sma(closes, 200)
        ema_12 = tech.ema(closes, 12)
        ema_26 = tech.ema(closes, 26)
        macd_result = tech.macd(closes)
        rsi_result = tech.rsi(closes)
        atr_result = tech.atr(highs, lows, closes)
        bb = tech.bollinger_bands(closes)

        # Market structure factors
        fr_signal = ms.funding_rate_signal(
            [fr.funding_rate for fr in funding_rates] if funding_rates else []
        )
        oi_data = ms.oi_change(oi_series or [])
        vol_data = ms.volume_delta(volumes)

        latest_idx = len(closes) - 1

        factors: dict[str, Any] = {
            "close": closes[latest_idx],
            "sma_20": sma_20[latest_idx],
            "sma_50": sma_50[latest_idx],
            "sma_200": sma_200[latest_idx],
            "ema_12": ema_12[latest_idx],
            "ema_26": ema_26[latest_idx],
            "macd_line": macd_result["macd_line"][latest_idx],
            "macd_signal": macd_result["signal_line"][latest_idx] if macd_result["signal_line"][latest_idx] is not None else 0,
            "macd_histogram": macd_result["histogram"][latest_idx],
            "rsi_14": rsi_result[latest_idx],
            "atr_14": atr_result[latest_idx],
            "boll_ub": bb["upper"][latest_idx],
            "boll_mb": bb["middle"][latest_idx],
            "boll_lb": bb["lower"][latest_idx],
            "funding_rate": fr_signal["current_rate"],
            "funding_sentiment": fr_signal["sentiment"],
            "oi_change_pct": oi_data["change_pct_24h"],
            "volume_ratio": vol_data["ratio"],
        }
        return factors

    def compute_factor_series(self, klines: list[KlineModel]) -> list[dict[str, Any]]:
        """Compute factors for EVERY bar in the series (for backtesting)."""
        if not klines:
            return []
        closes = self._extract_close(klines)
        highs = self._extract_high(klines)
        lows = self._extract_low(klines)
        volumes = self._extract_volume(klines)

        sma_20 = tech.sma(closes, 20)
        sma_50 = tech.sma(closes, 50)
        sma_200 = tech.sma(closes, 200)
        rsi_result = tech.rsi(closes)
        macd_result = tech.macd(closes)
        atr_result = tech.atr(highs, lows, closes)
        bb = tech.bollinger_bands(closes)
        vol_data = ms.volume_delta(volumes)

        series = []
        for i in range(len(klines)):
            series.append({
                "timestamp": klines[i].open_time,
                "close": closes[i],
                "sma_20": sma_20[i],
                "sma_50": sma_50[i],
                "sma_200": sma_200[i],
                "rsi_14": rsi_result[i],
                "macd_line": macd_result["macd_line"][i],
                "macd_signal": macd_result["signal_line"][i],
                "macd_histogram": macd_result["histogram"][i],
                "atr_14": atr_result[i],
                "boll_ub": bb["upper"][i],
                "boll_mb": bb["middle"][i],
                "boll_lb": bb["lower"][i],
                "volume_ratio": vol_data["ratio"],
            })
        return series

    async def compute_and_save(
        self,
        symbol: str,
        timeframe: str,
        klines: list[KlineModel],
        funding_rates: list[FundingRateModel] | None = None,
        oi_series: list[float] | None = None,
    ) -> FactorSnapshotModel:
        """Compute factors and save to database."""
        factors = self.compute_factors(symbol, timeframe, klines, funding_rates, oi_series)
        timestamp = klines[-1].open_time if klines else int(time.time() * 1000)

        snapshot = FactorSnapshotModel(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=timestamp,
            factors=factors,
        )
        if self.session:
            from sqlalchemy.dialects.postgresql import insert as pg_insert
            stmt = pg_insert(FactorSnapshotModel).values(
                symbol=symbol, timeframe=timeframe,
                timestamp=timestamp, factors=factors,
            )
            stmt = stmt.on_conflict_do_update(
                constraint="uq_factor_snapshot",
                set_={"factors": stmt.excluded.factors},
            )
            await self.session.execute(stmt)
            await self.session.commit()
        return snapshot

    async def get_latest_factors(
        self, symbol: str, timeframe: str
    ) -> Optional[FactorSnapshotModel]:
        if not self.session:
            return None
        query = (
            select(FactorSnapshotModel)
            .where(
                FactorSnapshotModel.symbol == symbol,
                FactorSnapshotModel.timeframe == timeframe,
            )
            .order_by(desc(FactorSnapshotModel.timestamp))
            .limit(1)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
