"""Reservas SQLite con verificación climática y unicidad transaccional.

Ningún agente puede aportar un veredicto para saltarse la consulta real.
Las condiciones marginales quedan pendientes; las prohibidas no se guardan.
"""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from shared.open_meteo_client import TIMEZONE, fetch_weather_reading, validate_forecast_date
from shared.weather_evaluator import evaluate_weather, PROHIBIDO, MARGINAL

ROOT = Path(__file__).resolve().parents[1]


class BookingError(ValueError):
    """Solicitud incompleta o rechazada antes de escribir una cita."""


def create_booking(fecha_iso: str, nombre_cliente: str, hora: str = "09:00", *,
                   db_path: str | Path | None = None) -> dict:
    """Reconsulta el clima, evalúa y guarda; un reintento retorna el mismo ID.

    `hora` corresponde a America/Guatemala. No se implementan cupos ni pagos.
    El clima se evalúa por día, aunque la cita tenga una hora concreta.
    """
    now = datetime.now(ZoneInfo(TIMEZONE))
    requested = validate_forecast_date(fecha_iso, today=now.date())
    name = " ".join(nombre_cliente.split())
    if not name or len(name) > 150:
        raise BookingError("Indica un nombre de cliente entre 1 y 150 caracteres.")
    try:
        clock = datetime.strptime(hora, "%H:%M").time()
        if clock.strftime("%H:%M") != hora:
            raise ValueError
    except ValueError as exc:
        raise BookingError("La hora debe tener formato HH:MM de 24 horas.") from exc
    if datetime.combine(requested, clock, tzinfo=ZoneInfo(TIMEZONE)) <= now:
        raise BookingError("La fecha y hora de la cita ya pasaron.")

    # La validación se ejecuta incluso si llaman directamente a esta función.
    reading = fetch_weather_reading(fecha_iso)
    assessment = evaluate_weather(reading)
    if assessment.status == PROHIBIDO:
        raise BookingError("No se puede reservar: " + "; ".join(assessment.reasons))
    state = "pendiente_revision" if assessment.status == MARGINAL else "confirmada"
    target = Path(db_path or os.getenv("BOOKINGS_DB", "data/bookings.sqlite3")).expanduser()
    if not target.is_absolute():
        target = ROOT / target
    target.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(target, timeout=10) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("""CREATE TABLE IF NOT EXISTS bookings (
            id TEXT PRIMARY KEY, fecha TEXT NOT NULL, hora TEXT NOT NULL,
            cliente TEXT NOT NULL, cliente_key TEXT NOT NULL,
            estado TEXT NOT NULL, clima_json TEXT NOT NULL,
            evaluacion_json TEXT NOT NULL, created_at TEXT NOT NULL,
            UNIQUE(fecha, hora, cliente_key)
        )""")
        identifier = uuid4().hex
        conn.execute("""INSERT INTO bookings VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(fecha, hora, cliente_key) DO NOTHING""",
            (identifier, fecha_iso, hora, name, name.casefold(), state,
             json.dumps(asdict(reading), ensure_ascii=False, allow_nan=False),
             json.dumps(asdict(assessment), ensure_ascii=False), now.isoformat()))
        row = conn.execute("""SELECT * FROM bookings
            WHERE fecha=? AND hora=? AND cliente_key=?""",
            (fecha_iso, hora, name.casefold())).fetchone()
    # Se informa el estado persistido, sin alterar una cita previa al reintentar.
    return {
        "id": row["id"], "fecha": row["fecha"], "hora": row["hora"],
        "zona_horaria": TIMEZONE, "cliente": row["cliente"], "estado": row["estado"],
        "ya_existia": row["id"] != identifier,
        "evaluacion_al_registrar": json.loads(row["evaluacion_json"]),
        "evaluacion_actual": asdict(assessment),
        "requiere_revision": state == "pendiente_revision" or row["estado"] == "pendiente_revision",
    }
