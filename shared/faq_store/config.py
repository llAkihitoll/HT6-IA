import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class Settings:
    database_url: str
    faq_file: Path
    embedding_model: str
    embedding_dimension: int
    llm_api_key: str
    llm_base_url: str
    llm_model: str
    search_min_similarity: float


def load_settings(
    project_root: Path = PROJECT_ROOT,
    env: Mapping[str, str] | None = None,
    require_llm_key: bool = False,
) -> Settings:
    if env is None:
        load_dotenv(project_root / ".env")
        values = os.environ
    else:
        values = env

    database_url = values.get(
        "DATABASE_URL",
        "postgresql://parachute:parachute_local@localhost:5433/parachute_faqs",
    ).strip()
    faq_value = values.get(
        "FAQ_FILE", "data/Corpus_FAQs_Parachute_SA_2026.txt"
    ).strip()
    embedding_model = values.get(
        "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
    ).strip()
    dimension_value = values.get("EMBEDDING_DIMENSION", "384").strip()
    llm_api_key = values.get("LLM_API_KEY", "").strip()
    llm_base_url = values.get(
        "LLM_BASE_URL", "https://api.groq.com/openai/v1"
    ).strip()
    llm_model = values.get("LLM_MODEL", "openai/gpt-oss-20b").strip()
    similarity_value = values.get("SEARCH_MIN_SIMILARITY", "0.35").strip()

    if not database_url:
        raise ConfigurationError("DATABASE_URL no puede estar vacío.")
    if not faq_value:
        raise ConfigurationError("FAQ_FILE no puede estar vacío.")
    if not embedding_model:
        raise ConfigurationError("EMBEDDING_MODEL no puede estar vacío.")
    if not llm_base_url:
        raise ConfigurationError("LLM_BASE_URL no puede estar vacío.")
    if not llm_model:
        raise ConfigurationError("LLM_MODEL no puede estar vacío.")
    if require_llm_key and not llm_api_key:
        raise ConfigurationError("LLM_API_KEY es obligatoria para ejecutar el agente.")

    try:
        embedding_dimension = int(dimension_value)
    except ValueError as error:
        raise ConfigurationError(
            "EMBEDDING_DIMENSION debe ser un número entero."
        ) from error

    if embedding_dimension <= 0:
        raise ConfigurationError("EMBEDDING_DIMENSION debe ser mayor que cero.")
    if embedding_dimension != 384:
        raise ConfigurationError(
            "EMBEDDING_DIMENSION debe coincidir con VECTOR(384) del esquema."
        )

    try:
        search_min_similarity = float(similarity_value)
    except ValueError as error:
        raise ConfigurationError(
            "SEARCH_MIN_SIMILARITY debe ser un número entre -1 y 1."
        ) from error
    if not -1.0 <= search_min_similarity <= 1.0:
        raise ConfigurationError(
            "SEARCH_MIN_SIMILARITY debe ser un número entre -1 y 1."
        )

    faq_file = Path(faq_value).expanduser()
    if not faq_file.is_absolute():
        faq_file = project_root / faq_file

    return Settings(
        database_url=database_url,
        faq_file=faq_file.resolve(),
        embedding_model=embedding_model,
        embedding_dimension=embedding_dimension,
        llm_api_key=llm_api_key,
        llm_base_url=llm_base_url,
        llm_model=llm_model,
        search_min_similarity=search_min_similarity,
    )
