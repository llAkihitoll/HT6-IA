"""Lector del corpus de FAQs de Parachute S.A.

El archivo es texto plano. Cada registro tiene la forma:

    ID: FAQ-001
    CATEGORÍA: Logística y Ubicación
    PREGUNTA: ¿Dónde se ubica la zona de salto?
    RESPUESTA: ...
    METADATA: {"empresa": "Parachute S.A.", ...}

y los registros están separados por una línea de guiones.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

# Etiqueta del corpus -> nombre del campo en el registro.
FIELD_LABELS = {
    "ID": "faq_id",
    "CATEGORÍA": "category",
    "PREGUNTA": "question",
    "RESPUESTA": "answer",
    "METADATA": "metadata_raw",
}

REQUIRED_FIELDS = ("faq_id", "category", "question", "answer")


class CorpusError(Exception):
    """Problema al leer o interpretar el corpus."""


@dataclass(frozen=True)
class FaqRecord:
    faq_id: str
    category: str
    question: str
    answer: str
    metadata: dict


def parse_corpus(path: str | Path) -> list[FaqRecord]:
    path = Path(path)
    if not path.is_file():
        raise CorpusError(f"No se encontró el corpus en '{path}'.")

    text = path.read_text(encoding="utf-8")
    records = []
    for block in _split_blocks(text):
        record = _parse_block(block)
        if record is not None:
            records.append(record)

    if not records:
        raise CorpusError("El corpus no contiene registros.")
    _check_unique_ids(records)
    return records


def _split_blocks(text: str) -> list[list[str]]:
    """Divide el texto en bloques usando las líneas de guiones como separador."""
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and set(stripped) == {"-"}:
            if current:
                blocks.append(current)
                current = []
            continue
        current.append(line)
    if current:
        blocks.append(current)
    return blocks


def _parse_block(lines: list[str]) -> FaqRecord | None:
    fields: dict[str, str] = {}
    current_key: str | None = None

    for line in lines:
        label, sep, rest = line.partition(":")
        key = FIELD_LABELS.get(label.strip()) if sep else None
        if key is not None:
            fields[key] = rest.strip()
            current_key = key
        elif current_key is not None and line.strip():
            # Línea de continuación del campo anterior.
            fields[current_key] += " " + line.strip()

    # Un bloque sin ID es el encabezado del archivo, no un registro.
    if "faq_id" not in fields:
        return None

    missing = [name for name in REQUIRED_FIELDS if not fields.get(name)]
    if missing:
        raise CorpusError(
            f"El registro '{fields.get('faq_id', '?')}' no tiene los campos: "
            f"{', '.join(missing)}."
        )

    raw_metadata = fields.get("metadata_raw", "").strip()
    try:
        metadata = json.loads(raw_metadata) if raw_metadata else {}
    except json.JSONDecodeError as error:
        raise CorpusError(
            f"METADATA inválida en el registro '{fields['faq_id']}': {error}"
        ) from error
    if not isinstance(metadata, dict):
        raise CorpusError(
            f"METADATA del registro '{fields['faq_id']}' debe ser un objeto JSON."
        )

    return FaqRecord(
        faq_id=fields["faq_id"],
        category=fields["category"],
        question=fields["question"],
        answer=fields["answer"],
        metadata=metadata,
    )


def _check_unique_ids(records: list[FaqRecord]) -> None:
    seen = set()
    duplicates = set()
    for record in records:
        if record.faq_id in seen:
            duplicates.add(record.faq_id)
        seen.add(record.faq_id)
    if duplicates:
        raise CorpusError(
            f"El corpus tiene IDs duplicados: {', '.join(sorted(duplicates))}."
        )
