"""Script de carga: corpus -> parser -> embeddings -> PostgreSQL + pgvector.

Uso:

    python -m shared.faq_store.load_data

Es idempotente: ejecutarlo varias veces mantiene 120 registros.
"""

from __future__ import annotations

import sys

from .config import ConfigurationError, load_settings
from .corpus import CorpusError, parse_corpus
from .database import DatabaseError, connect, upsert_records, verify_load
from .embeddings import Embedder

EXPECTED_RECORDS = 120
EXPECTED_CATEGORIES = 6


def main() -> int:
    try:
        settings = load_settings()
    except ConfigurationError as error:
        print(f"Error de configuración: {error}")
        return 1

    print("Reading corpus...")
    try:
        records = parse_corpus(settings.faq_file)
    except CorpusError as error:
        print(f"Error al leer el corpus: {error}")
        return 1
    print(f"Parsed {len(records)} records.")

    if len(records) != EXPECTED_RECORDS:
        print(
            f"Se esperaban {EXPECTED_RECORDS} registros y se encontraron "
            f"{len(records)}. Se detiene la carga."
        )
        return 1

    print("Generating embeddings...")
    try:
        embedder = Embedder(settings.embedding_model, settings.embedding_dimension)
        embeddings = embedder.encode(records)
    except Exception as error:  # sentence-transformers lanza errores variados
        print(f"Error al generar embeddings: {error}")
        return 1
    print(f"Embeddings generated: {len(embeddings)}")

    print("Connecting to PostgreSQL...")
    try:
        conn = connect(settings.database_url)
    except DatabaseError as error:
        print(f"Error de base de datos: {error}")
        return 1

    try:
        print("Loading data...")
        upsert_records(conn, records, embeddings)
        print(f"Loaded {len(records)} records.")
        result = verify_load(
            conn,
            EXPECTED_RECORDS,
            EXPECTED_CATEGORIES,
            settings.embedding_dimension,
        )
    except DatabaseError as error:
        print(f"Error de base de datos: {error}")
        return 1
    finally:
        conn.close()

    print(f"Rows: {result.total}")
    print(f"Categories: {result.categories}")
    print(f"Embedding dimensions: {result.dimension}")

    if not result.ok:
        for problem in result.problems:
            print(f"Verificación fallida: {problem}")
        return 1

    print("Verificación correcta: 120 filas, 6 categorías, embeddings de 384, IDs únicos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
