from __future__ import annotations

from contextlib import nullcontext

import pytest

from shared.faq_store.search import FAQSearch


class FakeEmbedder:
    def __init__(self) -> None:
        self.queries = []

    def encode_query(self, query: str) -> list[float]:
        self.queries.append(query)
        return [0.1, 0.2, 0.3]


class FakeCursor:
    def __init__(self, rows) -> None:
        self.rows = rows
        self.sql = None
        self.params = None

    def execute(self, sql, params) -> None:
        self.sql = sql
        self.params = params

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, rows) -> None:
        self.cur = FakeCursor(rows)

    def cursor(self):
        return nullcontext(self.cur)


@pytest.mark.parametrize(
    "query",
    [
        "¿Cuál es el horario de atención?",  # pregunta conocida
        "¿A qué horas puedo comunicarme con ustedes?",  # paráfrasis
    ],
)
def test_search_faqs_handles_known_questions_and_paraphrases(query) -> None:
    rows = [
        ("FAQ-001", "General", "Horario", "De lunes a viernes", {}, 0.91)
    ]
    conn = FakeConnection(rows)
    embedder = FakeEmbedder()

    results = FAQSearch(conn, embedder, min_similarity=0.4).search_faqs(query, 3)

    assert results[0]["faq_id"] == "FAQ-001"
    assert results[0]["answer"] == "De lunes a viernes"
    assert results[0]["similarity"] == pytest.approx(0.91)
    assert embedder.queries == [query]
    assert "<=>" in conn.cur.sql
    assert conn.cur.params["limit"] == 3
    assert conn.cur.params["min_similarity"] == 0.4


def test_search_faqs_returns_no_evidence_for_out_of_corpus_question() -> None:
    search = FAQSearch(FakeConnection([]), FakeEmbedder())
    assert search.search_faqs("¿Quién ganó el mundial?") == []


@pytest.mark.parametrize("limit", [0, 21, True, 2.5])
def test_search_faqs_rejects_invalid_limits(limit) -> None:
    search = FAQSearch(FakeConnection([]), FakeEmbedder())
    with pytest.raises(ValueError, match="limit"):
        search.search_faqs("consulta", limit)
