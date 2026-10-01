"""Programa de demostración — Arquitectura jerárquica (Integrante 2, HT5).

Ejecuta el flujo completo de la jerarquía:

    Usuario -> Supervisor General -> [Agente FAQs | Submanager Operaciones]
                                            -> [Agente Clima | Agente Reservas]

usando el SDK de OpenAI Agents (`Runner` + `Agent.as_tool()`). Requiere
una variable de entorno `OPENAI_API_KEY` válida (ver `.env.example` y
`docs/EJECUCION_INTEGRANTE2.md`).
"""

import os

from dotenv import load_dotenv

load_dotenv()

if not os.getenv("OPENAI_API_KEY"):
    raise SystemExit(
        "Falta OPENAI_API_KEY. Copia .env.example a .env y coloca tu API key "
        "antes de ejecutar la demo (ver docs/EJECUCION_INTEGRANTE2.md)."
    )

from agents import Runner  # noqa: E402  (import tras validar la API key)

from hierarchical.supervisor import supervisor  # noqa: E402

DEMO_QUERIES = [
    ("FAQs", "¿Cuál es la edad mínima para poder hacer el salto en tándem?"),
    (
        "Clima (dentro del horizonte de 16 días)",
        "¿Las condiciones climáticas permiten saltar el 2026-09-22?",
    ),
    (
        "Reservas (consulta clima antes de calendarizar)",
        "Quiero calendarizar una cita de salto para el 2026-09-22, a las 09:00, mi nombre es Juana Pérez.",
    ),
    (
        "Clima (fuera del horizonte de pronóstico de Open-Meteo)",
        "¿Puedo saltar el 2027-01-01?",
    ),
]


def run_demo() -> None:
    for titulo, mensaje in DEMO_QUERIES:
        print("=" * 80)
        print(f"[{titulo}]")
        print(f"Usuario: {mensaje}")
        print("-" * 80)
        result = Runner.run_sync(supervisor, mensaje)
        print(f"Supervisor General: {result.final_output}")
        print()


if __name__ == "__main__":
    run_demo()
