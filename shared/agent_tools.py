"""Herramientas comunes para los tres estilos de orquestación."""

import asyncio
import json
import logging
import sqlite3

from agents import function_tool

from shared import faqs, bookings
from shared.open_meteo_client import WeatherProviderError

logger = logging.getLogger(__name__)


def encode(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


@function_tool
async def buscar_faq(pregunta: str) -> str:
    """Recupera evidencia de las FAQs del Lab 4; nunca inventa una respuesta."""
    try:
        results = await asyncio.to_thread(faqs.search_faqs, pregunta)
        return encode({"resultados": results, "sin_evidencia": not results})
    except Exception:
        logger.warning("Consulta de FAQs no disponible; revisa configuración y base local.")
        return encode({"error": "No se pudo consultar la base de FAQs. Verifica PostgreSQL y la carga del corpus.",
                       "resultados": []})


@function_tool
async def calendarizar_cita(fecha_iso: str, nombre_cliente: str, hora: str = "09:00") -> str:
    """Guarda una cita tras reconsultar clima. Marginal queda pendiente de revisión.

    Args:
        fecha_iso: Fecha solicitada, YYYY-MM-DD.
        nombre_cliente: Nombre indicado por el usuario.
        hora: Hora acordada con el usuario en Guatemala, HH:MM (24 horas).
    """
    try:
        result = await asyncio.to_thread(bookings.create_booking, fecha_iso, nombre_cliente, hora)
        return encode(result)
    except (bookings.BookingError, WeatherProviderError) as exc:
        return encode({"error": str(exc), "registrada": False})
    except (sqlite3.Error, OSError):
        return encode({"error": "No fue posible guardar la cita. Intenta nuevamente.", "registrada": False})
