"""Supervisor General — Integrante 2 (arquitectura jerárquica).

Nivel superior de la jerarquía: decide si una solicitud del usuario debe
atenderse con el Agente de FAQs o con el Submanager de Operaciones (clima
+ reservas), y delega usando `as_tool`. No responde FAQs ni gestiona clima
o reservas directamente — solo decide y delega.

    Usuario
       │
       ▼
  Supervisor General
     /        \\
    ▼          ▼
Agente FAQs   Submanager Operaciones
                  /        \\
                 ▼          ▼
          Agente Clima   Agente Reservas
"""

from agents import Agent

from hierarchical.faq_agent_stub import faq_agent
from hierarchical.operations_manager import operations_manager

supervisor = Agent(
    name="Supervisor General",
    instructions=(
        "Eres el Supervisor General de Parachute S.A. No respondes preguntas "
        "directamente ni ejecutas operaciones tú mismo: delegas cada "
        "solicitud del usuario a la herramienta adecuada.\n"
        "- Si la solicitud es una pregunta frecuente (información general de "
        "la empresa, requisitos, políticas, etc.), usa responder_faq.\n"
        "- Si la solicitud es sobre clima, condiciones para saltar, o "
        "calendarizar/reprogramar una cita, usa gestionar_operaciones.\n"
        "Después de recibir la respuesta de la herramienta, repórtala al "
        "usuario de forma clara y sin inventar información adicional."
    ),
    tools=[
        faq_agent.as_tool(
            tool_name="responder_faq",
            tool_description="Responde preguntas frecuentes sobre Parachute S.A.",
        ),
        operations_manager.as_tool(
            tool_name="gestionar_operaciones",
            tool_description=(
                "Gestiona operaciones de clima y reservas: consulta si el "
                "clima permite saltar en una fecha, y calendariza citas."
            ),
        ),
    ],
)
