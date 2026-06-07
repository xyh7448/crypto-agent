"""AI Analyst agent - generates market analysis reports using OpenAI."""
from __future__ import annotations
import json
import logging
from datetime import datetime
from typing import Any, Optional

from openai import AsyncOpenAI

from app.core.config import settings
from app.analyst import prompts

logger = logging.getLogger(__name__)


class AnalystAgent:
    """AI analyst that generates market analysis reports."""

    def __init__(self) -> None:
        self.client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
        ) if settings.OPENAI_API_KEY else None
        self.model = settings.MODEL_NAME

    async def generate_daily_report(
        self,
        symbol: str,
        factors: dict[str, Any],
        signals: list[dict[str, Any]],
        structure: dict[str, Any],
        positions: dict[str, Any],
    ) -> str:
        """Generate daily analysis report for a symbol."""
        if not self.client:
            return self._generate_fallback_report(symbol, factors, signals, structure)

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": prompts.DAILY_ANALYSIS_SYSTEM},
                    {"role": "user", "content": prompts.DAILY_ANALYSIS_USER.format(
                        symbol=symbol,
                        factors_json=json.dumps(factors, indent=2, default=str),
                        signals_json=json.dumps(signals[-5:] if signals else [], indent=2, default=str),
                        structure_json=json.dumps(structure, indent=2, default=str),
                        positions_json=json.dumps(positions, indent=2, default=str),
                    )},
                ],
                temperature=0.3,
                max_tokens=2000,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error("OpenAI analysis error for %s: %s", symbol, e)
            return self._generate_fallback_report(symbol, factors, signals, structure)

    def _generate_fallback_report(
        self,
        symbol: str,
        factors: dict[str, Any],
        signals: list[dict[str, Any]],
        structure: dict[str, Any],
    ) -> str:
        """Generate a basic report without AI (fallback)."""
        close = factors.get("close", 0)
        rsi = factors.get("rsi_14", 50)
        ema_fast = factors.get("ema_12", 0)
        ema_slow = factors.get("ema_26", 0)
        macd = factors.get("macd_histogram", 0)
        vol_ratio = factors.get("volume_ratio", 1.0)

        if ema_fast > ema_slow:
            trend = "BULLISH"
        else:
            trend = "BEARISH"

        if rsi >= 70:
            rsi_signal = "Overbought"
        elif rsi <= 30:
            rsi_signal = "Oversold"
        else:
            rsi_signal = "Neutral"

        risk = "HIGH" if (abs(rsi - 50) > 30 or vol_ratio > 2.0) else "MEDIUM" if (abs(rsi - 50) > 20) else "LOW"

        report = f"""📊 **{symbol} 每日分析**

## 市场概览
- **价格**: ${close:.2f}
- **趋势**: {trend}（EMA12={ema_fast:.2f}, EMA26={ema_slow:.2f}）
- **RSI(14)**: {rsi:.1f} - {rsi_signal}
- **MACD柱**: {macd:.4f}
- **成交量比**: {vol_ratio:.2f}

## 风险评估
- **风险等级**: {risk}
- **资金费率**: {structure.get('funding_rate', 0):.6f}（{structure.get('funding_sentiment', '中性')}）
- **24h OI变化**: {structure.get('oi_change_pct', 0):.2f}%

## 建议
- 技术指标偏{trend}，建议{'谨慎看多' if rsi > 70 else '谨慎看空' if rsi < 30 else '中性观望'}
- 成交量{'偏高' if vol_ratio > 1.5 else '正常'}，{'确认趋势' if vol_ratio > 1.5 else '趋势有待确认'}

*自动分析，仅供参考*
"""
        return report

    async def generate_multi_symbol_report(
        self,
        symbols_data: list[dict[str, Any]],
    ) -> str:
        """Generate combined report for multiple symbols."""
        reports = []
        for data in symbols_data:
            report = await self.generate_daily_report(
                symbol=data["symbol"],
                factors=data.get("factors", {}),
                signals=data.get("signals", []),
                structure=data.get("structure", {}),
                positions=data.get("positions", {}),
            )
            reports.append(report)

        return "\n\n---\n\n".join(reports)
