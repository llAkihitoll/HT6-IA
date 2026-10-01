"""API común de FAQs: misma búsqueda semántica que en el Lab 4."""

from functools import lru_cache

from shared.faq_store.config import load_settings
from shared.faq_store.database import connect
from shared.faq_store.embeddings import Embedder
from shared.faq_store.search import FAQSearch


@lru_cache(maxsize=2)
def _embedder(model: str, dimension: int) -> Embedder:
    return Embedder(model, dimension)


def search_faqs(query: str, limit: int = 5) -> list[dict]:
    settings = load_settings()
    embedder = _embedder(settings.embedding_model, settings.embedding_dimension)
    with connect(settings.database_url) as conn:
        return FAQSearch(conn, embedder, settings.search_min_similarity).search_faqs(query, limit)
