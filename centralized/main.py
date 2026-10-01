"""CLI interactiva de la arquitectura centralizada."""

import os

from dotenv import load_dotenv

load_dotenv()

if not os.getenv("OPENAI_API_KEY"):
    raise SystemExit(
        "Falta OPENAI_API_KEY. Copia .env.example a .env y agrega tu API key."
    )

from agents import Runner  # noqa: E402

from centralized.manager import manager  # noqa: E402


def run_cli() -> None:
    print("Parachute S.A. — arquitectura centralizada (escribe 'salir' para terminar)")
    history = []
    while True:
        try:
            message = input("\nUsuario: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nHasta luego.")
            break
        if message.casefold() in {"salir", "exit", "quit"}:
            break
        if not message:
            continue
        result = Runner.run_sync(manager, history + [{"role": "user", "content": message}])
        history = result.to_input_list()
        print(f"Manager: {result.final_output}")


if __name__ == "__main__":
    run_cli()
