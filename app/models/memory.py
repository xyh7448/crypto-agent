"""Agent memory ORM model — text + embedding for vector similarity search."""

from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Float, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MemoryEntryModel(Base):
    """A single memory entry for an agent.

    ``embedding`` is a 1536-dimensional pgvector vector used for cosine
    similarity search.  ``metadata`` holds arbitrary key-value pairs
    (e.g. source, tags, importance).  ``similarity_score`` is populated
    at query time by the retrieval layer and is ``None`` when persisted.
    """

    __tablename__ = "memory_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(1536), nullable=True
    )
    extra_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    similarity_score: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=datetime.utcnow
    )

    __table_args__ = (
        Index(
            "ix_memory_embedding",
            embedding,  # type: ignore[arg-type]
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 200},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    def __repr__(self) -> str:
        return f"<MemoryEntryModel id={self.id} agent={self.agent_id}>"
