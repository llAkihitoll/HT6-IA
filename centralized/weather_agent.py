"""Especialista climático usado como herramienta por el manager central."""

from agents import Agent, function_tool

from shared.weather_service import describe_jump_weather


@function_tool
def consultar_clima(fecha_iso: str) -> str:
    """Consulta y evalúa el clima para una fecha YYYY-MM-DD."""

    return describe_jump_weather(fecha_iso)


weather_agent = Agent(
    name="Agente de Clima",
    instructions=(
        "Consulta siempre la fecha solicitada mediante consultar_clima. "
        "Devuelve fielmente el estado, valores, motivos y restricciones. "
        "No calendarices citas ni inventes datos."
    ),
    tools=[consultar_clima],
)
