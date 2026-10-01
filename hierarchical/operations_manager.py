"""Submanager de Operaciones — Integrante 2 (arquitectura jerárquica).

Coordina el Agente de Clima y el Agente de Reservas, exponiéndolos como
herramientas (`as_tool`) al Supervisor General. No contiene lógica de
negocio propia de clima ni de reservas: solo delega y aplica la regla de
negocio de "consultar clima antes de calendarizar".
"""

from agents import Agent

from hierarchical.booking_agent_stub import booking_agent
from hierarchical.weather_agent import weather_agent

operations_manager = Agent(
    name="Submanager Operaciones",
    handoff_description=(
        "Coordina las operaciones de clima y reservas de saltos de Parachute S.A."
    ),
    instructions=(
        "Eres el submanager de operaciones de Parachute S.A. Coordinas dos "
        "capacidades especializadas mediante herramientas:\n"
        "- consultar_clima: úsala para saber si las condiciones climáticas "
        "permiten saltar en una fecha dada.\n"
        "- gestionar_reserva: úsala para calendarizar una cita.\n\n"
        "Regla de negocio obligatoria: SIEMPRE consulta el clima antes de "
        "calendarizar una cita. Si el clima está 'prohibido', no calendarices "
        "y explica el motivo al usuario. Si está 'marginal', informa las "
        "restricciones aplicables y explica que se registra pendiente de revisión. "
        "Pide nombre, fecha y hora si faltan; nunca llames confirmada a una cita "
        "pendiente_revision. Reporta el ID y estado devueltos por gestionar_reserva."
    ),
    tools=[
        weather_agent.as_tool(
            tool_name="consultar_clima",
            tool_description=(
                "Consulta si las condiciones climáticas permiten saltar en una "
                "fecha dada (formato YYYY-MM-DD)."
            ),
        ),
        booking_agent.as_tool(
            tool_name="gestionar_reserva",
            tool_description=(
                "Calendariza una cita de salto para un cliente en una fecha dada."
            ),
        ),
    ],
)
