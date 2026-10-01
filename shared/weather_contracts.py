"""Contrato de datos climáticos compartido entre las tres arquitecturas.

Este dataclass describe las 5 variables que exige la Hoja de Trabajo #5
(wind_gust_10m, temperature_2m, precipitation, cloud_cover, wind_speed_10m).

NOTA PARA EL EQUIPO: esta es una definición PROVISIONAL creada por el
Integrante 2 porque al momento de escribirla no existía todavía una
integración real con Open-Meteo en el repositorio. Si el Integrante 1
(responsable de esa integración) ya define su propia estructura de datos,
esta clase debe alinearse con la suya en lugar de duplicarla.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class WeatherReading:
    """Lectura climática puntual para una fecha/hora de aterrizaje."""

    wind_speed_10m: float
    """Velocidad del viento sostenido a 10m, en km/h."""

    wind_gust_10m: float
    """Velocidad de las ráfagas de viento a 10m, en km/h."""

    precipitation: float
    """Precipitación acumulada, en mm."""

    cloud_cover: float
    """Cobertura de nubes, en porcentaje (0-100)."""

    temperature_2m: float
    """Temperatura a 2m, en °C. No forma parte de los criterios de
    seguridad del salto, pero es una de las 5 variables requeridas."""
