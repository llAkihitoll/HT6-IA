"""Grafo de especialistas pares: no hay supervisor ni llamadas as_tool."""

import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from agents import Agent, RunHooks, function_tool
from shared.specialists import make_faq_agent, make_booking_agent
from shared.weather_service import describe_jump_weather


@function_tool
async def consultar_clima(fecha_iso: str) -> str:
    """Consulta y evalúa Open-Meteo para una fecha YYYY-MM-DD."""
    return await asyncio.to_thread(describe_jump_weather, fecha_iso)


def build_agents(model=None) -> dict[str, Agent]:
    faq = make_faq_agent()
    booking = make_booking_agent()
    weather = Agent(
        name="Agente Clima",
        handoff_description="Pronóstico y condiciones para saltar en una fecha.",
        instructions=(
            "Pregunta la fecha si falta y usa consultar_clima. Reporta sus cinco "
            "variables, estado, motivos y restricciones. Si el usuario quiere "
            "agendar y no está prohibido ni hay error, transfiere a Agente Reservas. "
            "Si está prohibido, explica y pide otra fecha. No inventes pronósticos. "
            "Para preguntas informativas transfiere a Agente FAQs."
        ),
        tools=[consultar_clima],
    )
    faq.instructions += (
        " Para clima o intención de reservar, transfiere a Agente Clima; no "
        "resuelvas esas operaciones tú mismo. Eres un especialista, no un manager."
    )
    booking.instructions += (
        " Si falta consultar el clima para la fecha actual de la solicitud, "
        "transfiere a Agente Clima. Si la fecha cambia, consulta esa nueva fecha. "
        "Para preguntas informativas transfiere a Agente FAQs."
    )
    faq.handoffs = [weather]
    weather.handoffs = [faq, booking]
    booking.handoffs = [faq, weather]
    for agent in (faq, weather, booking):
        agent.instructions = dated_instructions(agent.instructions)
        if model is not None:
            agent.model = model
    return {"faq": faq, "clima": weather, "reservas": booking}


def dated_instructions(base):
    # El SDK exige exactamente (context, agent); la clausura conserva el texto.
    def instructions(context, agent):
        today = datetime.now(ZoneInfo("America/Guatemala")).date().isoformat()
        return (base + f" Hoy en Guatemala es {today}. "
                "Conserva los datos del historial al transferir. No transfieras "
                "sin motivo; si faltan datos pregunta al usuario y termina el turno.")
    return instructions


class HandoffTrace(RunHooks):
    """Muestra las transferencias para poder verificar el diagrama en la CLI."""
    async def on_handoff(self, context, from_agent, to_agent):
        print(f"[handoff] {from_agent.name} -> {to_agent.name}")
