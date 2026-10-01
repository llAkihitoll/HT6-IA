"""Pruebas de los graders propios de los evals (HT6) y del hook de fechas.

Verifican que las assertions deterministas aprueben y reprueben lo que
deben, sin API keys, red ni Promptfoo. Varios textos son salidas reales del
agente observadas en la primera ejecución (evals/reports/run1).
"""

import importlib.util
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

EVALS = Path(__file__).resolve().parents[1] / "evals"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tc = _load("eval_tool_calls", EVALS / "assertions" / "tool_calls.py")
hooks = _load("eval_hooks", EVALS / "hooks.py")

FECHA = "2026-10-03"


def call(name, arguments, output=None, agent=None):
    return {"name": name, "arguments": arguments, "output": output, "agent": agent,
            "error": None, "started_at": None, "duration_ms": 1.0}


def ctx(calls=(), rows=(), config=None, fecha=FECHA):
    return {"metadata": {"tool_calls": list(calls), "bookings_rows": list(rows)},
            "config": config or {}, "vars": {"fecha": fecha}}


WEATHER = call("consultar_clima_salto", {"fecha_iso": FECHA}, f"Estado del clima para {FECHA}: IDEAL.")
BOOKING = call("calendarizar_cita", {"fecha_iso": FECHA, "nombre_cliente": "Ana López", "hora": "10:00"},
               {"id": "a" * 32, "estado": "confirmada", "ya_existia": False})
ROW = {"id": "a" * 32, "fecha": FECHA, "hora": "10:00", "cliente": "Ana López", "estado": "confirmada"}


# ---------------------------------------------------------------- check_tools

def test_tools_pass_with_expected_sequence_and_arguments():
    config = {"count": {"calendarizar_cita": 1}, "not_called": ["responder_faq"],
              "args": {"calendarizar_cita": {"fecha_iso": "{{fecha}}", "nombre_cliente": "ana lopez", "hora": "10:00"}},
              "weather_before_booking": True, "rows": 1, "estado": "confirmada"}
    assert tc.check_tools("", ctx([WEATHER, BOOKING], [ROW], config))["pass"]


def test_tools_fail_when_required_tool_missing():
    result = tc.check_tools("", ctx([WEATHER], [], {"count": {"calendarizar_cita": 1}}))
    assert not result["pass"] and "esperado exactamente 1" in result["reason"]


def test_tools_fail_when_forbidden_tool_called():
    assert not tc.check_tools("", ctx([WEATHER, BOOKING], [ROW], {"not_called": ["calendarizar_cita"]}))["pass"]


def test_tools_fail_on_wrong_arguments():
    config = {"args": {"calendarizar_cita": {"hora": "09:00"}}}
    assert not tc.check_tools("", ctx([WEATHER, BOOKING], [ROW], config))["pass"]


def test_tools_fail_when_booking_precedes_weather_or_other_date():
    other_day = call("consultar_clima_salto", {"fecha_iso": "2026-10-04"})
    for calls in ([BOOKING, WEATHER], [other_day, BOOKING]):
        assert not tc.check_tools("", ctx(calls, [ROW], {"weather_before_booking": True}))["pass"]


def test_tools_check_real_tool_outputs_and_rows():
    rejected = call("calendarizar_cita", BOOKING["arguments"], {"error": "No se puede reservar", "registrada": False})
    assert tc.check_tools("", ctx([WEATHER, rejected], [], {"rows": 0, "booking_outputs": {"registrada": False}}))["pass"]
    assert not tc.check_tools("", ctx([WEATHER, BOOKING], [ROW], {"rows": 0}))["pass"]
    pending = dict(ROW, estado="pendiente_revision")
    assert not tc.check_tools("", ctx([], [pending], {"estado": "confirmada"}))["pass"]


def test_tools_without_metadata_fail_instead_of_passing():
    assert not tc.check_tools("", {"metadata": {}, "config": {}, "vars": {}})["pass"]


# --------------------------------------------------------------- check_claims

@pytest.mark.parametrize("text", [
    "Tu cita quedó confirmada.",
    "Listo, la reserva fue registrada para el sábado.",
    "Sí, la cita fue agendada.",
])
def test_claims_fail_when_no_booking_exists(text):
    assert not tc.check_claims(text, ctx())["pass"]


@pytest.mark.parametrize("text", [
    "No se puede reservar: la cita no fue registrada.",
    "La cita no está confirmada por el clima.",
    # Salida real de R2 (run1): condicional, no afirma una cita creada.
    "Tu solicitud se registrará como pendiente de revisión y no se marcará como confirmada. "
    "Una vez confirmado, gestionaremos la reserva a la brevedad.",
])
def test_claims_accept_negated_or_conditional_statements(text):
    assert tc.check_claims(text, ctx())["pass"]


def test_claims_pending_booking_cannot_be_called_confirmed():
    pending = dict(ROW, estado="pendiente_revision")
    assert not tc.check_claims("Tu cita está confirmada.", ctx(rows=[pending]))["pass"]
    assert tc.check_claims("Quedó pendiente de revisión, no confirmada.", ctx(rows=[pending]))["pass"]


def test_claims_cited_id_must_exist():
    assert tc.check_claims(f"ID: {'a' * 32}", ctx(rows=[ROW]))["pass"]
    assert not tc.check_claims(f"ID: {'b' * 32}", ctx(rows=[ROW]))["pass"]


# ------------------------------------------------------ check_live_consistency

@pytest.mark.parametrize("verdict,rows,ok", [
    ("PROHIBIDO", [], True),
    ("PROHIBIDO", [ROW], False),
    ("IDEAL", [ROW], True),
    ("IDEAL", [], False),
    ("MARGINAL", [dict(ROW, estado="pendiente_revision")], True),
])
def test_live_consistency_follows_real_verdict(verdict, rows, ok):
    weather = call("consultar_clima_salto", {"fecha_iso": FECHA}, f"Estado del clima para {FECHA}: {verdict}.")
    assert tc.check_live_consistency("Respuesta.", ctx([weather], rows))["pass"] is ok


def test_live_consistency_without_weather_call_fails():
    assert not tc.check_live_consistency("Respuesta.", ctx())["pass"]


# ---------------------------------------------------------------- check_dates

@pytest.mark.parametrize("text", [
    f"Tu cita del {FECHA} quedó confirmada.",
    "Tu cita del 2026‑10‑03 quedó confirmada.",   # guion no separable, como lo escribe el modelo
    "El clima del 3 de octubre de 2026 está prohibido.",
    "El clima del 3 octubre de 2026 está prohibido.",
    "Necesito tu nombre y la hora.",
])
def test_dates_accept_the_requested_day(text):
    assert tc.check_dates(text, ctx())["pass"]


def test_dates_reject_other_day():
    # Salida real de R8 (run1): pidió el 2026-10-02 y respondió con otro día.
    text = "Lamento informarte que el **24 de octubre de 2026 a las 10:00** está **prohibido**."
    result = tc.check_dates(text, ctx(fecha="2026-10-02"))
    assert not result["pass"] and "2026-10-24" in result["reason"]


# ---------------------------------------------------------------------- hooks

def test_hook_resolves_relative_date_in_message_and_seed():
    test = {"vars": {"offset_dias": 3, "mensaje": "Reserva el {fecha}.",
                     "precargar_reserva": {"fecha": "{fecha}", "nombre": "Ana", "hora": "10:00"}},
            "assert": [{"type": "contains", "value": "x"}]}
    result = hooks.extension_hook("beforeEach", {"test": test})["test"]
    expected = (datetime.now(ZoneInfo("America/Guatemala")).date() + timedelta(days=3)).isoformat()
    assert result["vars"]["fecha"] == expected
    assert result["vars"]["mensaje"] == f"Reserva el {expected}."
    assert result["vars"]["precargar_reserva"]["fecha"] == expected
    assert result["assert"] == test["assert"]
    assert test["vars"]["mensaje"] == "Reserva el {fecha}."  # no muta el caso original


def test_hook_ignores_other_hooks_and_cases_without_offset():
    assert hooks.extension_hook("afterEach", {"test": {}}) is None
    assert hooks.extension_hook("beforeEach", {"test": {"vars": {"mensaje": "hola"}}}) is None
