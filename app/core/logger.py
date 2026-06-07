"""
Structured logging via structlog.

Provides a pre-configured ``structlog.stdlib.BoundLogger`` with JSON output
for production and human-readable console output for development.

Usage::

    from app.core.logger import get_logger

    logger = get_logger(__name__)
    logger.info("trade_executed", symbol="BTCUSDT", side="BUY", qty=0.1)
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

import structlog

from app.core.config import settings

# ── Environment detection ──────────────────────────────────────────────────

_is_dev = os.environ.get("CRYPTO_AGENT_ENV", "development") == "development"
_is_test = os.environ.get("CRYPTO_AGENT_ENV") == "test"


# ── Processor chains ───────────────────────────────────────────────────────

_shared_processors: list[structlog.types.Processor] = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_log_level,
    structlog.stdlib.add_logger_name,
    structlog.stdlib.PositionalArgumentsFormatter(),
    structlog.processors.TimeStamper(fmt="iso", utc=True),
    structlog.processors.StackInfoRenderer(),
    structlog.processors.CallsiteParameterAdder(
        parameters=[
            structlog.processors.CallsiteParameter.FILENAME,
            structlog.processors.CallsiteParameter.FUNC_NAME,
            structlog.processors.CallsiteParameter.LINENO,
        ],
    ),
    structlog.stdlib.ExtraAdder(),
]

if _is_test:
    # During tests, keep processors minimal for speed.
    _chain: list[structlog.types.Processor] = _shared_processors + [
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ]
elif _is_dev:
    # Development: colourful console output.
    _chain = _shared_processors + [
        structlog.dev.ConsoleRenderer(
            colors=True,
            sort_keys=False,
        ),
    ]
else:
    # Production: JSON structured output.
    _chain = _shared_processors + [
        structlog.processors.dict_tracebacks,
        structlog.processors.JSONRenderer(
            serializer=lambda obj, **kw: __import__("orjson").dumps(
                obj, default=str
            ).decode(),
        ),
    ]


# ── Configure structlog ────────────────────────────────────────────────────

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        *_shared_processors,
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)


# ── Standard library integration ───────────────────────────────────────────

_formatter = structlog.stdlib.ProcessorFormatter(
    processor=_chain[-1],
)

_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(_formatter)

_root = logging.getLogger()
_root.addHandler(_handler)
_root.setLevel(
    logging.DEBUG if _is_dev else logging.INFO
)

# Silence noisy third-party loggers.
for name in (
    "asyncio",
    "httpx",
    "httpcore",
    "urllib3",
    "aiosqlite",
    "sqlalchemy.engine",
):
    logging.getLogger(name).setLevel(logging.WARNING)


# ── Public API ─────────────────────────────────────────────────────────────

def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger bound to *name*.

    Parameters
    ----------
    name:
        The logger name, typically ``__name__``. Falls back to ``"app"`` if
        ``None``.
    """
    return structlog.get_logger(name or "app")
