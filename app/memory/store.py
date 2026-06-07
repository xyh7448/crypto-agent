"""Long-term memory store using PostgreSQL + pgvector for semantic search."""
from __future__ import annotations
import json
import logging
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select, desc, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import text

from app.models.memory import MemoryEntryModel
from app.memory.embeddings import EmbeddingService

logger = logging.getLogger(__name__)


class MemoryStore:
    """Semantic memory store with pgvector similarity search."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.embeddings = EmbeddingService()

    async def save(
        self,
        agent_id: str,
        content: str,
        metadata: dict[str, Any] | None = None,
        embed: bool = True,
    ) -> MemoryEntryModel:
        """Save a memory entry with optional embedding."""
        embedding = None
        if embed:
            embedding = await self.embeddings.embed(content)

        entry = MemoryEntryModel(
            agent_id=agent_id,
            content=content,
            embedding=embedding,
            metadata=metadata or {},
        )
        self.session.add(entry)
        await self.session.commit()
        await self.session.refresh(entry)
        return entry

    async def save_batch(
        self, entries: list[dict[str, Any]], embed: bool = True,
    ) -> list[MemoryEntryModel]:
        """Save multiple memory entries."""
        texts = [e["content"] for e in entries]
        embeddings = await self.embeddings.embed_batch(texts) if embed else [[0.0] * 1536 for _ in entries]

        models = []
        for i, entry_data in enumerate(entries):
            model = MemoryEntryModel(
                agent_id=entry_data["agent_id"],
                content=entry_data["content"],
                embedding=embeddings[i],
                metadata=entry_data.get("metadata", {}),
            )
            self.session.add(model)
            models.append(model)

        await self.session.commit()
        return models

    async def search(
        self,
        query: str,
        agent_id: str | None = None,
        top_k: int = 10,
        min_score: float = 0.7,
    ) -> list[dict[str, Any]]:
        """Semantic search for relevant memories."""
        query_embedding = await self.embeddings.embed(query)

        # pgvector cosine distance
        agent_filter = "AND agent_id = :agent_id" if agent_id else ""
        sql = text(f"""
            SELECT id, agent_id, content, metadata, created_at,
                   1 - (embedding <=> :query_embedding::vector) AS similarity
            FROM memory_entries
            WHERE embedding IS NOT NULL {agent_filter}
              AND 1 - (embedding <=> :query_embedding::vector) >= :min_score
            ORDER BY similarity DESC
            LIMIT :top_k
        """)
        params = {
            "query_embedding": str(query_embedding),
            "min_score": min_score,
            "top_k": top_k,
        }
        if agent_id:
            params["agent_id"] = agent_id

        result = await self.session.execute(sql, params)
        rows = result.fetchall()

        return [
            {
                "id": r[0],
                "agent_id": r[1],
                "content": r[2],
                "metadata": r[3] if isinstance(r[3], dict) else json.loads(r[3]) if r[3] else {},
                "created_at": r[4].isoformat() if r[4] else "",
                "similarity": round(float(r[5]), 4),
            }
            for r in rows
        ]

    async def search_by_metadata(
        self, agent_id: str, metadata_filter: dict[str, Any], limit: int = 20,
    ) -> list[MemoryEntryModel]:
        """Search memories by metadata fields."""
        query = select(MemoryEntryModel).where(
            MemoryEntryModel.agent_id == agent_id,
        )
        for key, value in metadata_filter.items():
            query = query.where(
                MemoryEntryModel.extra_data[key].as_string() == json.dumps(value)
                if isinstance(value, (dict, list)) else
                MemoryEntryModel.extra_data[key].as_string() == str(value)
            )
        query = query.order_by(desc(MemoryEntryModel.created_at)).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_recent(self, agent_id: str, limit: int = 20) -> list[MemoryEntryModel]:
        query = (
            select(MemoryEntryModel)
            .where(MemoryEntryModel.agent_id == agent_id)
            .order_by(desc(MemoryEntryModel.created_at))
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def delete_old(self, agent_id: str, before: datetime) -> int:
        query = delete(MemoryEntryModel).where(
            MemoryEntryModel.agent_id == agent_id,
            MemoryEntryModel.created_at < before,
        )
        result = await self.session.execute(query)
        await self.session.commit()
        return result.rowcount

    async def count(self, agent_id: str | None = None) -> int:
        query = select(MemoryEntryModel)
        if agent_id:
            query = query.where(MemoryEntryModel.agent_id == agent_id)
        result = await self.session.execute(query)
        return len(result.scalars().all())
