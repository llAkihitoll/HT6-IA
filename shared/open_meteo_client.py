"""Cliente reutilizable para el pronóstico diario de Open-Meteo.

Este módulo no conoce agentes ni arquitecturas de orquestación. Las tres
implementaciones pueden reutilizarlo sin cambiar la lógica de integración.
"""

from __future__ import annotations

import json
import math
from datetime import date, datetime
from typing import Any, Callable
from zoneinfo import ZoneInfo
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from shared.weather_contracts import WeatherReading

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
LANDING_LATITUDE = 14.013722
LANDING_LONGITUDE = -90.771611
TIMEZONE = "America/Guatemala"
MAX_FORECAST_DAYS = 16
REQUEST_TIMEOUT_SECONDS = 10

# Open-Meteo usa nombres de agregados diarios. Se traducen al contrato
# WeatherReading para que el resto del sistema no dependa de la API externa.
DAILY_VARIABLES = (
    "temperature_2m_mean",
    "precipitation_sum",
    "cloud_cover_max",
    "wind_speed_10m_max",
    "wind_gusts_10m_max",
)


class WeatherProviderError(RuntimeError):
    """Error esperado al validar o consultar un pronóstico."""


RequestJson = Callable[[str, float], dict[str, Any]]


def validate_forecast_date(fecha_iso: str, *, today: date | None = None) -> date:
    """Valida formato, fecha pasada y horizonte máximo de 16 días."""

    try:
        requested = datetime.strptime(fecha_iso, "%Y-%m-%d").date()
        if requested.isoformat() != fecha_iso:
            raise ValueError
    except ValueError as exc:
        raise WeatherProviderError(
            f"Fecha inválida: '{fecha_iso}'. Usa el formato YYYY-MM-DD."
        ) from exc

    reference = today or datetime.now(ZoneInfo(TIMEZONE)).date()
    days_ahead = (requested - reference).days
    if days_ahead < 0:
        raise WeatherProviderError(f"La fecha {fecha_iso} ya pasó.")
    if days_ahead >= MAX_FORECAST_DAYS:
        raise WeatherProviderError(
            f"No es posible consultar el pronóstico para {fecha_iso}: "
            f"Open-Meteo solo permite consultar hasta {MAX_FORECAST_DAYS} días incluyendo hoy."
        )
    return requested


def build_forecast_url(requested: date) -> str:
    """Construye una URL diaria para las coordenadas del lugar de aterrizaje."""

    params = {
        "latitude": LANDING_LATITUDE,
        "longitude": LANDING_LONGITUDE,
        "daily": ",".join(DAILY_VARIABLES),
        "timezone": TIMEZONE,
        "wind_speed_unit": "kmh",
        "precipitation_unit": "mm",
        "temperature_unit": "celsius",
        "start_date": requested.isoformat(),
        "end_date": requested.isoformat(),
    }
    return f"{FORECAST_URL}?{urlencode(params)}"


def _request_json(url: str, timeout: float) -> dict[str, Any]:
    try:
        with urlopen(url, timeout=timeout) as response:  # noqa: S310 (URL fija HTTPS)
            payload = json.load(response)
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise WeatherProviderError(
            "No fue posible comunicarse con Open-Meteo. Intenta nuevamente."
        ) from exc

    if not isinstance(payload, dict):
        raise WeatherProviderError("Open-Meteo devolvió una respuesta inesperada.")
    if payload.get("error"):
        reason = payload.get("reason", "error no especificado")
        raise WeatherProviderError(f"Open-Meteo rechazó la consulta: {reason}.")
    return payload


def _daily_value(daily: dict[str, Any], field: str, index: int) -> float:
    values = daily.get(field)
    if not isinstance(values, list) or index >= len(values) or values[index] is None:
        raise WeatherProviderError(
            f"Open-Meteo no devolvió el dato diario requerido: {field}."
        )
    try:
        value = float(values[index])
        if isinstance(values[index], bool) or not math.isfinite(value):
            raise ValueError
        if field != "temperature_2m_mean" and value < 0:
            raise ValueError
        if field == "cloud_cover_max" and value > 100:
            raise ValueError
        return value
    except (TypeError, ValueError) as exc:
        raise WeatherProviderError(
            f"Open-Meteo devolvió un valor inválido para {field}."
        ) from exc


def parse_daily_forecast(payload: dict[str, Any], requested: date) -> WeatherReading:
    """Adapta la respuesta diaria de Open-Meteo al contrato común."""

    daily = payload.get("daily")
    if not isinstance(daily, dict):
        raise WeatherProviderError("Open-Meteo no devolvió la sección daily.")

    dates = daily.get("time")
    if not isinstance(dates, list):
        raise WeatherProviderError("Open-Meteo no devolvió las fechas del pronóstico.")
    try:
        index = dates.index(requested.isoformat())
    except ValueError as exc:
        raise WeatherProviderError(
            f"Open-Meteo no devolvió datos para {requested.isoformat()}."
        ) from exc

    return WeatherReading(
        wind_speed_10m=_daily_value(daily, "wind_speed_10m_max", index),
        wind_gust_10m=_daily_value(daily, "wind_gusts_10m_max", index),
        precipitation=_daily_value(daily, "precipitation_sum", index),
        cloud_cover=_daily_value(daily, "cloud_cover_max", index),
        temperature_2m=_daily_value(daily, "temperature_2m_mean", index),
    )


def fetch_weather_reading(
    fecha_iso: str,
    *,
    today: date | None = None,
    request_json: RequestJson = _request_json,
) -> WeatherReading:
    """Valida la fecha, consulta Open-Meteo y devuelve las cinco variables."""

    requested = validate_forecast_date(fecha_iso, today=today)
    payload = request_json(build_forecast_url(requested), REQUEST_TIMEOUT_SECONDS)
    return parse_daily_forecast(payload, requested)


def get_weather_reading(fecha_iso: str) -> tuple[WeatherReading | None, str | None]:
    """Adaptador compatible con los agentes: ``(lectura, error)``."""

    try:
        return fetch_weather_reading(fecha_iso), None
    except WeatherProviderError as exc:
        return None, str(exc)
