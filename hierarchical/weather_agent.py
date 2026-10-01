"""Agente de Clima — Integrante 2 (arquitectura jerárquica).

Obtiene y evalúa datos reales mediante el servicio compartido de Open-Meteo.
No decide reservas ni responde FAQs.
"""

from agents import Agent, function_tool

from shared.weather_service import describe_jump_weather


@function_tool
def consultar_clima_salto(fecha_iso: str) -> str:
    """Consulta el clima en el sitio de aterrizaje para `fecha_iso`
    (formato YYYY-MM-DD) y determina si las condiciones permiten realizar
    el salto (ideal, marginal o prohibido), con motivos y restricciones."""

    return describe_jump_weather(fecha_iso)


weather_agent = Agent(
    name="Agente Clima",
    handoff_description=(
        "Consulta las condiciones climáticas del sitio de aterrizaje para una "
        "fecha y determina si el salto es ideal, marginal o está prohibido."
    ),
    instructions=(
        "Eres el agente climático de Parachute S.A. Usa consultar_clima_salto "
        "con la fecha solicitada por el usuario (formato YYYY-MM-DD) y reporta "
        "el estado, los motivos y las restricciones tal como te los devuelve "
        "la herramienta, sin inventar información adicional."
    ),
    tools=[consultar_clima_salto],
)
