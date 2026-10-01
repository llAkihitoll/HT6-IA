"""Caso de uso compartido: consultar y evaluar el clima de un salto."""

from shared.open_meteo_client import get_weather_reading
from shared.weather_evaluator import evaluate_weather


def describe_jump_weather(fecha_iso: str) -> str:
    reading, error = get_weather_reading(fecha_iso)
    if error:
        return error
    if reading is None:  # Defensa adicional para proveedores intercambiables.
        return "No fue posible obtener el pronóstico solicitado."

    assessment = evaluate_weather(reading)
    lines = [
        f"Estado del clima para {fecha_iso}: {assessment.status.upper()}.",
        (
            "Valores: "
            f"viento={reading.wind_speed_10m} km/h, "
            f"ráfagas={reading.wind_gust_10m} km/h, "
            f"precipitación={reading.precipitation} mm, "
            f"nubes={reading.cloud_cover}%, "
            f"temperatura={reading.temperature_2m} °C."
        ),
    ]
    if assessment.reasons:
        lines.append("Motivos: " + "; ".join(assessment.reasons))
    if assessment.restrictions:
        lines.append("Restricciones: " + "; ".join(assessment.restrictions))
    return "\n".join(lines)
