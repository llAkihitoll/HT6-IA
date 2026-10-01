"""Evaluador climático compartido para decidir si es seguro saltar.

Responsabilidad del Integrante 2 (Hoja de Trabajo #5).

Este módulo es puro y determinista:
- NO hace llamadas HTTP.
- NO conoce Open-Meteo ni ninguna API externa.
- NO gestiona reservas ni responde FAQs.
- NO coordina agentes.

Solo recibe una `WeatherReading` (ver `weather_contracts.py`) y devuelve una
`WeatherAssessment` con el estado (ideal/marginal/prohibido), los motivos y
las restricciones aplicables, según los umbrales del enunciado.

Interpretación de límites (confirmada con el equipo, ya que el enunciado no
la especifica explícitamente): los límites superiores de "ideal" y
inferiores de "prohibido" usan desigualdad estricta (< / >); el rango
"marginal" es cerrado en ambos extremos (incluye los valores límite).

    Viento sostenido : < 20 ideal | 20 <= v <= 28 marginal | > 28 prohibido
    Ráfagas          : v <= 35 sin restricción             | > 35 prohibido
    Precipitación    : v == 0.0 ideal                      | > 0.0 prohibido
    Cobertura nubes  : < 30 ideal | 30 <= v <= 75 marginal  | > 75 prohibido

El estado global del salto es el peor caso entre las 4 variables evaluadas
(prohibido > marginal > ideal).
"""

from dataclasses import dataclass, field

from shared.weather_contracts import WeatherReading

IDEAL = "ideal"
MARGINAL = "marginal"
PROHIBIDO = "prohibido"

_SEVERITY = {IDEAL: 0, MARGINAL: 1, PROHIBIDO: 2}

WIND_SPEED_IDEAL_MAX = 20.0
WIND_SPEED_MARGINAL_MAX = 28.0
WIND_GUST_MAX = 35.0
CLOUD_COVER_IDEAL_MAX = 30.0
CLOUD_COVER_MARGINAL_MAX = 75.0


@dataclass(frozen=True)
class WeatherAssessment:
    """Resultado de evaluar una `WeatherReading` contra los umbrales."""

    status: str
    reasons: list[str] = field(default_factory=list)
    restrictions: list[str] = field(default_factory=list)
    per_variable: dict[str, str] = field(default_factory=dict)


def _evaluate_wind_speed(wind_speed_10m: float) -> tuple[str, str | None, str | None]:
    if wind_speed_10m > WIND_SPEED_MARGINAL_MAX:
        return (
            PROHIBIDO,
            f"Velocidad del viento de {wind_speed_10m} km/h supera 28 km/h: "
            "muy difícil de controlar el salto.",
            None,
        )
    if wind_speed_10m >= WIND_SPEED_IDEAL_MAX:
        return (
            MARGINAL,
            f"Velocidad del viento de {wind_speed_10m} km/h está entre 20 y 28 km/h.",
            "Solo tándem experimentado.",
        )
    return (IDEAL, None, None)


def _evaluate_wind_gust(wind_gust_10m: float) -> tuple[str, str | None]:
    if wind_gust_10m > WIND_GUST_MAX:
        return (
            PROHIBIDO,
            f"Ráfagas de viento de {wind_gust_10m} km/h superan 35 km/h.",
        )
    return (IDEAL, None)


def _evaluate_precipitation(precipitation: float) -> tuple[str, str | None]:
    if precipitation > 0.0:
        return (
            PROHIBIDO,
            f"Precipitación de {precipitation} mm: saltar con lluvia daña el "
            "equipo y lastima la piel.",
        )
    return (IDEAL, None)


def _evaluate_cloud_cover(cloud_cover: float) -> tuple[str, str | None]:
    if cloud_cover > CLOUD_COVER_MARGINAL_MAX:
        return (
            PROHIBIDO,
            f"Cobertura de nubes de {cloud_cover}%: un techo de nubes bajo "
            "impide las reglas de vuelo visual.",
        )
    if cloud_cover >= CLOUD_COVER_IDEAL_MAX:
        return (
            MARGINAL,
            f"Cobertura de nubes de {cloud_cover}% está entre 30% y 75%: nubes dispersas.",
        )
    return (IDEAL, None)


def evaluate_weather(reading: WeatherReading) -> WeatherAssessment:
    """Evalúa una lectura climática y devuelve el veredicto de seguridad."""

    reasons: list[str] = []
    restrictions: list[str] = []
    per_variable: dict[str, str] = {}

    wind_status, wind_reason, wind_restriction = _evaluate_wind_speed(reading.wind_speed_10m)
    per_variable["wind_speed_10m"] = wind_status
    if wind_reason:
        reasons.append(wind_reason)
    if wind_restriction:
        restrictions.append(wind_restriction)

    gust_status, gust_reason = _evaluate_wind_gust(reading.wind_gust_10m)
    per_variable["wind_gust_10m"] = gust_status
    if gust_reason:
        reasons.append(gust_reason)

    precip_status, precip_reason = _evaluate_precipitation(reading.precipitation)
    per_variable["precipitation"] = precip_status
    if precip_reason:
        reasons.append(precip_reason)

    cloud_status, cloud_reason = _evaluate_cloud_cover(reading.cloud_cover)
    per_variable["cloud_cover"] = cloud_status
    if cloud_reason:
        reasons.append(cloud_reason)

    overall = max(
        (wind_status, gust_status, precip_status, cloud_status),
        key=lambda status: _SEVERITY[status],
    )

    return WeatherAssessment(
        status=overall,
        reasons=reasons,
        restrictions=restrictions,
        per_variable=per_variable,
    )
