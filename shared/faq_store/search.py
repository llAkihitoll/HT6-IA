"""Búsqueda semántica de preguntas frecuentes mediante pgvector."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Protocol

import psycopg

from .config import Settings, load_settings
from .database import connect
from .embeddings import Embedder


class QueryEmbedder(Protocol):
    def encode_query(self, query: str) -> list[float]: ...


@dataclass(frozen=True)
class SearchResult:
    faq_id: str
    category: str
    question: str
    answer: str
    metadata: dict
    similarity: float

    def to_dict(self) -> dict:
        return asdict(self)


SEARCH_SQL = """
SELECT faq_id, category, question, answer, metadata,
       1 - (embedding <=> %(embedding)s::vector) AS similarity
FROM faq_embeddings
WHERE 1 - (embedding <=> %(embedding)s::vector) >= %(min_similarity)s
ORDER BY embedding <=> %(embedding)s::vector
LIMIT %(limit)s
"""


class FAQSearch:
    """Mantiene los recursos de búsqueda abiertos para varias consultas."""

    def __init__(
        self,
        conn: psycopg.Connection,
        embedder: QueryEmbedder,
        min_similarity: float = 0.35,
    ) -> None:
        self.conn = conn
        self.embedder = embedder
        self.min_similarity = min_similarity

    def search_faqs(self, query: str, limit: int = 5) -> list[dict]:
        query = query.strip()
        if not query:
            raise ValueError("La consulta no puede estar vacía.")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 20:
            raise ValueError("limit debe ser un entero entre 1 y 20.")

        vector = self.embedder.encode_query(query)
        literal = "[" + ",".join(repr(float(value)) for value in vector) + "]"
        with self.conn.cursor() as cur:
            cur.execute(
                SEARCH_SQL,
                {
                    "embedding": literal,
                    "min_similarity": self.min_similarity,
                    "limit": limit,
                },
            )
            rows = cur.fetchall()

        return [
            SearchResult(
                faq_id=row[0],
                category=row[1],
                question=row[2],
                answer=row[3],
                metadata=row[4],
                similarity=float(row[5]),
            ).to_dict()
            for row in rows
        ]


def build_search(settings: Settings | None = None) -> FAQSearch:
    settings = settings or load_settings()
    return FAQSearch(
        connect(settings.database_url),
        Embedder(settings.embedding_model, settings.embedding_dimension),
        settings.search_min_similarity,
    )


def search_faqs(query: str, limit: int = 5) -> list[dict]:
    """API sencilla solicitada por la tarea; cierra la conexión al terminar."""
    service = build_search()
    try:
        return service.search_faqs(query, limit)
    finally:
        service.conn.close()
