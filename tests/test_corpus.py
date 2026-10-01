import re
from pathlib import Path

import pytest

from shared.faq_store.corpus import CorpusError, FaqRecord, parse_corpus

CORPUS_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "Corpus_FAQs_Parachute_SA_2026.txt"
)

EXPECTED_CATEGORIES = {
    "Logística y Ubicación",
    "Requisitos Físicos y Salud",
    "Seguridad y Normativa Aeronáutica",
    "Precios, Paquetes y Métodos de Pago",
    "Fotografía y Contenido Multimedia",
    "Clima y Contingencias",
}


@pytest.fixture(scope="module")
def records() -> list[FaqRecord]:
    return parse_corpus(CORPUS_PATH)


def test_parses_120_records(records):
    assert len(records) == 120


def test_every_record_has_the_required_fields(records):
    for record in records:
        assert record.faq_id
        assert record.category
        assert record.question
        assert record.answer
        assert isinstance(record.metadata, dict)


def test_ids_are_well_formed_and_unique(records):
    ids = [record.faq_id for record in records]
    assert len(set(ids)) == 120
    assert all(re.fullmatch(r"FAQ-\d{3}", faq_id) for faq_id in ids)


def test_six_expected_categories(records):
    assert {record.category for record in records} == EXPECTED_CATEGORIES


def test_first_record_content(records):
    first = records[0]
    assert first.faq_id == "FAQ-001"
    assert first.category == "Logística y Ubicación"
    assert first.question == "¿Dónde se ubica la zona de salto?"
    assert "zona de salto" in first.answer
    assert first.metadata["empresa"] == "Parachute S.A."
    assert first.metadata["fecha"] == "2026-09-29"


def test_metadata_is_parsed_as_dict(records):
    keys = {"empresa", "evento", "fecha", "unidad_medida"}
    assert keys.issubset(records[0].metadata.keys())
    assert all(isinstance(record.metadata, dict) for record in records)


def test_a_record_from_another_category(records):
    by_id = {record.faq_id: record for record in records}
    assert by_id["FAQ-120"].category == "Clima y Contingencias"
    assert by_id["FAQ-120"].question.endswith("?")


def test_missing_file_raises_corpus_error(tmp_path):
    with pytest.raises(CorpusError):
        parse_corpus(tmp_path / "no_existe.txt")


def test_invalid_metadata_raises_corpus_error(tmp_path):
    bad = tmp_path / "bad.txt"
    bad.write_text(
        "ID: FAQ-001\n"
        "CATEGORÍA: Logística y Ubicación\n"
        "PREGUNTA: ¿Hola?\n"
        "RESPUESTA: Sí.\n"
        "METADATA: {no es json}\n",
        encoding="utf-8",
    )
    with pytest.raises(CorpusError):
        parse_corpus(bad)
