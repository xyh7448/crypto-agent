"""
Application configuration via pydantic-settings.

Loads from .env file and environment variables. All settings are typed,
validated, and available as a globally importable singleton.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import ClassVar

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_dotenv() -> str:
    """Walk up from cwd / home looking for a .env file."""
    candidates = [
        Path.cwd() / ".env",
        Path.home() / ".env",
        Path.home() / ".crypto-agent" / ".env",
        Path(__file__).resolve().parent.parent.parent / ".env",
    ]
    for p in candidates:
        if p.is_file():
            return str(p.resolve())
    return ""


class Settings(BaseSettings):
    """Central settings for the crypto-agent service."""

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_file=_find_dotenv() or ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        frozen=True,
    )

    # ── Binance ──────────────────────────────────────────────────────────
    BINANCE_API_KEY: str = Field(default="", description="Binance API key")
    BINANCE_API_SECRET: str = Field(default="", description="Binance API secret")

    # ── OpenAI / LLM ─────────────────────────────────────────────────────
    OPENAI_API_KEY: str = Field(default="", description="OpenAI API key")
    OPENAI_BASE_URL: str = Field(
        default="https://api.openai.com/v1",
        description="OpenAI base URL (use https://api.deepseek.com for DeepSeek)",
    )
    MODEL_NAME: str = Field(default="gpt-4o-mini", description="LLM model for analysis")

    # ── PostgreSQL ───────────────────────────────────────────────────────
    POSTGRES_URI: str = Field(
        default="postgresql+asyncpg://crypto:crypto@localhost:5432/crypto_agent",
        description="Async PostgreSQL connection URI",
    )

    # ── Redis ────────────────────────────────────────────────────────────
    REDIS_URI: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URI",
    )

    # ── Risk Parameters ─────────────────────────────────────────────────
    RISK_MAX_POSITION: float = Field(default=1.0, ge=0.0, le=1.0, description="Max position ratio of account balance")
    RISK_MAX_DRAWDOWN: float = Field(default=0.15, ge=0.0, le=1.0, description="Max drawdown ratio")
    RISK_MAX_DAILY_LOSS: float = Field(default=0.05, ge=0.0, le=1.0, description="Max daily loss ratio")

    # ── Strategy ─────────────────────────────────────────────────────────
    STRATEGY_CONFIG: str = Field(default="{}", description="JSON strategy configuration")

    # ── Feishu Notification ──────────────────────────────────────────────
    FEISHU_WEBHOOK_URL: str = Field(
        default="",
        description="Feishu custom bot webhook URL",
    )
    FEISHU_SIGNING_SECRET: str = Field(
        default="",
        description="Feishu webhook signing secret (optional)",
    )

    # ── Strategy ─────────────────────────────────────────────────────────
    STRATEGY_CONFIG: dict[str, object] = Field(
        default_factory=lambda: {
            "trend": {
                "fast_period": 12,
                "slow_period": 26,
                "signal_period": 9,
            },
            "breakout": {
                "lookback": 20,
                "deviation": 2.0,
            },
            "mean_reversion": {
                "rsi_period": 14,
                "rsi_overbought": 70,
                "rsi_oversold": 30,
            },
        },
        description="Strategy parameter configuration",
    )

    @field_validator("STRATEGY_CONFIG", mode="before")
    @classmethod
    def _parse_strategy_config(
        cls, v: str | dict[str, object]
    ) -> dict[str, object]:
        """Accept a JSON string from env var and parse it to a dict."""
        if isinstance(v, dict):
            return v
        try:
            parsed = json.loads(v)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"STRATEGY_CONFIG must be a valid JSON object: {exc}"
            ) from exc
        if not isinstance(parsed, dict):
            raise ValueError(
                f"STRATEGY_CONFIG must be a JSON object, got {type(parsed).__name__}"
            )
        return parsed

    # ── MCP server ───────────────────────────────────────────────────────
    MCP_SERVER_HOST: str = Field(
        default="0.0.0.0",
        description="Host to bind the MCP server to",
    )
    MCP_SERVER_PORT: int = Field(
        default=8001,
        ge=1,
        le=65535,
        description="Port to bind the MCP server to",
    )


# Module-level singleton — importers get `from app.core.config import settings`.
settings = Settings()
