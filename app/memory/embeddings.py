"""Text embedding service using OpenAI API."""
from __future__ import annotations
import asyncio
import logging
from typing import Optional

from openai import AsyncOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Generates text embeddings for semantic memory search."""

    def __init__(self) -> None:
        self.client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
        ) if settings.OPENAI_API_KEY else None

    async def embed(self, text: str, model: str = "text-embedding-3-small") -> list[float]:
        """Generate embedding vector for text."""
        if not self.client:
            logger.warning("OpenAI API key not set, returning empty embedding")
            return [0.0] * 1536
        try:
            response = await self.client.embeddings.create(input=text, model=model)
            return response.data[0].embedding
        except Exception:
            logger.debug("Embedding unavailable (unsupported by provider), returning empty vector")
            return [0.0] * 1536

    async def embed_batch(self, texts: list[str], model: str = "text-embedding-3-small") -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        if not self.client:
            return [[0.0] * 1536 for _ in texts]
        try:
            response = await self.client.embeddings.create(input=texts, model=model)
            result = [e.embedding for e in response.data]
            return result
        except Exception:
            logger.debug("Batch embedding unavailable (unsupported by provider)")
            return [[0.0] * 1536 for _ in texts]
