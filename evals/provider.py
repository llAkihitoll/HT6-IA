"""Provider de Promptfoo para la arquitectura jerárquica de HT5.

Ejecuta el Supervisor General real (`hierarchical.supervisor.supervisor`) con
el Runner del SDK de OpenAI Agents. No reimplementa ni modifica ningún agente:

- El modelo se inyecta con `RunConfig` (el SDK lo propaga a los sub-agentes
  expuestos con `as_tool`), apuntando a un endpoint compatible con OpenAI.
- Las tool calls se observan con el tracing nativo del SDK: un
  `TracingProcessor` recoge cada `FunctionSpan` (nombre, argumentos, salida,
  agente que la ejecutó y duración) de todos los niveles de la jerarquía.
- Cada caso escribe citas en una SQLite temporal propia; las filas reales se
  devuelven en `metadata` para compararlas con lo que afirma el agente.
- Escenarios climáticos (`vars.clima`): se reemplaza solo la frontera con
  Open-Meteo, igual que en `tests/test_bookings.py`, manteniendo la validación
  real de fechas. `clima: live` usa Open-Meteo real sin reemplazos.
"""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import sys
import tempfile
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from agents import RunConfig, Runner, gen_trace_id, set_trace_processors, trace  # noqa: E402
from agents.models.openai_provider import OpenAIProvider  # noqa: E402
from agents.tracing import TracingProcessor  # noqa: E402
from agents.tracing.span_data import AgentSpanData, FunctionSpanData  # noqa: E402

from hierarchical.supervisor import supervisor  # noqa: E402
from shared import bookings, faqs, open_meteo_client  # noqa: E402
from shared.faq_store.config import load_settings  # noqa: E402
from shared.weather_contracts import WeatherReading  # noqa: E402

# Lecturas de escenario. Son entradas controladas del eval (no pronósticos
# reales) y usan los mismos valores que las pruebas existentes del proyecto.
WEATHER_SCENARIOS = {
    "ideal": WeatherReading(10, 20, 0, 10, 24),
    "marginal": WeatherReading(20, 35, 0, 10, 24),
    "prohibido-lluvia": WeatherReading(10, 20, 0.1, 10, 24),
    "prohibido-rafagas": WeatherReading(10, 36, 0, 10, 24),
}


class ToolCallCollector(TracingProcessor):
    """Guarda las spans terminadas para reconstruir las tool calls de cada traza."""

    def __init__(self) -> None:
        self.spans: list = []

    def on_trace_start(self, trace) -> None:
        pass

    def on_trace_end(self, trace) -> None:
        pass

    def on_span_start(self, span) -> None:
        pass

    def on_span_end(self, span) -> None:
        self.spans.append(span)

    def shutdown(self) -> None:
        pass

    def force_flush(self) -> None:
        pass

    def tool_calls(self, trace_id: str) -> list[dict]:
        spans = [s for s in self.spans if s.trace_id == trace_id]
        by_id = {s.span_id: s for s in spans}

        def owner_agent(span):
            # FunctionSpan -> TurnSpan -> AgentSpan: se sube hasta el agente.
            parent = by_id.get(span.parent_id)
            while parent is not None and not isinstance(parent.span_data, AgentSpanData):
                parent = by_id.get(parent.parent_id)
            return parent.span_data.name if parent is not None else None

        calls = []
        for s in spans:
            if not isinstance(s.span_data, FunctionSpanData):
                continue
            calls.append({
                "name": s.span_data.name,
                "agent": owner_agent(s),
                "arguments": _maybe_json(s.span_data.input),
                "output": _maybe_json(s.span_data.output),
                "error": s.error["message"] if s.error else None,
                "started_at": s.started_at,
                "duration_ms": _duration_ms(s.started_at, s.ended_at),
            })
        return sorted(calls, key=lambda c: c["started_at"] or "")


COLLECTOR = ToolCallCollector()
# Reemplaza el exportador por defecto: las trazas no salen de la máquina.
set_trace_processors([COLLECTOR])

def _warm_up_embeddings() -> None:
    """Carga el modelo de embeddings (cacheado por `faqs._embedder`).

    Se llama en `call_api` antes de medir la latencia, para que la carga de
    torch/sentence-transformers (~30 s) no se cuente en el primer caso de FAQ.
    No se hace al importar porque Promptfoo exige que el worker Python esté
    listo en 30 s.
    """
    settings = load_settings(ROOT)
    faqs._embedder(settings.embedding_model, settings.embedding_dimension)


def _maybe_json(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return value
    return value


def _duration_ms(start: str | None, end: str | None) -> float | None:
    if not start or not end:
        return None
    return round((datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds() * 1000, 1)


def _fake_fetch(reading: WeatherReading):
    def fetch(fecha_iso, *, today=None, request_json=None):
        # La validación de fecha (formato, pasado, 16 días) sigue siendo real.
        open_meteo_client.validate_forecast_date(fecha_iso, today=today)
        return reading
    return fetch


def _read_bookings(db_path: Path) -> list[dict]:
    if not db_path.exists():
        return []
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT id, fecha, hora, cliente, estado FROM bookings ORDER BY created_at").fetchall()
    return [dict(row) for row in rows]


# Un solo event loop por worker: el SDK reutiliza un cliente HTTP global
# (`shared_http_client`) que queda ligado al loop donde se creó; con
# `asyncio.run` por llamada, la segunda llamada falla con "Event loop is closed".
_LOOP = asyncio.new_event_loop()


async def _run_agent(message: str, run_config: RunConfig, trace_id: str):
    with trace("HT6 eval - jerarquica", trace_id=trace_id):
        started = time.perf_counter()
        result = await Runner.run(supervisor, message, run_config=run_config)
        elapsed_ms = (time.perf_counter() - started) * 1000
    return result, elapsed_ms


def call_api(prompt, options, context):
    config = options.get("config", {})
    test_vars = context.get("vars", {})
    api_key = os.getenv(config.get("api_key_env", "NVIDIA_API_KEY"))
    if not api_key:
        return {"error": f"Falta la variable {config.get('api_key_env', 'NVIDIA_API_KEY')} en .env."}

    # Base de FAQs usada por el eval (puerto 5434 en HT6). El bloque `env:` de
    # Promptfoo no llega al worker de Python, por eso se pasa por config.
    if config.get("database_url"):
        os.environ["DATABASE_URL"] = config["database_url"]

    clima = test_vars.get("clima", "live")
    if clima != "live" and clima not in WEATHER_SCENARIOS:
        return {"error": f"Escenario climático desconocido: {clima}"}

    run_config = RunConfig(
        model_provider=OpenAIProvider(api_key=api_key, base_url=config["base_url"], use_responses=False),
        model=config["agent_model"],
        workflow_name="HT6 eval - jerarquica",
    )

    tmp = Path(tempfile.mkdtemp(prefix="ht6_eval_"))
    db_path = tmp / "bookings.sqlite3"
    previous = {
        "db": os.environ.get("BOOKINGS_DB"),
        "om": open_meteo_client.fetch_weather_reading,
        "bk": bookings.fetch_weather_reading,
    }
    os.environ["BOOKINGS_DB"] = str(db_path)
    if clima != "live":
        fake = _fake_fetch(WEATHER_SCENARIOS[clima])
        open_meteo_client.fetch_weather_reading = fake
        bookings.fetch_weather_reading = fake

    metadata = {
        "fecha_resuelta": test_vars.get("fecha"),
        "clima": clima,
        "clima_lectura": asdict(WEATHER_SCENARIOS[clima]) if clima != "live" else None,
        "modelo_agente": config["agent_model"],
    }
    try:
        _warm_up_embeddings()
        seed = test_vars.get("precargar_reserva")
        if seed:
            # Cita existente antes del run, creada con el servicio real.
            seeded = bookings.create_booking(seed["fecha"], seed["nombre"], seed["hora"], db_path=db_path)
            metadata["reserva_precargada"] = {"id": seeded["id"], "estado": seeded["estado"]}

        COLLECTOR.spans.clear()
        trace_id = gen_trace_id()
        try:
            result, elapsed_ms = _LOOP.run_until_complete(_run_agent(prompt, run_config, trace_id))
        except Exception as exc:  # errores del modelo/proveedor: se reportan, no se ocultan
            metadata["tool_calls"] = COLLECTOR.tool_calls(trace_id)
            metadata["bookings_rows"] = _read_bookings(db_path)
            return {"error": f"{type(exc).__name__}: {exc}", "metadata": metadata}

        usage = result.context_wrapper.usage
        metadata.update({
            "tool_calls": COLLECTOR.tool_calls(trace_id),
            "bookings_rows": _read_bookings(db_path),
            "agent_latency_ms": round(elapsed_ms, 1),
        })
        return {
            "output": str(result.final_output),
            # Tiempo de Runner.run del Supervisor (incluye todas las llamadas al
            # LLM y a las tools); excluye preparación del harness.
            "latencyMs": round(elapsed_ms),
            "tokenUsage": {
                "total": usage.total_tokens,
                "prompt": usage.input_tokens,
                "completion": usage.output_tokens,
                "numRequests": usage.requests,
            },
            "metadata": metadata,
        }
    finally:
        open_meteo_client.fetch_weather_reading = previous["om"]
        bookings.fetch_weather_reading = previous["bk"]
        if previous["db"] is None:
            os.environ.pop("BOOKINGS_DB", None)
        else:
            os.environ["BOOKINGS_DB"] = previous["db"]
