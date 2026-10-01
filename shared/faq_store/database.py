"""Persistencia de las FAQs y sus embeddings en PostgreSQL + pgvector.

La tabla `faq_embeddings` la crea `db/init.sql` cuando se levanta el contenedor.
Aquí solo se comprueba que exista y se insertan/actualizan los registros.

La carga es idempotente: `faq_id` es UNIQUE y se usa `ON CONFLICT` para
actualizar en vez de duplicar. El `content_hash` evita reescribir filas que no
cambiaron.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

import psycopg
from psycopg.types.json import Jsonb

from .corpus import FaqRecord


class DatabaseError(Exception):
    """Problema de conexión o de esquema en PostgreSQL."""


UPSERT_SQL = """
INSERT INTO faq_embeddings
    (faq_id, category, question, answer, metadata, content_hash, embedding, updated_at)
VALUES
    (%(faq_id)s, %(category)s, %(question)s, %(answer)s, %(metadata)s,
     %(content_hash)s, %(embedding)s::vector, CURRENT_TIMESTAMP)
ON CONFLICT (faq_id) DO UPDATE SET
    category = EXCLUDED.category,
    question = EXCLUDED.question,
    answer = EXCLUDED.answer,
    metadata = EXCLUDED.metadata,
    content_hash = EXCLUDED.content_hash,
    embedding = EXCLUDED.embedding,
    updated_at = CURRENT_TIMESTAMP
WHERE faq_embeddings.content_hash IS DISTINCT FROM EXCLUDED.content_hash
"""


def connect(database_url: str) -> psycopg.Connection:
    try:
        conn = psycopg.connect(database_url)
    except psycopg.OperationalError as error:
        raise DatabaseError(
            "No se pudo conectar a PostgreSQL. ¿Está levantado el contenedor "
            f"('docker compose up -d')? Detalle: {error}"
        ) from error

    _check_schema(conn)
    return conn


def _check_schema(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
        if cur.fetchone() is None:
            raise DatabaseError(
                "La extensión pgvector no está disponible. Recrea la base con "
                "'docker compose down --volumes && docker compose up -d'."
            )
        cur.execute("SELECT to_regclass('public.faq_embeddings')")
        if cur.fetchone()[0] is None:
            raise DatabaseError(
                "La tabla 'faq_embeddings' no existe. Ejecuta 'docker compose up -d' "
                "para que se aplique db/init.sql."
            )


def content_hash(record: FaqRecord) -> str:
    payload = json.dumps(
        {
            "faq_id": record.faq_id,
            "category": record.category,
            "question": record.question,
            "answer": record.answer,
            "metadata": record.metadata,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _vector_literal(embedding: list[float]) -> str:
    return "[" + ",".join(repr(float(value)) for value in embedding) + "]"


def upsert_records(
    conn: psycopg.Connection,
    records: list[FaqRecord],
    embeddings: list[list[float]],
) -> None:
    rows = [
        {
            "faq_id": record.faq_id,
            "category": record.category,
            "question": record.question,
            "answer": record.answer,
            "metadata": Jsonb(record.metadata),
            "content_hash": content_hash(record),
            "embedding": _vector_literal(embedding),
        }
        for record, embedding in zip(records, embeddings)
    ]
    with conn.cursor() as cur:
        cur.executemany(UPSERT_SQL, rows)
    conn.commit()


@dataclass
class VerificationResult:
    total: int
    categories: int
    dimension: int | None
    duplicates: int
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


def verify_load(
    conn: psycopg.Connection,
    expected_total: int = 120,
    expected_categories: int = 6,
    expected_dimension: int = 384,
) -> VerificationResult:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM faq_embeddings")
        total = cur.fetchone()[0]

        cur.execute("SELECT COUNT(DISTINCT category) FROM faq_embeddings")
        categories = cur.fetchone()[0]

        cur.execute(
            "SELECT MIN(vector_dims(embedding)), MAX(vector_dims(embedding)) "
            "FROM faq_embeddings"
        )
        min_dim, max_dim = cur.fetchone()

        cur.execute(
            "SELECT COUNT(*) FROM ("
            "  SELECT faq_id FROM faq_embeddings"
            "  GROUP BY faq_id HAVING COUNT(*) > 1"
            ") AS d"
        )
        duplicates = cur.fetchone()[0]

    problems = []
    if total != expected_total:
        problems.append(f"Se esperaban {expected_total} filas y hay {total}.")
    if categories != expected_categories:
        problems.append(
            f"Se esperaban {expected_categories} categorías y hay {categories}."
        )
    if min_dim != expected_dimension or max_dim != expected_dimension:
        problems.append(
            f"Los embeddings deben tener {expected_dimension} dimensiones "
            f"(rango encontrado: {min_dim}-{max_dim})."
        )
    if duplicates:
        problems.append(f"Hay {duplicates} faq_id duplicados.")

    return VerificationResult(
        total=total,
        categories=categories,
        dimension=min_dim if min_dim == max_dim else None,
        duplicates=duplicates,
        problems=problems,
    )
