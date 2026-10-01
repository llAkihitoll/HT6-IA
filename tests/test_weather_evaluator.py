"""Pruebas de límites para el evaluador climático (Integrante 2, HT5).

Cubre cada umbral del enunciado con: un valor claramente dentro del rango,
el valor exacto en el límite, y un valor inmediatamente fuera del límite.
"""

import pytest

from shared.weather_contracts import WeatherReading
from shared.weather_evaluator import IDEAL, MARGINAL, PROHIBIDO, evaluate_weather


def make_reading(
    wind_speed_10m=10.0,
    wind_gust_10m=10.0,
    precipitation=0.0,
    cloud_cover=10.0,
    temperature_2m=20.0,
):
    """Lectura base con todas las variables en zona ideal, salvo la que se
    esté probando en cada caso."""

    return WeatherReading(
        wind_speed_10m=wind_speed_10m,
        wind_gust_10m=wind_gust_10m,
        precipitation=precipitation,
        cloud_cover=cloud_cover,
        temperature_2m=temperature_2m,
    )


# ---------------------------------------------------------------------------
# Velocidad del viento sostenido: <20 ideal | 20-28 marginal | >28 prohibido
# ---------------------------------------------------------------------------


def test_wind_speed_claramente_ideal():
    result = evaluate_weather(make_reading(wind_speed_10m=10.0))
    assert result.per_variable["wind_speed_10m"] == IDEAL


def test_wind_speed_limite_20_es_marginal():
    result = evaluate_weather(make_reading(wind_speed_10m=20.0))
    assert result.per_variable["wind_speed_10m"] == MARGINAL


def test_wind_speed_dentro_de_20_28_es_marginal():
    result = evaluate_weather(make_reading(wind_speed_10m=24.0))
    assert result.per_variable["wind_speed_10m"] == MARGINAL


def test_wind_speed_limite_28_es_marginal():
    result = evaluate_weather(make_reading(wind_speed_10m=28.0))
    assert result.per_variable["wind_speed_10m"] == MARGINAL


def test_wind_speed_mayor_a_28_es_prohibido():
    result = evaluate_weather(make_reading(wind_speed_10m=28.1))
    assert result.per_variable["wind_speed_10m"] == PROHIBIDO


def test_wind_speed_marginal_agrega_restriccion_tandem():
    result = evaluate_weather(make_reading(wind_speed_10m=24.0))
    assert "Solo tándem experimentado." in result.restrictions


def test_wind_speed_prohibido_agrega_motivo_dificil_de_controlar():
    result = evaluate_weather(make_reading(wind_speed_10m=30.0))
    assert any("difícil de controlar" in reason for reason in result.reasons)


# ---------------------------------------------------------------------------
# Ráfagas de viento: <=35 sin restricción | >35 prohibido
# ---------------------------------------------------------------------------


def test_wind_gust_por_debajo_de_35_no_restringe():
    result = evaluate_weather(make_reading(wind_gust_10m=20.0))
    assert result.per_variable["wind_gust_10m"] == IDEAL


def test_wind_gust_limite_35_no_restringe():
    result = evaluate_weather(make_reading(wind_gust_10m=35.0))
    assert result.per_variable["wind_gust_10m"] == IDEAL


def test_wind_gust_por_encima_de_35_es_prohibido():
    result = evaluate_weather(make_reading(wind_gust_10m=35.1))
    assert result.per_variable["wind_gust_10m"] == PROHIBIDO
    assert any("Ráfagas" in reason for reason in result.reasons)


# ---------------------------------------------------------------------------
# Precipitación: 0.0 ideal | >0.0 prohibido
# ---------------------------------------------------------------------------


def test_precipitation_cero_es_ideal():
    result = evaluate_weather(make_reading(precipitation=0.0))
    assert result.per_variable["precipitation"] == IDEAL


def test_precipitation_mayor_a_cero_es_prohibido():
    result = evaluate_weather(make_reading(precipitation=0.1))
    assert result.per_variable["precipitation"] == PROHIBIDO
    assert any("daña el equipo" in reason for reason in result.reasons)


# ---------------------------------------------------------------------------
# Cobertura de nubes: <30 ideal | 30-75 marginal | >75 prohibido
# ---------------------------------------------------------------------------


def test_cloud_cover_claramente_ideal():
    result = evaluate_weather(make_reading(cloud_cover=10.0))
    assert result.per_variable["cloud_cover"] == IDEAL


def test_cloud_cover_limite_30_es_marginal():
    result = evaluate_weather(make_reading(cloud_cover=30.0))
    assert result.per_variable["cloud_cover"] == MARGINAL


def test_cloud_cover_dentro_de_30_75_es_marginal():
    result = evaluate_weather(make_reading(cloud_cover=50.0))
    assert result.per_variable["cloud_cover"] == MARGINAL


def test_cloud_cover_limite_75_es_marginal():
    result = evaluate_weather(make_reading(cloud_cover=75.0))
    assert result.per_variable["cloud_cover"] == MARGINAL


def test_cloud_cover_mayor_a_75_es_prohibido():
    result = evaluate_weather(make_reading(cloud_cover=75.1))
    assert result.per_variable["cloud_cover"] == PROHIBIDO
    assert any("vuelo visual" in reason for reason in result.reasons)


# ---------------------------------------------------------------------------
# Estados globales combinados
# ---------------------------------------------------------------------------


def test_condiciones_completamente_ideales():
    result = evaluate_weather(
        make_reading(
            wind_speed_10m=5.0,
            wind_gust_10m=5.0,
            precipitation=0.0,
            cloud_cover=5.0,
        )
    )
    assert result.status == IDEAL
    assert result.reasons == []
    assert result.restrictions == []


def test_condiciones_marginales_por_viento():
    result = evaluate_weather(make_reading(wind_speed_10m=25.0))
    assert result.status == MARGINAL
    assert result.restrictions == ["Solo tándem experimentado."]


def test_condiciones_marginales_por_nubes():
    result = evaluate_weather(make_reading(cloud_cover=50.0))
    assert result.status == MARGINAL


def test_condiciones_prohibidas_por_una_sola_variable():
    result = evaluate_weather(make_reading(precipitation=1.0))
    assert result.status == PROHIBIDO


def test_multiples_condiciones_prohibidas_simultaneas():
    result = evaluate_weather(
        make_reading(
            wind_speed_10m=40.0,
            wind_gust_10m=50.0,
            precipitation=2.0,
            cloud_cover=90.0,
        )
    )
    assert result.status == PROHIBIDO
    assert len(result.reasons) == 4


def test_prohibido_tiene_prioridad_sobre_marginal():
    result = evaluate_weather(
        make_reading(wind_speed_10m=24.0, precipitation=1.0)
    )
    assert result.status == PROHIBIDO
    assert len(result.reasons) == 2


@pytest.mark.parametrize(
    "field_name, value",
    [
        ("wind_speed_10m", 19.999),
        ("wind_gust_10m", 34.999),
        ("cloud_cover", 29.999),
    ],
)
def test_valores_inmediatamente_por_debajo_del_limite_ideal(field_name, value):
    result = evaluate_weather(make_reading(**{field_name: value}))
    assert result.per_variable[field_name] == IDEAL
