"""Terminal con historial y continuidad del agente que conserva el control."""

import os
from agents import Runner, RunConfig, MaxTurnsExceeded
from openai import OpenAIError
from dotenv import load_dotenv
from decentralized.agents import build_agents, HandoffTrace


class Conversation:
    def __init__(self, model=None, trace=True):
        self.agents = build_agents(model)
        self.active_agent = self.agents["faq"]
        self.history = []
        self.hooks = HandoffTrace() if trace else None

    def reply(self, message: str) -> str:
        items = self.history + [{"role": "user", "content": message}]
        result = Runner.run_sync(
            self.active_agent, items, max_turns=12, hooks=self.hooks,
            run_config=RunConfig(tracing_disabled=True),
        )
        self.history = result.to_input_list()
        self.active_agent = result.last_agent
        return str(result.final_output)


def run_cli() -> None:
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") == "sk-your-key-here":
        raise SystemExit("Falta OPENAI_API_KEY. Configura .env antes de ejecutar el agente.")
    conversation = Conversation(model=os.getenv("OPENAI_MODEL") or None)
    print("Parachute S.A. — descentralizada. Escribe salir o Bye para terminar.")
    while True:
        try:
            message = input("\nUsuario: ").strip()
            if message.casefold() in {"salir", "bye", "exit", "quit"}:
                break
            if not message:
                continue
            try:
                answer = conversation.reply(message)
                print(f"{conversation.active_agent.name}: {answer}")
            except MaxTurnsExceeded:
                # No reintentar automáticamente una operación que pudo guardar datos.
                print("Se alcanzó el límite de transferencias. Reformula la solicitud; "
                      "si repites una reserva, se conserva su mismo identificador.")
            except OpenAIError:
                print("No se pudo completar la consulta al modelo. Revisa conexión, "
                      "clave y cuota; no se reintentó automáticamente.")
        except (EOFError, KeyboardInterrupt):
            print("\nHasta luego.")
            break


if __name__ == "__main__":
    run_cli()
